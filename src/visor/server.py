import json
import logging
import os
import threading

from mcp.server.fastmcp import FastMCP

from visor.db.client import db_client
from visor.parser.watcher import start_watcher, stop_watcher, index_workspace
from visor.tools.core import register_tools

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize FastMCP Server
mcp = FastMCP("VISOR")

register_tools(mcp)

@mcp.tool()
def health_check() -> str:
    """Basic health-check endpoint confirming the server is alive."""
    return "V.I.S.O.R MCP daemon is alive and operational."

# ---------------------------------------------------------------------------
# Built-in Skill Strategies (seeded on first boot)
# ---------------------------------------------------------------------------

_DEFAULT_SKILLS = [
    {
        "name": "bug-fixer",
        "description": "Deep call chain tracing with high recency boost for hunting bugs.",
        "content": "Focus on recently modified files and dependency chains. Trace the call stack from the error location outward.",
        "strategy": json.dumps({
            "intent_override": "BUG_FIX",
            "scoring_bias": {"dep": 1.2, "recency": 1.5},
            "tool_priority": ["build_context", "get_dependency_chain", "impact_analysis"],
        }),
    },
    {
        "name": "architecture-explainer",
        "description": "Wide graph traversal with embedding-heavy scoring for understanding codebases.",
        "content": "Prioritize semantic similarity and broad architectural context. Explain how components connect.",
        "strategy": json.dumps({
            "intent_override": "EXPLAIN",
            "scoring_bias": {"embed": 1.8, "dep": 0.8},
            "tool_priority": ["build_context", "get_architecture_map", "trace_route"],
        }),
    },
    {
        "name": "refactor-assistant",
        "description": "Dependency clustering and impact analysis for safe refactoring.",
        "content": "Map all downstream dependencies before restructuring. Identify blast radius of changes.",
        "strategy": json.dumps({
            "intent_override": "REFACTOR",
            "scoring_bias": {"dep": 1.5, "exact": 1.5},
            "tool_priority": ["build_context", "impact_analysis", "dead_code_detection"],
        }),
    },
    {
        "name": "performance-optimizer",
        "description": "Hotspot detection with recent file weighting for performance tuning.",
        "content": "Find recently modified hot paths and co-located performance bottlenecks.",
        "strategy": json.dumps({
            "intent_override": "BUG_FIX",
            "scoring_bias": {"recency": 2.0, "same": 1.5},
            "tool_priority": ["build_context", "get_dependency_chain"],
        }),
    },
]


def _seed_default_skills():
    """Insert built-in skills on first boot if they don't already exist."""
    existing = {s["name"].lower() for s in db_client.get_custom_skills()}
    for skill in _DEFAULT_SKILLS:
        if skill["name"].lower() not in existing:
            db_client.add_custom_skill(
                name=skill["name"],
                description=skill["description"],
                content=skill["content"],
                strategy=skill["strategy"],
            )
            logger.info(f"Seeded built-in skill: {skill['name']}")


def _background_index(workspace: str) -> None:
    """Run the progressive workspace scan in a daemon thread.

    This lets the MCP server start accepting tool calls immediately while
    the (potentially slow) embedding pipeline runs in the background.
    The file watcher will handle any changes that arrive during indexing.
    """
    try:
        index_workspace(workspace)
    except Exception as exc:
        logger.error(f"Background indexing failed: {exc}")


def main():
    """CLI entrypoint to start the MCP daemon using stdio transport."""
    workspace = os.environ.get("WORKSPACE_ROOT", ".")
    logger.info(f"Starting V.I.S.O.R. MCP Server (workspace={workspace})")

    # Seed built-in skill strategies
    _seed_default_skills()

    logger.debug(f"VISOR_DB_PATH: {os.environ.get('VISOR_DB_PATH')}")
    logger.debug(f"WORKSPACE_ROOT: {os.environ.get('WORKSPACE_ROOT')}")

    # Task 5: Log persisted data on startup for verification
    cursor = db_client.conn.cursor()
    node_count = cursor.execute("SELECT COUNT(*) FROM code_nodes").fetchone()[0]
    edge_count = cursor.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
    logger.info(f"[VISOR] Startup DB check — Nodes: {node_count}, Edges: {edge_count}")

    # Task 4: Only full re-index if the DB is empty.
    # If nodes already exist, skip heavy boot scan — the file watcher will
    # handle incremental changes going forward.
    if node_count == 0:
        logger.info("[VISOR] Empty database detected — running full workspace index.")
        index_thread = threading.Thread(
            target=_background_index,
            args=(workspace,),
            daemon=True,
            name="visor-indexer",
        )
        index_thread.start()
    else:
        logger.info(f"[VISOR] Database already populated ({node_count} nodes). Skipping re-index.")

    try:
        start_watcher(workspace)
        mcp.run(transport="stdio")
    finally:
        stop_watcher()


if __name__ == "__main__":
    main()
