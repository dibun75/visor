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

def main():
    """CLI entrypoint to start the MCP daemon using stdio"""
    logger.info("Starting V.I.S.O.R. MCP Server daemon...")
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
