from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import json
import numpy as np
import functools
import networkx as nx

from visor.db.client import db_client, EMBEDDING_DIM

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
    """Builds a directed graph of the codebase simulating dependencies based on directory clustering."""
    G = nx.DiGraph()
    db_client.conn.commit()
    cursor = db_client.conn.cursor()
    
    # Just fetch file paths to represent our nodes for architectural tracing
    cursor.execute("SELECT DISTINCT file_path FROM code_nodes WHERE file_path NOT LIKE '%node_modules%' AND file_path NOT LIKE '%.venv%'")
    files = [r[0] for r in cursor.fetchall()]
    
    for f in files:
        G.add_node(f)
        
    # Simulate edges based on directory clusters (until AST parser is finished)
    cluster_map = {}
    for f in files:
        parts = f.replace("./", "").split("/")
        cluster = "/".join(parts[:3]) if len(parts) >= 3 else "/".join(parts[:2]) if len(parts) >= 2 else parts[0]
        cluster_map.setdefault(cluster, []).append(f)
        
    for cluster, f_list in cluster_map.items():
        for i in range(len(f_list)):
            for j in range(i + 1, min(i + 5, len(f_list))): # Limit intra-cluster edges
                # Add bidirectional simulated dependency
                G.add_edge(f_list[i], f_list[j], type="EXTRACTED")
                G.add_edge(f_list[j], f_list[i], type="INFERRED")
                
    return G

def register_tools(mcp: FastMCP):
    
    @mcp.tool()
    @track_telemetry
    def get_file_context(path: str) -> str:
        """Returns AST summary + related nodes for a given file. (Placeholder for Epic 2 AST parser)"""
        return f"Context for {path}. Graph not fully built yet."
        
    @mcp.tool()
    @track_telemetry
    def store_memory(role: str, content: str) -> str:
        """Persists an agent conversation turn with an embedding in the local DB."""
        # For now, generate a random embedding vector. In the future this uses a real sentence-transformer model.
        # Epic 1 placeholder vector.
        vec = np.random.rand(EMBEDDING_DIM).tolist()
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

        # Compute co-directory edges (files in same cluster)
        edges = []
        cluster_map: Dict[str, list] = {}
        for node in nodes:
            cluster_map.setdefault(node["cluster"], []).append(node["id"])

        for cluster, ids in cluster_map.items():
            # Connect files within the same cluster (BFS depth=1)
            for j in range(len(ids)):
                for k in range(j + 1, min(j + 3, len(ids))):
                    edges.append({
                        "source": ids[j],
                        "target": ids[k],
                        "type": "EXTRACTED",
                    })

        return json.dumps({"nodes": nodes, "edges": edges})
        
    @mcp.tool()
    @track_telemetry
    def search_codebase(query: str) -> str:
        """Semantic vector search across CodeNodes. Returns list of nodes."""
        # Generates a random query vector placeholder
        vec = np.random.rand(EMBEDDING_DIM).tolist()
        res = db_client.search_similar(vec, limit=5)
        return json.dumps(res)
        
    @mcp.tool()
    @track_telemetry
    def get_drift_report(context_files: List[str], loaded_at: str) -> str:
        """Returns stale context warnings based on recent Git changes to prevent hallucinations on outdated logic."""
        try:
            from dateutil.parser import parse as parse_date
            context_time = parse_date(loaded_at)
        except Exception:
            return DriftReport(drift_detected=False, stale_files=[], severity="INFO").model_dump_json()

        cursor = db_client.conn.cursor()
        placeholders = ','.join(['?'] * len(context_files))
        query = f"SELECT file_path, changed_at FROM file_changelog WHERE file_path IN ({placeholders})"
        cursor.execute(query, context_files)
        
        stale_files = []
        for row in cursor.fetchall():
            file_path, changed_at_str = row
            try:
                 changed_at = parse_date(changed_at_str)
                 if changed_at > context_time:
                     stale_files.append({"path": file_path, "changed_at": changed_at_str})
            except Exception:
                 pass
                 
        if stale_files:
            report = DriftReport(
                drift_detected=True,
                stale_files=stale_files,
                severity="CRITICAL"
            )
        else:
            report = DriftReport(
                 drift_detected=False,
                 stale_files=[],
                 severity="INFO"
            )
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
        return json.dumps([{"id": s["id"], "name": s["name"], "description": s["description"], "content": s["content"]} for s in skills])

    @mcp.tool()
    @track_telemetry
    def add_custom_skill(name: str, description: str, content: str) -> str:
        """Adds a newly created custom skill via the UI."""
        skill_id = db_client.add_custom_skill(name, description, content)
        return json.dumps({"success": True, "id": skill_id})

    @mcp.tool()
    @track_telemetry
    def delete_custom_skill(skill_id: int) -> str:
        """Deletes a custom skill."""
        success = db_client.delete_custom_skill(skill_id)
        return json.dumps({"success": success})
