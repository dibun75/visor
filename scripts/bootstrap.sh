#!/bin/bash
set -e

echo ">> Booting V.I.S.O.R. Remote Environment via Fast Vibe-Coding loop..."

# Start compose in watch mode detached
docker compose up -d
docker compose watch &

echo "================================================="
echo " Fetching Dynamic Ports "
echo "================================================="

# Extract ephemeral ports
MCP_PORT=$(docker compose port visor-mcp 8000 | cut -d: -f2)
HUD_PORT=$(docker compose port visor-hud 5173 | cut -d: -f2)

export VISOR_INTERNAL_MCP_PORT=$MCP_PORT
export VISOR_INTERNAL_HUD_PORT=$HUD_PORT

echo ">> Backend (mcp) bound to Ephemeral Port: $MCP_PORT"
echo ">> Frontend (hud) bound to Ephemeral Port: $HUD_PORT"
echo ">> System Nominal."
