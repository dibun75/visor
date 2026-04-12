import anyio
import json
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.types import CallToolResult

server_params = StdioServerParameters(command="uv", args=["run", "src/visor/server.py"])

async def run():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("Initialized!")
            res = await session.call_tool("get_architecture_map", {"depth": 1})
            if res.isError:
                print("Error:", res.content)
            else:
                s = res.content[0].text
                try:
                    d = json.loads(s)
                    print(f"Success! {len(d['nodes'])} nodes, {len(d['edges'])} edges")
                except Exception as e:
                    print("JSON PARSE ERROR!")
                    print(s[:500])
            
            # test telemetry
            res2 = await session.call_tool("get_telemetry")
            if res2.isError:
                print("Error:", res2.content)
            else:
                print("Telemetry:", res2.content[0].text)

anyio.run(run)
