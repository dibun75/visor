import asyncio
import logging
import threading
from mcp.server.fastmcp import FastMCP

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from visor.tools.core import register_tools

# Initialize FastMCP Server
mcp = FastMCP("VISOR")

register_tools(mcp)

@mcp.tool()
def health_check() -> str:
    """Basic health-check endpoint confirming the server is alive."""
    return "V.I.S.O.R MCP daemon is alive and operational."

import os
from visor.parser.watcher import start_watcher, stop_watcher, index_workspace


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

    # Kick off the workspace scan in the background — MCP server is usable immediately
    index_thread = threading.Thread(
        target=_background_index,
        args=(workspace,),
        daemon=True,
        name="visor-indexer",
    )
    index_thread.start()

    try:
        start_watcher(workspace)
        mcp.run(transport="stdio")
    finally:
        stop_watcher()


if __name__ == "__main__":
    main()
