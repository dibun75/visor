import json
import logging
import os
import threading
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from mcp.server.fastmcp import FastMCP

from visor.db.client import db_client
from visor.db.migration import migrate_old_dbs
from visor.parser.watcher import start_watcher, stop_watcher, index_workspace
from visor.tools.core import register_tools

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(name)s - %(levelname)s - %(message)s")
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
        "strategy": json.dumps(
            {
                "intent_override": "BUG_FIX",
                "scoring_bias": {"dep": 1.2, "recency": 1.5},
                "tool_priority": [
                    "build_context",
                    "get_dependency_chain",
                    "impact_analysis",
                ],
            }
        ),
    },
    {
        "name": "architecture-explainer",
        "description": "Wide graph traversal with embedding-heavy scoring for understanding codebases.",
        "content": "Prioritize semantic similarity and broad architectural context. Explain how components connect.",
        "strategy": json.dumps(
            {
                "intent_override": "EXPLAIN",
                "scoring_bias": {"embed": 1.8, "dep": 0.8},
                "tool_priority": [
                    "build_context",
                    "get_architecture_map",
                    "trace_route",
                ],
            }
        ),
    },
    {
        "name": "refactor-assistant",
        "description": "Dependency clustering and impact analysis for safe refactoring.",
        "content": "Map all downstream dependencies before restructuring. Identify blast radius of changes.",
        "strategy": json.dumps(
            {
                "intent_override": "REFACTOR",
                "scoring_bias": {"dep": 1.5, "exact": 1.5},
                "tool_priority": [
                    "build_context",
                    "impact_analysis",
                    "dead_code_detection",
                ],
            }
        ),
    },
    {
        "name": "performance-optimizer",
        "description": "Hotspot detection with recent file weighting for performance tuning.",
        "content": "Find recently modified hot paths and co-located performance bottlenecks.",
        "strategy": json.dumps(
            {
                "intent_override": "BUG_FIX",
                "scoring_bias": {"recency": 2.0, "same": 1.5},
                "tool_priority": ["build_context", "get_dependency_chain"],
            }
        ),
    },
    {
        "name": "security-auditor",
        "description": "Deep data-flow tracking for identifying vulnerabilities and tracing untrusted input.",
        "content": "Follow data flows from entry points to sinks. Look for missing validation, fail-open states, and OWASP vulnerabilities.",
        "strategy": json.dumps(
            {
                "intent_override": "SECURITY_AUDIT",
                "scoring_bias": {"dep": 1.5, "embed": 1.2},
                "tool_priority": [
                    "build_context",
                    "impact_analysis",
                    "get_dependency_chain",
                ],
            }
        ),
    },
    {
        "name": "clean-code-reviewer",
        "description": "Semantic pattern matching for code reviews and anti-pattern detection.",
        "content": "Analyze code for structural integrity, single responsibility, and architectural adherence. Highlight over-engineering.",
        "strategy": json.dumps(
            {
                "intent_override": "CODE_REVIEW",
                "scoring_bias": {"embed": 1.5, "exact": 1.2},
                "tool_priority": ["build_context", "get_architecture_map"],
            }
        ),
    },
    {
        "name": "systematic-debugger",
        "description": "Heavy graph-traversal strategy for root cause analysis of complex bugs.",
        "content": "Do not guess. Trace the exact execution path from the error origin to the ultimate root cause using deep dependency graphs.",
        "strategy": json.dumps(
            {
                "intent_override": "ROOT_CAUSE_ANALYSIS",
                "scoring_bias": {"dep": 2.0, "recency": 1.0},
                "tool_priority": [
                    "trace_route",
                    "get_dependency_chain",
                    "build_context",
                ],
            }
        ),
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


_WORKSPACE_FROM_ENV = os.environ.get("WORKSPACE_ROOT")

# Project markers that indicate a directory is a real project root
_PROJECT_MARKERS = {
    ".git",
    "pyproject.toml",
    "package.json",
    "Cargo.toml",
    "go.mod",
    "pom.xml",
    ".sln",
}


def _is_project_dir(path: str) -> bool:
    """Check if a directory looks like a real project (has common project markers)."""
    return any(
        os.path.exists(os.path.join(path, marker)) for marker in _PROJECT_MARKERS
    )


def _detect_workspace() -> str:
    """Best-effort workspace detection without MCP roots.

    Priority: WORKSPACE_ROOT env > cwd (if project dir) > "." (deferred).
    """
    if _WORKSPACE_FROM_ENV:
        return _WORKSPACE_FROM_ENV

    cwd = os.path.abspath(os.path.realpath(os.getcwd()))
    if _is_project_dir(cwd):
        return cwd

    # cwd is not a project (probably home dir) — return it but flag for deferred resolution
    return cwd


@asynccontextmanager
async def _lifespan(server: FastMCP):
    """Lifecycle hook: after MCP handshake, query client for workspace roots."""
    workspace = _detect_workspace()
    needs_roots = not _WORKSPACE_FROM_ENV and not _is_project_dir(workspace)

    if needs_roots:
        logger.info(
            "[VISOR] No WORKSPACE_ROOT set and cwd is not a project — will query MCP roots after handshake."
        )

    yield  # MCP handshake completes here

    # After handshake, try to get workspace roots from the MCP client
    if needs_roots:
        try:
            ctx = server.get_context()
            roots_result = await ctx.session.list_roots()
            if roots_result and roots_result.roots:
                root_uri = str(roots_result.roots[0].uri)
                # Convert file:///path/to/dir → /path/to/dir
                if root_uri.startswith("file://"):
                    root_path = urlparse(root_uri).path
                else:
                    root_path = root_uri

                root_path = os.path.abspath(root_path)
                if os.path.isdir(root_path) and root_path != db_client.workspace_root:
                    logger.info(f"[VISOR] MCP roots detected workspace: {root_path}")
                    switched = db_client.reinitialize(root_path)
                    if switched:
                        db_client.register_workspace()
                        # Re-index the correct workspace
                        node_count = db_client.conn.execute(
                            "SELECT COUNT(*) FROM code_nodes"
                        ).fetchone()[0]
                        if node_count == 0:
                            logger.info(
                                "[VISOR] Empty database for new workspace — indexing..."
                            )
                            index_thread = threading.Thread(
                                target=_background_index,
                                args=(root_path,),
                                daemon=True,
                                name="visor-indexer",
                            )
                            index_thread.start()
                        try:
                            start_watcher(root_path)
                        except Exception as e:
                            logger.warning(
                                f"[VISOR] File watcher failed for {root_path}: {e}"
                            )
        except Exception as e:
            logger.warning(f"[VISOR] Could not query MCP roots: {e}")


# Apply lifespan to the MCP server
mcp.settings.lifespan = _lifespan


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
    workspace = _detect_workspace()
    logger.info(f"Starting V.I.S.O.R. MCP Server (workspace={workspace})")

    # Auto-migrate old monolith DBs on first boot
    migrated = migrate_old_dbs(db_client.hub_conn)
    if migrated:
        logger.info(f"[VISOR] Migrated {migrated} old database(s) to hub-and-spoke.")

    # Register this workspace in the global hub
    db_client.register_workspace()
    logger.info(
        f"[VISOR] Registered workspace: {db_client.workspace_name} ({db_client.workspace_hash})"
    )

    # Seed built-in skill strategies (into global hub)
    _seed_default_skills()

    logger.info(f"[VISOR] Hub DB: {db_client.hub_path}")
    logger.info(f"[VISOR] Spoke DB: {db_client.spoke_path}")

    # Log persisted data on startup for verification
    cursor = db_client.conn.cursor()
    node_count = cursor.execute("SELECT COUNT(*) FROM code_nodes").fetchone()[0]
    edge_count = cursor.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
    logger.info(f"[VISOR] Startup DB check — Nodes: {node_count}, Edges: {edge_count}")

    # Only full re-index if the DB is empty AND we have a real project dir
    if node_count == 0 and _is_project_dir(workspace):
        logger.info("[VISOR] Empty database detected — running full workspace index.")
        index_thread = threading.Thread(
            target=_background_index,
            args=(workspace,),
            daemon=True,
            name="visor-indexer",
        )
        index_thread.start()
    elif node_count == 0:
        logger.info(
            "[VISOR] Empty database but cwd is not a project — deferring index until MCP roots are available."
        )
    else:
        logger.info(
            f"[VISOR] Database already populated ({node_count} nodes). Skipping re-index."
        )

    try:
        if _is_project_dir(workspace):
            start_watcher(workspace)
        mcp.run(transport="stdio")
    finally:
        stop_watcher()


if __name__ == "__main__":
    main()
