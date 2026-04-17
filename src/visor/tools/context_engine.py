"""
V.I.S.O.R. Context Intelligence Engine
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Builds ranked, compressed context payloads from a user query using a
multi-signal relevance scoring formula. This is the core innovation that
separates V.I.S.O.R. from a simple code indexer.

Pipeline:
    User Query
        → Skill Resolution (optional strategy override)
        → Semantic Search (embedding similarity)
        → Dependency Expansion (graph traversal)
        → Relevance Scoring (weighted multi-signal)
        → Explainable Reasoning (per-node justification)
        → Context Compression (token budget enforcement)
        → Token Metrics + Prompt Export
        → Final payload ready for LLM injection
"""

from __future__ import annotations

import os
from typing import List, Dict, Any, Optional

import networkx as nx

from visor.db.client import db_client
from visor.db.embeddings import embedder

# ---------------------------------------------------------------------------
# Scoring weights (tunable intent profiles)
# ---------------------------------------------------------------------------

INTENT_PROFILES = {
    "DEFAULT": {"exact": 1.0, "same": 0.7, "embed": 0.5, "dep": 0.3, "recency": 0.2},
    "BUG_FIX": {"exact": 1.0, "same": 1.5, "embed": 0.4, "dep": 1.2, "recency": 1.0},
    "REFACTOR": {"exact": 1.5, "same": 0.5, "embed": 0.3, "dep": 1.5, "recency": 0.1},
    "EXPLAIN": {"exact": 0.8, "same": 0.2, "embed": 1.5, "dep": 0.5, "recency": 0.0},
}

MAX_CONTEXT_TOKENS = 8_000  # Conservative budget to avoid overflows

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_ctx_graph_cache: nx.DiGraph | None = None
_ctx_graph_edge_count: int = -1


def _load_edges_graph() -> nx.DiGraph:
    """Load edges from the DB into a lightweight DiGraph for hop-distance queries."""
    G = nx.DiGraph()
    cursor = db_client.conn.cursor()
    cursor.execute("SELECT from_node, to_node FROM edges")
    for from_n, to_n in cursor.fetchall():
        G.add_edge(from_n, to_n)
    return G


