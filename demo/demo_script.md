# Terminal demo script

Run these commands from a checkout. They are the same commands recorded by [`terminal_demo.tape`](./terminal_demo.tape).

```bash
uv run visor doctor
uv run visor index
uv run visor context "resolve local workspace project root"
```

`doctor` reports whether the local index is ready and which retrieval mode is active. `index` builds or refreshes the local AST index. `context` prints selected symbols, file paths, and the reason strings for that query.

A cold index can take longer than the short GIF target. For the recording, index once beforehand so the taped `visor index` refreshes an existing index. Keep the command output. Do not substitute a typed transcript.

Other local commands, when you want them:

```bash
uv run visor status
uv run visor trace src/visor/server.py src/visor/workspace.py
uv run visor drift
uv run visor context "resolve local workspace project root" --json
```

`visor fix` and `visor explain` are thin wrappers around `visor context` with the `bug-fixer` and `architecture-explainer` skills. Their human-readable output includes a per-result size estimate. That estimate compares candidate file text with returned snippets. It is not a published token-reduction measurement.

What this demo can show:

- The CLI runs without the HUD.
- The default retrieval mode is lexical.
- A context response names files, symbols, and reasons.

What it does not show:

- That the selected context is sufficient to change the code.
- A change in agent task success.
- A benchmark result. Those live in [`benchmarks/`](../benchmarks/).
