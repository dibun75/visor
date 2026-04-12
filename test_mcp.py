import asyncio
import json
from mcp.client.stdio import stdio_client
from mcp.client.session import ClientSession
from mcp import ClientOptions

async def main():
    server_params = {"command": "uv", "args": ["--directory", "/home/arunav/visor", "run", "-q", "src/visor/server.py"]}
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                print("Connected!")
                result = await session.call_tool("get_architecture_map", arguments={"depth": 1})
                print("Result:")
                if result.content:
                    print(result.content[0].text[:500] + "...")
                else:
                    print("Empty content")
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(main())
