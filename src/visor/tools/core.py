from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import json
import numpy as np
import functools
import networkx as nx

from visor.db.client import db_client, EMBEDDING_DIM
from visor.db.embeddings import embedder
from visor.tools.context_engine import build_context as _build_context

class DriftReport(BaseModel):
    drift_detected: bool
    stale_files: List[Dict[str, Any]]
    severity: str

def track_telemetry(func):
    """Decorator to track token proxy volume transmitted to the IDE."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        if isinstance(result, str):
            bytes_transmitted = len(result)
        else:
            bytes_transmitted = len(str(result))
            
        try:
            db_client.log_telemetry(func.__name__, bytes_transmitted)
        except Exception:
            pass
            
        return result
    return wrapper

def _build_nx_graph() -> nx.DiGraph:
    """Builds a directed graph of the codebase pulling from the actual edges table."""
    G = nx.DiGraph()
    db_client.conn.commit()
    cursor = db_client.conn.cursor()
    
    # Just fetch file paths to represent our nodes for architectural tracing
    cursor.execute("SELECT DISTINCT file_path FROM code_nodes WHERE file_path NOT LIKE '%node_modules%' AND file_path NOT LIKE '%.venv%'")
    files = [r[0] for r in cursor.fetchall()]
    
    for f in files:
        G.add_node(f)
        
    # Read edges from database
    cursor.execute("SELECT from_node, to_node, relation_type FROM edges")
    db_edges = cursor.fetchall()
    
    for from_n, to_n, rel_type in db_edges:
        if G.has_node(from_n) and G.has_node(to_n):
            G.add_edge(from_n, to_n, type=rel_type)
                
    return G

def register_tools(mcp: FastMCP):
    
    @mcp.tool()
    @track_telemetry
    def get_file_context(path: str) -> str:
        """
        Returns a structured AST summary for a given file, including all indexed
        symbols (classes, functions, imports) and their line ranges.
        """
        db_client.conn.commit()
        cursor = db_client.conn.cursor()
        cursor.execute(
            "SELECT name, node_type, start_line, end_line, docstring FROM code_nodes "
            "WHERE file_path = ? ORDER BY start_line ASC",
            (path,)
        )
        rows = cursor.fetchall()
        if not rows:
            return json.dumps({"error": f"No indexed nodes found for '{path}'. Has the file been saved?"})
        symbols = [
            {"name": r[0], "type": r[1], "start_line": r[2], "end_line": r[3], "docstring": r[4]}
            for r in rows
        ]
        return json.dumps({"file_path": path, "symbol_count": len(symbols), "symbols": symbols})
        
    @mcp.tool()
    @track_telemetry
    def store_memory(role: str, content: str) -> str:
        """Persists an agent conversation turn with an embedding in the local DB."""
        vec = embedder.encode(content)
        mem_id = db_client.store_memory(role, content, vec)
        return f"Successfully stored memory with ID: {mem_id}"
        
    @mcp.tool()
    @track_telemetry
    def get_architecture_map(depth: int = 1) -> str:
        """Returns the full or partial CodeNode graph topology as a JSON string."""
        db_client.conn.commit()
        cursor = db_client.conn.cursor()

        # Get file-level aggregation, filtering out noise directories
        cursor.execute("""
            SELECT file_path,
                   COUNT(*) as total,
                   SUM(CASE WHEN node_type='class' THEN 1 ELSE 0 END) as classes,
                   SUM(CASE WHEN node_type='function' THEN 1 ELSE 0 END) as funcs
            FROM code_nodes
            WHERE file_path NOT LIKE '%node_modules%'
              AND file_path NOT LIKE '%.venv%'
              AND file_path NOT LIKE '%__pycache__%'
              AND file_path NOT LIKE '%dist/%'
              AND file_path NOT LIKE '%.git/%'
              AND file_path NOT LIKE '%.agent/%'
              AND file_path NOT LIKE '%.temp_%'
              AND file_path NOT LIKE '%test_ts%'
            GROUP BY file_path
            ORDER BY total DESC
            LIMIT 70
        """)
        file_rows = cursor.fetchall()

        nodes = []
        for i, (fpath, total, classes, funcs) in enumerate(file_rows):
            # Get top 3 entities for this file
            cursor.execute("""
                SELECT name, node_type FROM code_nodes
                WHERE file_path = ? AND name NOT LIKE 'func_%' AND name != '__init__'
                ORDER BY CASE WHEN node_type='class' THEN 0 ELSE 1 END, name
                LIMIT 3
            """, (fpath,))
            top_entities = [{"name": r[0], "type": r[1]} for r in cursor.fetchall()]

            # Check if recently modified (drift pulse)
            cursor.execute("""
                SELECT COUNT(*) FROM file_changelog
                WHERE file_path = ? AND datetime(changed_at) > datetime('now', '-60 seconds')
            """, (fpath,))
            recently_modified = cursor.fetchone()[0] > 0

            # Extract directory cluster for coloring
            parts = fpath.replace("./", "").split("/")
            cluster = "/".join(parts[:3]) if len(parts) >= 3 else "/".join(parts[:2]) if len(parts) >= 2 else parts[0]

            nodes.append({
                "id": i,
                "file_path": fpath,
                "name": parts[-1] if parts else fpath,
                "node_count": total,
                "classes": classes,
                "functions": funcs,
                "top_entities": top_entities,
                "cluster": cluster,
                "recently_modified": recently_modified,
            })

        # ── Real edges from DB ──────────────────────────────────────────
        # Build a file_path → node id lookup for fast resolution
        path_to_id = {n["file_path"]: n["id"] for n in nodes}

        cursor.execute("""
            SELECT e.from_node, cn.file_path, e.relation_type 
            FROM edges e
            JOIN code_nodes cn ON e.to_node = cn.name COLLATE NOCASE
            LIMIT 500
        """)
        db_edges = cursor.fetchall()

        edges = []
        seen_edge_pairs: set = set()
        for from_path, to_path, rel_type in db_edges:
            src_id = path_to_id.get(from_path)
            tgt_id = path_to_id.get(to_path)
            if src_id is not None and tgt_id is not None and src_id != tgt_id:
                pair = (src_id, tgt_id)
                if pair not in seen_edge_pairs:
                    seen_edge_pairs.add(pair)
                    edges.append({
                        "source": src_id,
                        "target": tgt_id,
                        "type": rel_type,  # "IMPORTS" | "CALLS"
                    })

        return json.dumps({"nodes": nodes, "edges": edges})
        
    @mcp.tool()
    @track_telemetry
    def search_codebase(query: str) -> str:
        """Semantic vector search across CodeNodes. Returns list of nodes."""
        vec = embedder.encode(query)
        res = db_client.search_similar(vec, limit=5)
        return json.dumps(res)
        
    @mcp.tool()
    @track_telemetry
    def get_drift_report(context_files: List[str], loaded_at: str, file_hashes: Optional[Dict[str, str]] = None) -> str:
        """
        Detects context drift between the AI's loaded snapshot and the current codebase.

        Two detection modes:
        - **Hash-based** (preferred): Pass ``file_hashes`` as ``{file_path: sha256_hash}``.
          V.I.S.O.R. compares the provided hashes against the indexed ``file_hash`` column.
          If they differ, the file has changed since the agent last read it.
        - **Timestamp-based** (fallback): Compares ``loaded_at`` against ``file_changelog``
          entries when hashes are not supplied.

        Args:
            context_files: List of file paths the agent currently holds in context.
            loaded_at:     ISO-8601 timestamp of when the agent loaded its context.
            file_hashes:   Optional dict mapping file_path → sha256 hash the agent last saw.
        """
        stale_files = []

        if file_hashes:
            # --- Hash-based drift (accurate) ---
            cursor = db_client.conn.cursor()
            for fpath, agent_hash in file_hashes.items():
                cursor.execute("SELECT file_hash FROM code_nodes WHERE file_path=? LIMIT 1", (fpath,))
                row = cursor.fetchone()
                stored_hash = row[0] if row else None
                if stored_hash and stored_hash != agent_hash:
                    stale_files.append({
                        "path": fpath,
                        "reason": "hash_mismatch",
                        "stored_hash": stored_hash[:8] + "...",
                        "agent_hash": agent_hash[:8] + "...",
                    })
        else:
            # --- Timestamp-based drift (fallback) ---
            try:
                from dateutil.parser import parse as parse_date
                context_time = parse_date(loaded_at)
            except Exception:
                return DriftReport(drift_detected=False, stale_files=[], severity="INFO").model_dump_json()

            cursor = db_client.conn.cursor()
            placeholders = ','.join(['?'] * len(context_files))
            cursor.execute(
                f"SELECT file_path, changed_at FROM file_changelog WHERE file_path IN ({placeholders})",
                context_files
            )
            for file_path, changed_at_str in cursor.fetchall():
                try:
                    from dateutil.parser import parse as parse_date
                    if parse_date(changed_at_str) > parse_date(loaded_at):
                        stale_files.append({"path": file_path, "changed_at": changed_at_str, "reason": "timestamp"})
                except Exception:
                    pass

        severity = "CRITICAL" if stale_files else "INFO"
        report = DriftReport(drift_detected=bool(stale_files), stale_files=stale_files, severity=severity)
        return report.model_dump_json()

    @mcp.tool()
    def get_telemetry() -> str:
        """Returns the current state of telemetry data. graph_nodes, context_burn, drift_alert."""
        # Flush the read snapshot so we can see writes from the watchdog process
        db_client.conn.commit()
        
        cursor = db_client.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM code_nodes")
        nodes = cursor.fetchone()[0]
        
        cursor.execute("SELECT IFNULL(SUM(length(content)), 0) FROM agent_memory")
        memory_burn = cursor.fetchone()[0]
        
        cursor.execute("SELECT IFNULL(SUM(bytes_transmitted), 0) FROM telemetry_logs")
        tool_burn = cursor.fetchone()[0]
        
        burn = memory_burn + tool_burn
        
        # Simple global drift proxy: Any modifications inside the last 60 seconds
        cursor.execute("SELECT COUNT(*) FROM file_changelog WHERE datetime(changed_at) > datetime('now', '-60 seconds')")
        drift = cursor.fetchone()[0] > 0
        
        data = {"graph_nodes": nodes, "context_burn": burn, "drift_alert": drift}
        return json.dumps(data)

    @mcp.tool()
    @track_telemetry
    def impact_analysis(file_path: str) -> str:
        """Fetch downstream dependent files impacted by a change using BFS (max depth 5)."""
        G = _build_nx_graph()
        if not G.has_node(file_path):
            return json.dumps({"error": f"Node {file_path} not found in architecture graph."})
            
        # BFS up to depth 5
        edges = nx.bfs_edges(G, source=file_path, depth_limit=5)
        impacted_nodes = [v for u, v in edges]
        return json.dumps({
            "target": file_path,
            "blast_radius": list(set(impacted_nodes))
        })

    @mcp.tool()
    @track_telemetry
    def trace_route(source: str, target: str) -> str:
        """Trace a path from a source node to a target node."""
        G = _build_nx_graph()
        if not G.has_node(source) or not G.has_node(target):
            return json.dumps({"error": "Source or Target node not found."})
            
        try:
            path = nx.shortest_path(G, source=source, target=target)
            return json.dumps({"path": path})
        except nx.NetworkXNoPath:
            return json.dumps({"error": "No architectural path found between these nodes."})

    @mcp.tool()
    @track_telemetry
    def dead_code_detection() -> str:
        """Finds nodes with an in-degree of 0 (no incoming callers)."""
        G = _build_nx_graph()
        dead_nodes = [n for n, d in G.in_degree() if d == 0]
        return json.dumps({"isolated_nodes": dead_nodes})

    @mcp.tool()
    @track_telemetry
    def get_symbol_context(symbol: str) -> str:
        """
        Returns all indexed AST nodes matching a symbol name, including file path,
        node type (class/function/import), and precise line range.

        Useful for answering: *"Where is `VectorDBClient` defined and what does it do?"*

        Args:
            symbol: The exact or partial name of the class, function, or import to look up.
        """
        db_client.conn.commit()
        cursor = db_client.conn.cursor()
        cursor.execute(
            "SELECT name, node_type, file_path, start_line, end_line, docstring "
            "FROM code_nodes WHERE name LIKE ? ORDER BY node_type, file_path",
            (f"%{symbol}%",)
        )
        rows = cursor.fetchall()
        if not rows:
            return json.dumps({"error": f"Symbol '{symbol}' not found in index."})
        results = [
            {
                "name": r[0],
                "type": r[1],
                "file": r[2],
                "start_line": r[3],
                "end_line": r[4],
                "docstring": r[5],
            }
            for r in rows
        ]
        return json.dumps({"symbol": symbol, "matches": results})

    @mcp.tool()
    @track_telemetry
    def get_dependency_chain(symbol: str) -> str:
        """
        Traverses the import edges graph from the file containing ``symbol``
        and returns the full transitive dependency chain (max depth 5).

        Useful for answering: *"What does `auth.py` ultimately depend on?"*

        Args:
            symbol: Name of a class or function. Its source file becomes the
                    root of the BFS traversal.
        """
        db_client.conn.commit()
        cursor = db_client.conn.cursor()
        cursor.execute("SELECT file_path FROM code_nodes WHERE name LIKE ? LIMIT 1", (f"%{symbol}%",))
        row = cursor.fetchone()
        if not row:
            return json.dumps({"error": f"Symbol '{symbol}' not found — cannot resolve dependency chain."})
        source_file = row[0]

        G = _build_nx_graph()
        if not G.has_node(source_file):
            return json.dumps({"source": source_file, "chain": [], "note": "No outgoing edges found. Run the file watcher to populate the edges table."})

        chain = list(nx.bfs_tree(G, source=source_file, depth_limit=5).nodes())
        chain.remove(source_file)  # Exclude the root itself
        return json.dumps({"symbol": symbol, "source_file": source_file, "dependency_chain": chain})

    @mcp.tool()
    @track_telemetry
    def build_context(query: str, skill: Optional[str] = None) -> str:
        """
        **Context Intelligence Engine** — the most powerful V.I.S.O.R. tool.

        Builds a ranked, token-budget-enforced context payload from a natural
        language query. Combines four signals:
        - Embedding similarity (semantic proximity)
        - Exact symbol name match
        - Co-location in the same file as the top hit
        - Dependency graph distance

        Returns a scored list of code nodes ready to be injected into an LLM
        prompt, capped at 8,000 tokens to prevent context overflow.

        Example:
            ``build_context("how is authentication handled")``
        """
        result = _build_context(query, skill_name=skill)
        return json.dumps(result)

    @mcp.prompt()
    def get_visor_skill(skill_name: str) -> str:
        """Fetch a specific Custom V.I.S.O.R Skill instruction pack by name."""
        skills = db_client.get_custom_skills()
        for s in skills:
            if s["name"].lower() == skill_name.lower():
                return f"Skill: {s['name']}\nDescription: {s['description']}\n\nInstructions:\n{s['content']}"
        return f"Error: Skill '{skill_name}' not found. Use list_custom_skills tool to view available skills."

    @mcp.tool()
    @track_telemetry
    def list_custom_skills() -> str:
        """List all available custom V.I.S.O.R architecture skills."""
        skills = db_client.get_custom_skills()
        return json.dumps([{"id": s["id"], "name": s["name"], "description": s["description"], "strategy": s.get("strategy")} for s in skills])

    @mcp.tool()
    @track_telemetry
    def add_custom_skill(name: str, description: str, content: str, strategy: Optional[str] = None) -> str:
        """Adds a newly created custom skill via the UI."""
        skill_id = db_client.add_custom_skill(name, description, content, strategy)
        return json.dumps({"success": True, "id": skill_id})

    @mcp.tool()
    @track_telemetry
    def delete_custom_skill(skill_id: int) -> str:
        """Deletes a custom skill."""
        success = db_client.delete_custom_skill(skill_id)
        return json.dumps({"success": success})
