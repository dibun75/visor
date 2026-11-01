# V.I.S.O.R. — Frequently Asked Questions

---

### What is V.I.S.O.R.?

V.I.S.O.R. (**V**isual **I**ntelligence **S**ystem for **O**rchestrated **R**easoning) is a local-first context engine for Codex, Claude Code, and other terminal coding agents. It builds an AST-backed index and dependency graph, then returns focused context with the files, symbols, and reasons for each selection. It complements ordinary repository search.

---

### How does retrieval work?

Lexical retrieval is the default. It searches symbol names and docstrings with SQLite FTS5 and does not download a model.

The context scorer can combine the retrieval hit with symbol-name overlap, same-file proximity, dependency distance, and file recency. Semantic similarity is used when retrieval mode is `semantic`. That mode is optional and requires the `semantic` extra.

---

### Does V.I.S.O.R. replace my AI agent?

No. V.I.S.O.R. does not generate code. Codex, Claude Code, and other configured clients still inspect the repository and apply edits. The Agent Skill tells the agent to treat V.I.S.O.R. results as leads and verify them.

---

### What IDEs are supported?

| Client | Method |
|-----|--------|
| Codex CLI | `codex mcp add visor -- uvx visor-mcp` |
| Claude Code | `claude mcp add visor -- uvx visor-mcp` |
| Cursor | `~/.cursor/mcp.json` |
| Claude Desktop | `claude_desktop_config.json` |
| VS Code | `.vscode/mcp.json`, optional HUD extension |
| Antigravity | The VS Code MCP file above, optional HUD extension |
| Terminal | `visor doctor`, `visor index`, `visor context` |

---

### What languages can V.I.S.O.R. index?

Nine languages: **Python**, **TypeScript**, **JavaScript**, **Go**, **Rust**, **Java**, **C**, **C++**, and **C#**. `.tsx` uses the TypeScript parser's TSX variant. It is not a separate language.

V.I.S.O.R. uses Tree-sitter for AST parsing, so adding new languages is straightforward (~15 lines of code) — see [CONTRIBUTING.md](../CONTRIBUTING.md#how-to-add-a-new-language-most-common-contribution).

---

### Is my code sent to any server?

The index and graph stay in local SQLite databases under `~/.visor/`. Lexical retrieval works offline. Semantic mode is optional and may download `all-MiniLM-L6-v2` on first use.

V.I.S.O.R. does not upload the repository to a hosted V.I.S.O.R. service. The MCP server uses stdio. Snippets you pass to Codex, Claude Code, or another configured agent are subject to that provider's policies. The optional HUD can open a local dev-server or SSH forward port; that is separate from the MCP server.

---

### What do the token fields mean?

`build_context` estimates the size of the full candidate files and the size of the snippets it returns, then stores both on that response. The fields are `estimated_tokens_without`, `estimated_tokens_with`, and `reduction_percent`. They describe one response. They are not a measurement of agent token use, and this repository does not publish a universal reduction figure.

---

### What are Skills?

Skills are pre-loaded strategies that change how V.I.S.O.R. scores and retrieves context. Each skill can:
- Override the intent classifier (e.g., force BUG_FIX mode)
- Adjust individual scoring weights (e.g., boost dependency proximity)
- Suggest specific follow-up tools

V.I.S.O.R. ships with 4 built-in skills: `bug-fixer`, `architecture-explainer`, `refactor-assistant`, and `performance-optimizer`. You can create your own via the `add_custom_skill` MCP tool.

---

### Do I need the VS Code extension, or just the MCP server?

The MCP server is the core. It registers 17 tools, including `health_check`. `get_visor_skill` is an MCP prompt. The VS Code extension is optional and adds:

- a WebGPU view of the indexed graph
- telemetry from `get_telemetry` (node count, local payload-byte counter, drift)
- agent focus when `set_hud_focus` has been called

The CLI and MCP server work without the extension.

---

### How does indexing behave?

`visor index` walks supported source files and skips unchanged SHA-256 hashes on later runs. This repository does not publish a timing for that walk.

Lexical indexing does not download a model. The optional semantic extra downloads `all-MiniLM-L6-v2` when that mode is first used.
