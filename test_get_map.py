from visor.server import mcp
import asyncio
from visor.parser.watcher import _ensure_changelog
from visor.db.client import db_client

# make sure table exists
_ensure_changelog(db_client.conn)

async def test():
    # simulate what FastMCP does
    res = await mcp.call_tool("get_architecture_map", {"depth": 1})
    if res.is_error:
        print("ERROR:", [c.text for c in res.content])
    else:
        print("SUCCESS! Length:", len(res.content[0].text))

asyncio.run(test())
