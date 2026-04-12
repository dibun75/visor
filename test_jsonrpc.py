import json, subprocess, copy

req = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "get_architecture_map",
        "arguments": {"depth": 1}
    }
}

p = subprocess.Popen(
    ["uv", "run", "src/visor/server.py"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

stdout, stderr = p.communicate(input=json.dumps(req) + "\n", timeout=10)
print("STDOUT:", stdout)
print("STDERR:", stderr)
