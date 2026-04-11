from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import json
import numpy as np

from visor.db.client import db_client, EMBEDDING_DIM

class DriftReport(BaseModel):
    drift_detected: bool
    stale_files: List[Dict[str, Any]]
    severity: str

def register_tools(mcp: FastMCP):
    
    @mcp.tool()
    def get_file_context(path: str) -> str:
        """Returns AST summary + related nodes for a given file. (Placeholder for Epic 2 AST parser)"""
        return f"Context for {path}. Graph not fully built yet."
        
    @mcp.tool()
    def store_memory(role: str, content: str) -> str:
        """Persists an agent conversation turn with an embedding in the local DB."""
        # For now, generate a random embedding vector. In the future this uses a real sentence-transformer model.
        # Epic 1 placeholder vector.
        vec = np.random.rand(EMBEDDING_DIM).tolist()
        mem_id = db_client.store_memory(role, content, vec)
        return f"Successfully stored memory with ID: {mem_id}"
        
    @mcp.tool()
    def get_architecture_map(depth: int = 1) -> str:
        """Returns the full or partial CodeNode graph topology as a JSON string."""
        # Return empty shell until Tree-sitter is integrated
        return json.dumps({"nodes": [], "edges": []})
        
    @mcp.tool()
    def search_codebase(query: str) -> str:
        """Semantic vector search across CodeNodes. Returns list of nodes."""
        # Generates a random query vector placeholder
        vec = np.random.rand(EMBEDDING_DIM).tolist()
        res = db_client.search_similar(vec, limit=5)
        return json.dumps(res)
        
    @mcp.tool()
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
