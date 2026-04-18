# V.I.S.O.R. HUD

> A real-time 3D visualization of your codebase — right inside your editor. Watch your AI agent think.

---

## What is V.I.S.O.R.?

V.I.S.O.R. is a **smart helper for AI coding assistants**. It reads your code, understands how files are connected, and gives your AI exactly the right context — saving time and avoiding mistakes.

The **HUD extension** adds a visual layer: an interactive 3D graph of your codebase that updates in real-time as your AI agent works.

<div align="center">
  <h3>🎬 See it in action</h3>
</div>

<div align="center">
https://github.com/dibun75/visor/raw/main/docs/assets/demo.mp4
</div>

## 💬 What Can You Do With It?

Just talk to your AI like normal. V.I.S.O.R. works behind the scenes.

| You say... | V.I.S.O.R. does... |
|---|---|
| "Find the bug in the login flow" | Finds the 3–5 most relevant files instantly |
| "Explain how auth works" | Traces the full flow across files |
| "What breaks if I change this?" | Shows every dependent file |
| "Is my context still fresh?" | Checks for file changes since last read |

## 🚀 Features

### 🧠 Smart Code Search
- **Find code by meaning** — not just text matching
- **See how files connect** — interactive dependency graph
- **Check what breaks** — impact analysis before you refactor
- **Catch stale context** — drift detection warns when files change

### 🎯 Works With Any AI Agent
- Supports any AI that uses the **Model Context Protocol** (MCP)
- 17 specialized tools for code understanding
- **Custom skills** — create your own search strategies
- **HUD Focus** — watch your AI's attention on the 3D graph in real-time

### 📊 Live Stats
- How many files are indexed
- How many tokens your AI is using
- Warnings when files change under your AI

## 📦 Installation

### From Open VSX
Search for **"V.I.S.O.R. HUD"** in your editor's extension panel and install.

### MCP Server (Required)
The HUD visualizes data from the V.I.S.O.R. MCP server. Add this to your `.vscode/mcp.json`:

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

> **Prerequisite:** You need [`uv`](https://docs.astral.sh/uv/getting-started/installation/) installed. `uvx` handles everything else automatically.

## 🛠️ How to Use

1. **Open the HUD** — Click the V.I.S.O.R. icon in the activity bar, or run `Start V.I.S.O.R. HUD` from the command palette
2. **Talk to your AI** — Ask it to find code, explain architecture, or check for bugs
3. **Watch the graph** — See nodes light up as your AI explores your codebase

### Example Prompts to Try

```
"Find the code related to user authentication"
"What files depend on the database client?"
"Explain how the API routes are structured"
"Check if the files you read earlier have changed"
```

## ⚙️ Settings

| Setting | Default | What It Does |
|---------|---------|-------------|
| `visor.localProxyPort` | `4173` | Port for the local HUD dev server |
| `visor.remoteProxyPort` | `8080` | Port for remote SSH connections |
| `visor.enableLocalForwarding` | `true` | Auto-tunnel for Docker setups |
| `visor.serverPath` | `""` | Path to V.I.S.O.R. server (auto-detected if empty) |

## 🏗️ How It Works

```
visor-mcp (Python)          visor-hud (Extension)
┌─────────────────┐         ┌──────────────────┐
│  MCP Server     │◄────────│  WebGPU HUD      │
│  Code Parser    │         │  3D Graph View   │
│  Vector Search  │         │  Live Stats      │
│  Context Engine │         │  Focus Tracker   │
└─────────────────┘         └──────────────────┘
```

The MCP server reads and indexes your code. The HUD extension displays it as an interactive 3D graph. Your AI agent uses the server's tools to find relevant code, and the HUD shows you what it's looking at.

## 📄 License

MIT — [View on GitHub](https://github.com/dibun75/visor)
