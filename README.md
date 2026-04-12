# V.I.S.O.R.

> **AI is wasting 60% of your tokens reading the wrong code. V.I.S.O.R. fixes that.**

[![Version](https://img.shields.io/badge/version-0.8.0-blue)](https://github.com/dibun75/visor) [![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE) [![Python](https://img.shields.io/badge/python-3.10+-blue)](pyproject.toml) [![MCP](https://img.shields.io/badge/protocol-MCP-purple)](https://modelcontextprotocol.io)

**Visual Intelligence System for Orchestrated Reasoning**

V.I.S.O.R. is a **Skill-Orchestrated Context Intelligence Engine** — a local-first MCP server that indexes your codebase via Tree-sitter AST parsing, ranks code with a multi-signal scoring engine, and delivers surgical context to AI coding agents. It works with **Antigravity, VS Code, Cursor, and Claude Code**.

<div align="center">
  <img src="./docs/assets/hud_overview.png" alt="V.I.S.O.R HUD Dashboard" width="800"/>
</div>

---

## Why V.I.S.O.R.?

Every time your AI agent searches for context, it burns tokens reading irrelevant files. V.I.S.O.R. eliminates this waste:

| Without V.I.S.O.R. | With V.I.S.O.R. |
|---|---|
| Agent greps 20+ files blindly | Agent gets 3-5 precise snippets |
| ~12,000 tokens per context fetch | ~2,300 tokens (80% reduction) |
| No reasoning — just raw search | Every selection is explainable |
| Stale context → hallucinations | Drift detection prevents errors |

---

## ✨ Key Features

### 🧠 Context Intelligence Engine
The `build_context` tool is the core differentiator. It doesn't just search — it **reasons**:
- **Intent Classification** — Detects if you're debugging, refactoring, or exploring, and adjusts weights dynamically
- **5-Signal Scoring** — Combines embedding similarity, exact match, co-location, dependency proximity, and recency
- **Explainable Decisions** — Every node includes human-readable reasoning for why it was selected
- **Token Metrics** — Shows exact reduction percentage vs. naive full-file approach

### ⚡ Skill Execution Layer
Pre-loaded strategies that change how V.I.S.O.R. retrieves context:

| Skill | Intent | Behavior |
|---|---|---|
| `bug-fixer` | BUG_FIX | Boosts dependency chains + recently modified files |
| `architecture-explainer` | EXPLAIN | Heavy embedding similarity for broad understanding |
| `refactor-assistant` | REFACTOR | Wide dependency graph + exact symbol matching |
| `performance-optimizer` | BUG_FIX | Hotspot detection via extreme recency weighting |

Skills are defined as JSON strategies and stored in SQLite. Create your own via `add_custom_skill`.

### 🔍 Semantic AST Indexing
Powered by Tree-sitter (Python, TypeScript, JavaScript, TSX), V.I.S.O.R. parses your codebase into an AST. Symbols are embedded using `all-MiniLM-L6-v2` and stored in a local SQLite + `sqlite-vec` vector store.

### 📊 3D WebGPU Developer HUD
A real-time force-directed graph visualization of your codebase architecture, embedded directly in your IDE sidebar. Displays live telemetry: Agent Context Burn, Graph Scale, and Drift Alerts.

### ⚠️ Drift Detection
Dual-mode detection (SHA-256 hash comparison or file changelog timestamps) warns agents before they hallucinate from stale context.

---

## 🚀 Quick Start

### CLI (Immediate, no extension required)

```bash
git clone https://github.com/dibun75/visor.git
cd visor && uv sync

# Find context for a bug
uv run visor fix "login crash on null user"

# Explain a module
uv run visor explain "database client"

# General context query
uv run visor context "how is authentication handled"

# Trace architectural path
uv run visor trace src/auth.py src/db/client.py

# Check for drift
uv run visor drift
```

### IDE Extension

1. Download the latest `visor-hud-0.8.0.vsix` release.
2. Open VS Code / Antigravity → Extensions → `...` → **Install from VSIX...**
3. The extension bootstraps the Python MCP server via `uv run` and launches the HUD.

> **Note**: First launch downloads the `all-MiniLM-L6-v2` embedding model (~80MB). Subsequent starts are instant.

### MCP Configuration (Antigravity)

Add to `~/.gemini/antigravity/mcp_config.json`:

```json
"visor": {
  "command": "uv",
  "args": [
    "--directory", "<PATH_TO_VISOR>",
    "run", "-q", "<PATH_TO_VISOR>/src/visor/server.py"
  ],
  "env": {}
}
```

---

## 🛠️ MCP Tool Suite

V.I.S.O.R. exposes **16 MCP tools** across 5 categories. See [`docs/MCP_TOOLS.md`](./docs/MCP_TOOLS.md) for the full API reference.

### 🧠 Intelligence
| Tool | Description |
|------|-------------|
| `build_context(query, skill?)` | Ranked context with scoring, reasoning, metrics, and prompt export |

### 🔍 Search
| Tool | Description |
|------|-------------|
| `search_codebase(query)` | Semantic vector search across AST nodes |
| `get_symbol_context(symbol)` | Find all definitions with file + line range |
| `get_file_context(path)` | Full AST symbol listing for a file |

### 🗺️ Graph Analysis
| Tool | Description |
|------|-------------|
| `get_dependency_chain(symbol)` | Transitive import chain (BFS depth 5) |
| `impact_analysis(file_path)` | Downstream blast radius |
| `trace_route(source, target)` | Shortest path between files |
| `dead_code_detection()` | Files with zero incoming edges |

### ⚠️ Drift Detection
| Tool | Description |
|------|-------------|
| `get_drift_report(files, loaded_at, hashes?)` | Hash or timestamp-based drift detection |

### 🧩 Memory & Skills
| Tool | Description |
|------|-------------|
| `store_memory(role, content)` | Persist conversation with embedding |
| `add_custom_skill(name, desc, content, strategy?)` | Create a skill with optional JSON strategy |
| `list_custom_skills()` | List all skills with strategies |
| `delete_custom_skill(id)` | Remove a skill |

---

## 📦 Example Output

```bash
$ uv run visor fix "authentication crash"
```

```
============================================================
  V.I.S.O.R. Context Intelligence Engine
============================================================
  Query:  authentication crash
  Intent: BUG_FIX
  Skill:  bug-fixer
────────────────────────────────────────────────────────────
  Tokens without V.I.S.O.R.: 11,400
  Tokens with V.I.S.O.R.:    2,180
  Reduction:                  80.9%
────────────────────────────────────────────────────────────
  Selected 4 nodes (truncated=False):

  [2.8500]  src/auth/jwt.py:verify_token
            → Matched query token in symbol name
            → Co-located in same file as top semantic hit
            → Recently modified file (boosted)

  [2.1200]  src/auth/middleware.py:auth_guard
            → Reachable via dependency chain
            → Semantic similarity (score: 0.375)

============================================================
```

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) | System design, data flow, DB schema |
| [`docs/MCP_TOOLS.md`](./docs/MCP_TOOLS.md) | Complete MCP tool API reference |
| [`CHANGELOG.md`](./CHANGELOG.md) | Release history |

---

## 🤝 Contributing

```bash
git clone https://github.com/dibun75/visor.git
cd visor && uv sync

# Run the MCP server
uv run src/visor/server.py

# Run tests
uv run pytest tests/

# Build the HUD
cd src/visor/hud && npm install && npm run build

# Build the extension
cd src/visor/extension && npm install && npm run compile
npx @vscode/vsce package -o visor-hud-0.8.0.vsix
```

---

## 🌐 Compatibility

| IDE | Support | Method |
|------|---------|--------|
| Google Antigravity | ✅ Full | MCP config + Extension |
| VS Code | ✅ Full | MCP config + Extension |
| Cursor | ✅ MCP tools | MCP config |
| Claude Code | ✅ MCP tools | MCP config |

---

## License

MIT © [Arunav Mandal](https://github.com/dibun75)
