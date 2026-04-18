# V.I.S.O.R.

> **Your AI coding assistant wastes time reading the wrong files. V.I.S.O.R. fixes that.**

[![CI](https://github.com/dibun75/visor/actions/workflows/ci.yml/badge.svg)](https://github.com/dibun75/visor/actions/workflows/ci.yml) [![PyPI](https://img.shields.io/pypi/v/visor-mcp)](https://pypi.org/project/visor-mcp/) [![Open VSX](https://img.shields.io/open-vsx/v/dibun75/visor-hud)](https://open-vsx.org/extension/dibun75/visor-hud) [![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE) [![Python](https://img.shields.io/badge/python-3.10+-blue)](pyproject.toml)

**Visual Intelligence System for Orchestrated Reasoning**

V.I.S.O.R. is a **smart helper for your AI coding assistant**. It reads your code, understands how files are connected, and gives your AI exactly the right context — so it spends less time searching and more time solving.

It works with **Antigravity, VS Code, Cursor, Claude Code, and Windsurf**.

<div align="center">
  <img src="./docs/assets/hud_overview.png" alt="V.I.S.O.R HUD — 3D codebase visualization in your IDE" width="800"/>
</div>

<div align="center">
  <h3>🎬 See it in action</h3>
</div>

<div align="center">
  <img src="./docs/assets/demo.gif" alt="V.I.S.O.R HUD in action" width="800"/>
</div>

---

## 💬 What Can You Do With It?

Just talk to your AI agent like normal. V.I.S.O.R. works behind the scenes to find the right code automatically.

### Find a bug
> "Find the code related to the login crash"

Without V.I.S.O.R., your AI reads 20+ files blindly. With V.I.S.O.R., it gets the 3–5 most relevant files instantly.

### Understand your code
> "Explain how authentication works in this project"

V.I.S.O.R. traces the full auth flow across files — showing your AI exactly which functions call which, and in what order.

### Refactor safely
> "What files would break if I change the database client?"

V.I.S.O.R. runs an **impact analysis** and shows every file that depends on the one you're changing.

### Check for stale context
> "Are the files you read earlier still up to date?"

V.I.S.O.R. checks file hashes and warns your AI if something changed since it last looked.

---

## 🚀 Install (2 minutes)

### Step 1: Add V.I.S.O.R. to your IDE

Pick your IDE below and add the config. That's it — V.I.S.O.R. installs itself automatically the first time it runs.

<details>
<summary><b>Claude Code</b> (one command)</summary>

```bash
claude mcp add visor -- uvx visor-mcp
```

Done. Claude Code handles everything.

</details>

<details>
<summary><b>Cursor</b> (~/.cursor/mcp.json)</summary>

```json
{
  "mcpServers": {
    "visor": {
      "command": "uvx",
      "args": ["visor-mcp"]
    }
  }
}
```

Or per-project: create `.cursor/mcp.json` in your repo root.

</details>

<details>
<summary><b>VS Code / Antigravity</b> (.vscode/mcp.json)</summary>

Create `.vscode/mcp.json` in your project root:

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

Or use Command Palette → `MCP: Add Server`.

For the full 3D HUD experience, also install the [V.I.S.O.R. HUD extension](https://open-vsx.org/extension/dibun75/visor-hud).

</details>

<details>
<summary><b>Claude Desktop</b> (claude_desktop_config.json)</summary>

macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
Linux: `~/.config/claude/claude_desktop_config.json`
Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "visor": {
      "command": "uvx",
      "args": ["visor-mcp"]
    }
  }
}
```

</details>

<details>
<summary><b>Windsurf</b></summary>

Open Plugins sidebar → Manage plugins → View raw config, then add:

```json
{
  "mcpServers": {
    "visor": {
      "command": "uvx",
      "args": ["visor-mcp"]
    }
  }
}
```

</details>

> **Prerequisite:** You need [`uv`](https://docs.astral.sh/uv/getting-started/installation/) installed. `uvx` (included with `uv`) handles virtual environments and dependencies automatically — no manual setup needed.

### Step 2 (Optional): Install the 3D HUD Extension

Search for **"V.I.S.O.R. HUD"** in your editor's extension panel, or install from [Open VSX](https://open-vsx.org/extension/dibun75/visor-hud). This gives you a live 3D visualization of your codebase graph right in the sidebar.

---

## 🤔 Why V.I.S.O.R.?

Every time your AI agent searches for context, it wastes time reading irrelevant files. V.I.S.O.R. eliminates that waste:

| Without V.I.S.O.R. | With V.I.S.O.R. |
|---|---|
| AI reads 20+ files blindly | AI gets 3–5 precise code snippets |
| ~12,000 tokens per search | ~2,300 tokens (80% reduction) |
| No reasoning — raw text search | Every selection has an explanation |
| Stale context → wrong answers | Drift detection prevents mistakes |

---

## ✨ Key Features

### 🧠 Smart Context Engine
The heart of V.I.S.O.R. When your AI asks "find code related to X", it doesn't just search by text — it **thinks**:

- **Understands your question** — Detects if you're fixing a bug, exploring, or refactoring, and adjusts accordingly
- **Scores code 5 different ways** — Combines meaning similarity, name matching, file proximity, code connections, and how recently the file was changed
- **Explains its choices** — Every code snippet includes a plain-English reason for why it was picked
- **Saves tokens** — Shows you exactly how many tokens it saved vs. a naive approach

### ⚡ Built-in Skills
Pre-built strategies that change how V.I.S.O.R. finds code. Think of them as "modes":

| Skill | What it does |
|---|---|
| `bug-fixer` | Focuses on recently changed files and dependency chains |
| `architecture-explainer` | Casts a wide net to help explain how things connect |
| `refactor-assistant` | Traces all dependencies so you know what might break |
| `performance-optimizer` | Finds hotspots by prioritizing recently modified code |

You can also create your own custom skills.

### 🔍 Code Understanding
V.I.S.O.R. reads your code structure (classes, functions, imports) in **9 languages**:

| Language | File Types |
|----------|-----------|
| Python | `.py` |
| TypeScript | `.ts`, `.tsx` |
| JavaScript | `.js`, `.jsx` |
| Go | `.go` |
| Rust | `.rs` |
| Java | `.java` |
| C | `.c`, `.h` |
| C++ | `.cpp`, `.cc`, `.cxx`, `.hpp` |

> **Want more?** Adding a new language is ~15 lines of code. See [CONTRIBUTING.md](./CONTRIBUTING.md#how-to-add-a-new-language-most-common-contribution).

### 📊 3D HUD (VS Code / Antigravity)
A real-time interactive graph of your codebase — right in your editor sidebar. Shows:
- Your code as connected nodes you can explore
- Live stats: how many tokens your AI is using, how many files are indexed
- Drift alerts when files change under your AI

### ⚠️ Drift Detection
Knows when your AI is looking at outdated code. Compares file hashes and warns before your AI makes decisions on stale information.

---

## 📦 Example: Finding a Bug

```bash
$ visor fix "authentication crash"
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

  [2.85]  src/auth/jwt.py:verify_token
          → Matched query token in symbol name
          → Co-located in same file as top semantic hit
          → Recently modified file (boosted)

  [2.12]  src/auth/middleware.py:auth_guard
          → Reachable via dependency chain
          → Semantic similarity (score: 0.375)

============================================================
```

**What happened:** Instead of your AI reading every file in the project, V.I.S.O.R. found the 4 most relevant functions and saved 80% of the tokens.

---

## 🛠️ CLI Commands

You can also use V.I.S.O.R. from the terminal:

```bash
visor fix "login crash on null user"         # Find bug-related code
visor explain "database client"              # Understand how a module works
visor context "how is auth handled"          # General code search
visor trace src/auth.py src/db/client.py     # Show how two files are connected
visor drift                                  # Check for changed files
```

---

## 🛠️ MCP Tools (for AI Agents)

V.I.S.O.R. gives your AI agent **17 tools** across 5 categories. Your AI uses these automatically — you don't need to call them manually.

| Category | Tools |
|----------|-------|
| 🧠 **Intelligence** | `build_context` — the main tool that finds and ranks relevant code |
| 🔍 **Search** | `search_codebase`, `get_symbol_context`, `get_file_context` |
| 🗺️ **Graph** | `get_dependency_chain`, `impact_analysis`, `trace_route`, `dead_code_detection` |
| ⚠️ **Drift** | `get_drift_report` |
| 🧩 **Memory & Skills** | `store_memory`, `add_custom_skill`, `list_custom_skills`, `delete_custom_skill` |
| 📊 **HUD** | `get_architecture_map`, `get_telemetry`, `set_hud_focus` |

See [`docs/MCP_TOOLS.md`](./docs/MCP_TOOLS.md) for the full API reference.

---

## 📚 Documentation

| Document | What's Inside |
|----------|--------------|
| [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) | How V.I.S.O.R. works under the hood |
| [`docs/MCP_TOOLS.md`](./docs/MCP_TOOLS.md) | Complete reference for all 17 tools |
| [`docs/FAQ.md`](./docs/FAQ.md) | Common questions answered |
| [`docs/TROUBLESHOOTING.md`](./docs/TROUBLESHOOTING.md) | Fixing common problems |
| [`CONTRIBUTING.md`](./CONTRIBUTING.md) | How to add languages, tools, and skills |
| [`CHANGELOG.md`](./CHANGELOG.md) | What changed in each version |

---

## 🤝 Contributing

V.I.S.O.R. welcomes contributions! The easiest way to start is by [adding a new language](./CONTRIBUTING.md#how-to-add-a-new-language-most-common-contribution) — it's ~15 lines and a great first issue.

```bash
git clone https://github.com/dibun75/visor.git
cd visor && uv sync --dev
uv run pytest tests/ -v
```

See [CONTRIBUTING.md](./CONTRIBUTING.md) for the full guide.

---

## 🌐 Works With

| IDE | Support | How to Set Up |
|------|---------|--------------|
| Claude Code | ✅ Full | `claude mcp add visor -- uvx visor-mcp` |
| Cursor | ✅ Full | `~/.cursor/mcp.json` |
| Claude Desktop | ✅ Full | `claude_desktop_config.json` |
| VS Code | ✅ Full | `.vscode/mcp.json` + [HUD Extension](https://open-vsx.org/extension/dibun75/visor-hud) |
| Antigravity | ✅ Full | `.vscode/mcp.json` + [HUD Extension](https://open-vsx.org/extension/dibun75/visor-hud) |
| Windsurf | ✅ Full | Plugin raw config |

---

## License

MIT © [Arunav Mandal](https://github.com/dibun75)