def _get_cached_edges_graph() -> nx.DiGraph:
    """Returns a cached edges graph, rebuilding only when edges change."""
    global _ctx_graph_cache, _ctx_graph_edge_count
    db_client.conn.commit()
    cursor = db_client.conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM edges")
    current_count = cursor.fetchone()[0]
    if _ctx_graph_cache is None or current_count != _ctx_graph_edge_count:
        _ctx_graph_cache = _load_edges_graph()
        _ctx_graph_edge_count = current_count
    return _ctx_graph_cache


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return max(1, len(text) // 4)


def _read_snippet(
    file_path: str, start_line: int, end_line: int, max_lines: int = 40
) -> str:
    """Read a limited code snippet directly from the file to compress token budgets."""
    try:
        if not os.path.isfile(file_path):
            return ""
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Note: start_line / end_line are 0-indexed from Tree-sitter in the DB.
        target_lines = lines[start_line:end_line]
        if len(target_lines) > max_lines:
            # Keep first N/2 and last N/2 lines
            half = max_lines // 2
            top = target_lines[:half]
            bottom = target_lines[-half:]
            return (
                "".join(top)
                + f"\n... [{len(target_lines) - max_lines} lines truncated] ...\n"
                + "".join(bottom)
            )
        return "".join(target_lines)
    except Exception:
        return ""


def _classify_intent(query: str) -> str:
    """Fast heuristic intent scanner mapping a natural language query to a Reasoning Profile."""
    q = query.lower()

    if any(
        k in q for k in ["bug", "fix", "error", "crash", "issue", "exception", "trace"]
    ):
        return "BUG_FIX"

    if any(
        k in q
        for k in ["refactor", "restructure", "clean", "extract", "move", "rename"]
    ):
        return "REFACTOR"

    if any(
        k in q
        for k in [
            "explain",
            "how does",
            "what is",
            "architecture",
            "overview",
            "show me",
        ]
    ):
        return "EXPLAIN"

    return "DEFAULT"


def _generate_reasoning(signals: Dict[str, float]) -> List[str]:
    """Generate human-readable reasoning for why a node was selected."""
    reasons = []
    if signals.get("exact_match", 0) > 0:
        reasons.append("Matched query token in symbol name")
    if signals.get("proximity", 0) > 0:
        reasons.append("Co-located in same file as top semantic hit")
    if signals.get("dependency", 0) > 0:
        reasons.append("Reachable via dependency chain")
    if signals.get("recency", 0) > 0:
        reasons.append("Recently modified file (boosted)")
    if signals.get("embedding", 0) > 0:
        reasons.append(f"Semantic similarity (score: {signals['embedding']})")
    return reasons if reasons else ["Baseline semantic match"]


def _score_node(
    node: Dict[str, Any],
    query_tokens: List[str],
    anchor_file: str,
    anchor_embedding_distance: float,
    hop_map: Dict[str, int],
    recency_map: Dict[str, float],
    weights: Dict[str, float],
) -> tuple[float, Dict[str, float]]:
    """
    Compute a relevance score for a single code node.

    Signals:
        exact_match     — name token overlap with query
        same_file       — same file as the closest semantic match
        embedding_sim   — inverted cosine distance (lower dist = higher score)
        dependency_dist — inverse hop count from anchor file
        recency         — time-decayed modification freshness
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

    # Recency: derived from file_changelog timestamps
    recency = recency_map.get(node["file_path"], 0.0)

    final_score = (
        weights["exact"] * exact
        + weights["same"] * same_file
        + weights["embed"] * embedding_sim
        + weights["dep"] * dep_score
        + weights.get("recency", 0.0) * recency
    )

    debug_signals = {
        "final": round(final_score, 4),
        "exact_match": round(weights["exact"] * exact, 4),
        "proximity": round(weights["same"] * same_file, 4),
        "embedding": round(weights["embed"] * embedding_sim, 4),
        "dependency": round(weights["dep"] * dep_score, 4),
        "recency": round(weights.get("recency", 0.0) * recency, 4),
    }

    return final_score, debug_signals


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_context(
    query: str, max_results: int = 20, skill_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Build a ranked, token-budget-aware context payload for the given query.

    Args:
        query:        Natural language question or task description.
        max_results:  Maximum candidates to retrieve from semantic search.
        skill_name:   Optional skill name to apply strategy overrides.

    Returns:
        A dict with keys:
            ``context``     — Ranked list of relevant code nodes.
            ``debug``       — Intent, skill, per-node scores and reasoning.
            ``metrics``     — Token optimization stats.
            ``prompt_ready``— Pre-formatted text ready for AI injection.
            ``query``       — Echo of the input query.
            ``total_tokens``— Estimated token count of the payload.
            ``truncated``   — True if budget forced truncation.
    """
    db_client.conn.commit()

    # 1. Resolve skill strategy
    active_skill = None
    skill_strategy = None
    if skill_name:
        skill_data = db_client.get_skill_by_name(skill_name)
        if skill_data and skill_data.get("strategy"):
            active_skill = skill_data["name"]
            skill_strategy = skill_data["strategy"]

    # 2. Semantic search — wider net than default
    query_vec = embedder.encode(query)
    candidates = db_client.search_similar(query_vec, limit=max_results)

    if not candidates:
        return {
            "context": [],
            "debug": {
                "intent": "DEFAULT",
                "skill": active_skill,
                "scores": {},
                "reasoning": {},
            },
            "metrics": {
                "estimated_tokens_without": 0,
                "estimated_tokens_with": 0,
                "reduction_percent": 0,
            },
            "prompt_ready": "",
            "query": query,
            "total_tokens": 0,
            "truncated": False,
        }

    # 3. Anchor context — top semantic hit
    anchor_file = candidates[0]["file_path"]
    anchor_dist = candidates[0]["distance"]

    # 4. Compute hop map from anchor file using BFS (max depth 5)
    G = _get_cached_edges_graph()
    hop_map: Dict[str, int] = {}
    if G.has_node(anchor_file):
        for target, hops in nx.single_source_shortest_path_length(
            G, anchor_file, cutoff=5
        ).items():
            hop_map[target] = hops

    # 5. Tokenise query and map intent
    query_tokens = [t.lower() for t in query.split() if len(t) > 2]
    intent = _classify_intent(query)

    # 6. Apply skill strategy overrides
    if skill_strategy:
        override_intent = skill_strategy.get("intent_override")
        if override_intent and override_intent in INTENT_PROFILES:
            intent = override_intent

    weights = dict(INTENT_PROFILES[intent])  # Copy so we don't mutate global

    if skill_strategy:
        scoring_bias = skill_strategy.get("scoring_bias", {})
        for key, value in scoring_bias.items():
            if key in weights:
                weights[key] = value

    # 7. Get file recencies to integrate drift / recency
    all_files = list(set(n["file_path"] for n in candidates))
    recency_map = db_client.get_recency_map(all_files)

    # 8. Score every candidate
    scored: List[Dict[str, Any]] = []
    debug_scores = {}
    debug_reasoning = {}
    for node in candidates:
        score, signals = _score_node(
            node, query_tokens, anchor_file, anchor_dist, hop_map, recency_map, weights
        )
        scored.append({**node, "relevance_score": round(score, 4)})
        node_id = str(node.get("id", "unknown"))
        debug_scores[node_id] = signals
        debug_reasoning[node_id] = _generate_reasoning(signals)

    # 9. Sort descending by relevance
    scored.sort(key=lambda n: n["relevance_score"], reverse=True)

    # 10. Estimate raw token cost (without V.I.S.O.R.) — full file approach
    estimated_without = 0
    seen_files = set()
    for node in scored:
        fp = node["file_path"]
        if fp not in seen_files:
            seen_files.add(fp)
            try:
                if os.path.isfile(fp):
                    estimated_without += _estimate_tokens(
                        open(fp, "r", encoding="utf-8").read()
                    )
            except Exception:
                estimated_without += 500  # Fallback estimate

    # 11. Token budget enforcement + precision snippet injection
    budget = MAX_CONTEXT_TOKENS
    payload: List[Dict[str, Any]] = []
    prompt_parts: List[str] = []
    truncated = False

    for node in scored:
        # Instead of generic docstrings, extract precise compressed snippet bounds!
        sl, el = node.get("start_line", -1), node.get("end_line", -1)
        if sl >= 0 and el >= 0:
            snippet = _read_snippet(node["file_path"], sl, el, max_lines=40)
            node["code_snippet"] = snippet
            # drop docstring string to save JSON space
            node.pop("docstring", None)
            cost_text = snippet
        else:
            cost_text = node.get("docstring", "")

        cost = _estimate_tokens(f"{node['file_path']}:{node['name']} — {cost_text}")
        if budget - cost < 0:
            truncated = True
            break
        budget -= cost
        payload.append(node)
        prompt_parts.append(
            f"// {node['file_path']}:{node.get('start_line', '?')}-{node.get('end_line', '?')} ({node['name']})\n{cost_text}"
        )

    # 12. Compute final metrics
    estimated_with = MAX_CONTEXT_TOKENS - budget
    reduction = (
        round((1.0 - (estimated_with / max(estimated_without, 1))) * 100, 1)
        if estimated_without > 0
        else 0
    )

    # 13. Filter debug data to only payload nodes
    payload_ids = {str(n.get("id")) for n in payload}

    return {
        "context": payload,
        "debug": {
            "intent": intent,
            "skill": active_skill,
            "scores": {k: v for k, v in debug_scores.items() if k in payload_ids},
            "reasoning": {k: v for k, v in debug_reasoning.items() if k in payload_ids},
        },
        "metrics": {
            "estimated_tokens_without": estimated_without,
            "estimated_tokens_with": estimated_with,
            "reduction_percent": reduction,
        },
        "prompt_ready": "\n\n".join(prompt_parts),
        "query": query,
        "total_tokens": estimated_with,
        "truncated": truncated,
    }
