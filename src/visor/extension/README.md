<div align="center">
  <img src="https://github.com/dibun75/visor/raw/main/docs/assets/icon.png" alt="V.I.S.O.R. logo" width="120"/>
  <h1>V.I.S.O.R. HUD</h1>
  <p>Optional WebGPU view of a local V.I.S.O.R. index.</p>
</div>

The HUD is optional. Context retrieval lives in the `visor` CLI and the `visor-mcp` stdio server. Both work without this extension.

The extension draws the indexed dependency graph in the editor and polls `get_telemetry`. That payload contains:

- `graph_nodes`: count of indexed code nodes for the workspace
- `context_burn`: sum of recorded MCP payload bytes for the workspace, shown in the HUD as tokens after dividing by 4
- `drift_alert` and `drift_files`: files whose changelog entries are newer than 120 seconds
- `agent_focus`: present after a client calls `set_hud_focus`
- `workspace_name`

`context_burn` is local tool-payload accounting. It is not provider token usage and it is not a measure of retrieval quality.

<div align="center">
  <img src="https://github.com/dibun75/visor/raw/main/docs/assets/hud_overview.png" alt="Optional HUD with a dependency graph and telemetry panels" width="800"/>
  <p>Existing capture. It was not recaptured with the current build, so the numbers in the image are not a measurement for this revision.</p>
</div>

## Install and verify the server

Install [`uv`](https://docs.astral.sh/uv/getting-started/installation/), then check the CLI:

```bash
uvx --from visor-mcp visor doctor
uvx --from visor-mcp visor index
```

Codex and Claude Code can register the server directly:

```bash
codex mcp add visor -- uvx visor-mcp
claude mcp add visor -- uvx visor-mcp
```

For VS Code, add `.vscode/mcp.json`:

```json
{
  "servers": {
    "visor": {
      "command": "uvx",
      "args": ["visor-mcp"]
    }
  }
}
```

`visor init` only prints that style of entry. It does not write the file.

Search for **V.I.S.O.R. HUD** in the editor, or install [dibun75.visor-hud on Open VSX](https://open-vsx.org/extension/dibun75/visor-hud). Open the V.I.S.O.R. activity-bar view, or run **Start V.I.S.O.R. HUD** from the command palette.

## Editors

The extension targets VS Code `^1.80.0` and other editors that install Open VSX extensions, including the Antigravity setup documented in the repository README. Codex, Claude Code, Cursor, and Claude Desktop use the MCP server or the CLI. They do not need this extension to retrieve context.

## Settings

| Setting | Default | Role |
| --- | --- | --- |
| `visor.localProxyPort` | `4173` | Port for a local HUD dev server |
| `visor.remoteProxyPort` | `8080` | Port used for a remote SSH proxy |
| `visor.enableLocalForwarding` | `true` | Open a reverse tunnel when the HUD is reached over SSH |
| `visor.serverPath` | empty | Optional path to `server.py` or a `visor` executable. Empty uses discovery |

## What the graph is

The MCP server indexes the workspace and can answer `get_architecture_map`. The webview renders that map. Structural import edges and function-call edges use the legend in the view. Selecting or focusing a node depends on the running HUD and on `set_hud_focus`; this page does not claim a particular focus state for the still above.

Project documentation: [github.com/dibun75/visor](https://github.com/dibun75/visor).

## License

MIT
