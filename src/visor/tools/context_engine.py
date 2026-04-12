"""
V.I.S.O.R. Context Intelligence Engine
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Builds ranked, compressed context payloads from a user query using a
multi-signal relevance scoring formula. This is the core innovation that
separates V.I.S.O.R. from a simple code indexer.

Pipeline:
    User Query
        → Semantic Search (embedding similarity)
        → Dependency Expansion (graph traversal)
        → Relevance Scoring (weighted multi-signal)
        → Context Compression (token budget enforcement)
        → Final payload ready for LLM injection
"""
from __future__ import annotations

import math
from typing import List, Dict, Any

import networkx as nx

from visor.db.client import db_client
from visor.db.embeddings import embedder

# ---------------------------------------------------------------------------
# Scoring weights (tunable)
# ---------------------------------------------------------------------------

_W_EXACT_MATCH   = 1.0   # Symbol name exactly matches a query token
_W_SAME_FILE     = 0.7   # Node is in the same file as the top semantic hit
_W_EMBEDDING     = 0.5   # Normalised embedding similarity contribution
_W_DEPENDENCY    = 0.3   # Inverse of graph hop distance from top hit

MAX_CONTEXT_TOKENS = 8_000  # Conservative budget to avoid overflows

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_edges_graph() -> nx.DiGraph:
    """Load edges from the DB into a lightweight DiGraph for hop-distance queries."""
    G = nx.DiGraph()
    cursor = db_client.conn.cursor()
    cursor.execute("SELECT from_node, to_node FROM edges")
    for from_n, to_n in cursor.fetchall():
        G.add_edge(from_n, to_n)
    return G


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return max(1, len(text) // 4)


def _score_node(
    node: Dict[str, Any],
    query_tokens: List[str],
    anchor_file: str,
    anchor_embedding_distance: float,
    hop_map: Dict[str, int],
) -> float:
    """
    Compute a relevance score for a single code node.

    Signals:
        exact_match     — name token overlap with query
        same_file       — same file as the closest semantic match
        embedding_sim   — inverted cosine distance (lower dist = higher score)
        dependency_dist — inverse hop count from anchor file
    """
    name_lower = node["name"].lower()
    exact = 1.0 if any(t in name_lower for t in query_tokens) else 0.0

    same_file = 1.0 if node["file_path"] == anchor_file else 0.0

    # Embedding: distance is already normalised [0, 2] for L2 with unit vectors.
    # We invert it so closer = higher score; clamp to [0, 1].
    raw_dist = node.get("distance", 1.0)
    embedding_sim = max(0.0, 1.0 - (raw_dist / 2.0))

    # Dependency: BFS hop count from anchor file to this node's file.
    hops = hop_map.get(node["file_path"], None)
    if hops is None:
        dep_score = 0.0
    else:
        # 0 hops (same node) = 1.0; each additional hop halves the score
        dep_score = 1.0 / (1.0 + hops)

    return (
        _W_EXACT_MATCH   * exact
        + _W_SAME_FILE   * same_file
        + _W_EMBEDDING   * embedding_sim
        + _W_DEPENDENCY  * dep_score
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_context(query: str, max_results: int = 20) -> Dict[str, Any]:
    """
    Build a ranked, token-budget-aware context payload for the given query.

    Args:
        query:        Natural language question or task description.
        max_results:  Maximum candidates to retrieve from semantic search.

    Returns:
        A dict with keys:
            ``query``       — Echo of the input query.
            ``nodes``       — Ranked list of relevant code nodes.
            ``total_tokens``— Estimated token count of the payload.
            ``truncated``   — True if budget forced truncation.
    """
    db_client.conn.commit()

    # 1. Semantic search — wider net than default
    query_vec = embedder.encode(query)
    candidates = db_client.search_similar(query_vec, limit=max_results)

    if not candidates:
        return {"query": query, "nodes": [], "total_tokens": 0, "truncated": False}

    # 2. Anchor context — top semantic hit
    anchor_file = candidates[0]["file_path"]
    anchor_dist = candidates[0]["distance"]

    # 3. Compute hop map from anchor file using BFS (max depth 5)
    G = _load_edges_graph()
    hop_map: Dict[str, int] = {}
    if G.has_node(anchor_file):
        for target, hops in nx.single_source_shortest_path_length(G, anchor_file, cutoff=5).items():
            hop_map[target] = hops

    # 4. Tokenise query for exact-match scoring
    query_tokens = [t.lower() for t in query.split() if len(t) > 2]

    # 5. Score every candidate
    scored: List[Dict[str, Any]] = []
    for node in candidates:
        score = _score_node(node, query_tokens, anchor_file, anchor_dist, hop_map)
        scored.append({**node, "relevance_score": round(score, 4)})

    # 6. Sort descending by relevance
    scored.sort(key=lambda n: n["relevance_score"], reverse=True)

    # 7. Token budget enforcement — build payload within budget
    budget = MAX_CONTEXT_TOKENS
    payload: List[Dict[str, Any]] = []
    truncated = False

    for node in scored:
        snippet = f"{node['file_path']}:{node['name']} — {node.get('docstring','')}"
        cost = _estimate_tokens(snippet)
        if budget - cost < 0:
            truncated = True
            break
        budget -= cost
        payload.append(node)

    return {
        "query": query,
        "nodes": payload,
        "total_tokens": MAX_CONTEXT_TOKENS - budget,
        "truncated": truncated,
    }
