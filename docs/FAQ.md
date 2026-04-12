# V.I.S.O.R. — Frequently Asked Questions

---

### What is V.I.S.O.R.?

V.I.S.O.R. (**V**isual **I**ntelligence **S**ystem for **O**rchestrated **R**easoning) is a local-first MCP server that gives AI coding agents precise, ranked codebase context instead of letting them blindly search through files.

---

### How is this different from just using embeddings?

Embeddings only measure semantic similarity — "does this code look like it's about authentication?" V.I.S.O.R. combines **5 signals**:

1. **Embedding similarity** — semantic relevance (like pure embedding search)
2. **Exact symbol match** — direct name matches in function/class names
3. **Co-location** — proximity to the top semantic hit
4. **Dependency graph** — architectural connections between files
5. **Recency** — recently modified files are more likely relevant to active bugs

Pure embedding search gives you semantically similar code. V.I.S.O.R. gives you **architecturally relevant** code.

---

### Does V.I.S.O.R. replace my AI agent?

No. V.I.S.O.R. is a **co-processor** for your AI agent. It doesn't generate code — it helps your existing AI (Antigravity, Claude, GPT-4, Gemini) make better decisions by giving it the right context. Think of it as giving your AI a map instead of making it wander.

---

### What IDEs are supported?

| IDE | Support Level | Method |
|-----|--------------|--------|
| Google Antigravity | ✅ Full (MCP + HUD) | MCP config + VSIX extension |
| VS Code | ✅ Full (MCP + HUD) | MCP config + VSIX extension |
| Cursor | ✅ MCP tools | MCP config |
| Claude Code | ✅ MCP tools | MCP config |

---

### What languages can V.I.S.O.R. index?

Currently: **Python**, **TypeScript**, **JavaScript**, and **TSX**.

V.I.S.O.R. uses Tree-sitter for AST parsing, so adding new languages is straightforward — see the "How to Extend" section in [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md).

---

### Is my code sent to any server?

**No.** V.I.S.O.R. is entirely local-first:
- Code is indexed into a SQLite database on your machine
- Embeddings are generated locally using `all-MiniLM-L6-v2`
- Communication with your IDE happens over stdio (no network ports)
- No data ever leaves your machine

---

### How much does it reduce token usage?

In typical codebases, V.I.S.O.R. achieves **70-85% token reduction** compared to naive full-file reads. The exact number depends on:
- Codebase size
- Query specificity
- Active skill strategy

Every response includes exact metrics:
```json
{
  "estimated_tokens_without": 11400,
  "estimated_tokens_with": 2180,
  "reduction_percent": 80.9
}
```

---

### What are Skills?

Skills are pre-loaded strategies that change how V.I.S.O.R. scores and retrieves context. Each skill can:
- Override the intent classifier (e.g., force BUG_FIX mode)
- Adjust individual scoring weights (e.g., boost dependency proximity)
- Suggest specific follow-up tools

V.I.S.O.R. ships with 4 built-in skills: `bug-fixer`, `architecture-explainer`, `refactor-assistant`, and `performance-optimizer`. You can create your own via the `add_custom_skill` MCP tool.

---

### Do I need the VS Code extension, or just the MCP server?

The **MCP server** is the core product — it provides all 16 tools to your AI agent. The VS Code extension is optional and adds:
- 3D WebGPU visualization of your codebase architecture
- Real-time telemetry (Agent Context Burn, Graph Scale, Drift Alerts)
- Skill management UI

You can use V.I.S.O.R. purely via MCP config + CLI without the extension.

---

### How fast is indexing?

- **First index**: 5-15 seconds for a medium codebase (~500 files)
- **Subsequent changes**: Incremental — only re-indexes files with changed SHA-256 hashes
- **Model download**: First boot downloads `all-MiniLM-L6-v2` (~80MB), cached locally after that
