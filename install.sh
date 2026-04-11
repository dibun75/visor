#!/bin/bash
set -e

echo "======================================"
echo " Starting V.I.S.O.R. Auto-Installer"
echo "======================================"

if ! command -v uv &> /dev/null
then
    echo ">> UV package manager could not be found! Please install it first."
    exit 1
fi

echo ">> Generating system daemon links..."
uv sync

echo ">> Registering FastMCP configuration globally..."
cat << 'EOF' > mcp.config.json
{
  "mcpServers": {
    "visor-mcp": {
      "command": "uv",
      "args": ["run", "visor-mcp"],
      "env": {
        "WORKSPACE_ROOT": "${workspaceFolder}"
      }
    }
  }
}
EOF

echo ">> V.I.S.O.R. packaged successfully. Link complete."
echo ">> To begin, install the VS Code plugin and run 'Start V.I.S.O.R. HUD'."
