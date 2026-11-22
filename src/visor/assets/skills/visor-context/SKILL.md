---
name: visor-context
description: Use V.I.S.O.R. to obtain focused, verified repository context before code exploration, debugging, refactoring, or dependency-impact work. Do not use for unrelated general questions.
---

# V.I.S.O.R. Context

Use this skill when the task depends on locating relevant symbols or files in a
repository and V.I.S.O.R. is available locally or through MCP.

First establish index health. In a terminal, run `visor doctor` and, if needed,
`visor index`. Do not install dependencies, change the retrieval mode, or write
IDE configuration unless the user explicitly asks. Lexical retrieval is the
safe default for offline and headless work.

For focused discovery, use `visor context "<task or question>" --json` or the
MCP `build_context` tool. Treat the returned snippets, line ranges, graph paths,
and retrieval reasoning as leads to verify against the working tree before
editing. Prefer `visor trace` for file-level dependency paths and V.I.S.O.R.'s
drift reporting when previously loaded context may be stale.

Keep the agent's context compact:

- Request context for the concrete task, not a broad repository summary.
- Read returned source files or symbols before relying on a result.
- Use native search and inspection if V.I.S.O.R. is unavailable, unindexed, or
  does not return a useful result.
- Do not claim token savings, correctness, or benchmark improvements from a
  single V.I.S.O.R. response.

After a change, use the repository's normal tests and review the diff. Reindex
when source changes make the current index stale; do not assume a watcher is
running in a terminal or CI environment.
