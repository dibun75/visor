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
    def get_drift_report() -> str:
        """Returns stale context warnings based on recent Git changes to prevent hallucinations on outdated logic."""
        # Placeholder for Epic 2 Git Watcher
        report = DriftReport(
             drift_detected=False,
             stale_files=[],
             severity="INFO"
        )
        return report.model_dump_json()
