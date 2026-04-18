# V.I.S.O.R. HUD

**Visual Intelligence System for Orchestrated Reasoning**

> A real-time WebGPU-powered Developer HUD that gives your AI coding agent a visual brain — right inside your editor.

---

## ✨ What is V.I.S.O.R.?

V.I.S.O.R. is a **Context Intelligence Engine** for AI coding agents. It parses your codebase into an AST-aware graph, embeds it with semantic vectors, and provides powerful tools for code navigation, architecture analysis, and context-aware reasoning.

The **HUD extension** brings this to life with an interactive 3D visualization of your codebase graph, real-time telemetry, and AI focus tracking — all rendered with WebGPU.

## 🚀 Features

### 🧠 Context Intelligence Engine
- **Semantic Code Search** — Find code by meaning, not just text
- **Architecture Map** — Visualize your entire codebase as an interactive dependency graph
- **Impact Analysis** — See exactly which files are affected by a change
- **Dependency Chains** — Trace the full transitive dependency tree of any symbol
- **Dead Code Detection** — Find unreachable nodes with zero incoming callers
- **Drift Detection** — Know when your AI agent's context is stale

### 🎯 AI Agent Integration (MCP)
- Works with any AI agent that supports the **Model Context Protocol**
- Provides 20+ specialized tools for code intelligence
- **Custom Skills** — Create reusable analysis strategies
- **Memory System** — Persistent conversation memory with semantic recall
- **HUD Focus** — Watch your AI agent's attention in real-time on the 3D graph

### 📊 Real-Time Telemetry
- Graph node count and edge statistics
- Context token budget tracking
- Drift alerts when files change under the agent

## 📦 Installation

### From Open VSX / Marketplace
Search for **"V.I.S.O.R. HUD"** in your editor's extension panel and install.

### MCP Server (Required)
The HUD extension visualizes data from the V.I.S.O.R. MCP server. Install it via:

```bash
uvx visor-mcp
```

Or add to your IDE's MCP configuration:

```json
{
  "visor": {
    "command": "uvx",
    "args": ["visor-mcp"]
  }
}
```

## 🛠️ Usage

1. **Open the HUD** — Click the V.I.S.O.R. icon in the activity bar, or run `Start V.I.S.O.R. HUD` from the command palette
2. **Ask your AI agent** to use V.I.S.O.R. tools like `build_context`, `search_codebase`, or `get_architecture_map`
3. **Watch the graph** update in real-time as your agent explores your codebase

## ⚙️ Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `visor.localProxyPort` | `4173` | Local Vite dev server port |
| `visor.remoteProxyPort` | `8080` | Remote SSH Docker proxy port |
| `visor.enableLocalForwarding` | `true` | Enable automatic reverse-tunnel over SSH |
| `visor.serverPath` | `""` | Path to V.I.S.O.R. server (auto-detected if empty) |

## 🏗️ Architecture

```
visor-mcp (Python)          visor-hud (Extension)
┌─────────────────┐         ┌──────────────────┐
│  MCP Server     │◄────────│  WebGPU HUD      │
│  AST Parser     │         │  3D Graph View   │
│  Vector DB      │         │  Telemetry Panel │
│  Context Engine │         │  Focus Tracker   │
└─────────────────┘         └──────────────────┘
```

## 📄 License

MIT — see [LICENSE](https://github.com/dibun75/visor/blob/main/LICENSE) for details.
