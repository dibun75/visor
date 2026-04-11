import asyncio
import logging
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
    """Basic health-check endpoint confirming the server is alive"""
    return "V.I.S.O.R MCP daemon is alive and operational."

import os
from visor.parser.watcher import start_watcher, stop_watcher, index_workspace

def main():
    """CLI entrypoint to start the MCP daemon using stdio"""
    workspace = os.environ.get("WORKSPACE_ROOT", ".")
    logger.info(f"Starting V.I.S.O.R. MCP Server daemon in {workspace}...")
    
    try:
        index_workspace(workspace)
        start_watcher(workspace)
        mcp.run(transport="stdio")
    finally:
        stop_watcher()

if __name__ == "__main__":
    main()
