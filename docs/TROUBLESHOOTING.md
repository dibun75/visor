# V.I.S.O.R. — Troubleshooting

Common issues and their solutions.

---

## Database Issues

### "No relevant context found"

**Cause:** V.I.S.O.R. hasn't indexed your workspace yet.

**Fix:**
1. Index the intended project explicitly:
   ```bash
   visor index --workspace /path/to/project
   ```
2. Confirm the selected workspace and retrieval mode with `visor doctor --workspace /path/to/project`.

### Feedback is changing a later result

**Cause:** A previous `useful`, `irrelevant`, or `missing` verdict still matches the query. Feedback applies only in the same workspace, only when token overlap is at least 0.6, and only when the intent matches. Its effect halves every 30 days.

**Fix:** Inspect it with `visor feedback list --json`. Remove one record with `visor feedback delete <id>`, or remove every record for this workspace with `visor feedback clear --yes`. This does not delete the code index.

### Database location

V.I.S.O.R. uses a hub-and-spoke architecture with databases stored in `~/.visor/`:

- **Hub**: `~/.visor/hub.db` — global telemetry, custom skills, workspace registry
- **Spoke**: `~/.visor/workspaces/{hash}/graph.db` — per-workspace code nodes, edges, embeddings

First run `visor doctor --workspace /path/to/project` and note its exact `database` path. Close V.I.S.O.R., back up that file, and delete only that one `graph.db`; the next index recreates it. Do not use a wildcard, because it would reset every indexed workspace.

To reset all local V.I.S.O.R. state, first close V.I.S.O.R. and move `~/.visor` to a backup location. This removes every workspace index, telemetry row, skill, memory, and feedback record.

### "sqlite3.OperationalError: no such table"

**Cause:** Database was corrupted or partially migrated.

**Fix:** Back up and remove only the exact affected database reported by `visor doctor`, then run `visor index --workspace /path/to/project`. If the hub itself is corrupt, move `~/.visor/hub.db` aside rather than deleting the whole directory.

---

## Indexing Issues

### Files not being indexed

**Check these:**

1. **File extension**: V.I.S.O.R. indexes `.py`, `.ts`, `.tsx`, `.js`, `.jsx`, `.go`, `.rs`, `.java`, `.c`, `.h`, `.cpp`, `.cc`, `.cxx`, `.hpp`, and `.cs` files.
2. **Ignored paths**: Files in `node_modules/`, `.git/`, `__pycache__/`, and `dist/` are skipped.
3. **Hash cache**: If a file hasn't changed (same SHA-256), it won't re-index. Modify the file to trigger re-indexing.

### "Model download stuck"

**Cause:** Semantic mode, or a tool that calls the embedder such as `store_memory`, downloads `all-MiniLM-L6-v2` from Hugging Face on first use. Lexical `visor index` and `visor context` do not.

**Fix:**
- Check network connectivity
- Try a manual download:
  ```python
  from sentence_transformers import SentenceTransformer
  SentenceTransformer("all-MiniLM-L6-v2")
  ```
- Set `SENTENCE_TRANSFORMERS_HOME` to control cache location

---

## CLI Errors

### "ModuleNotFoundError: No module named 'visor'"

**Cause:** The package isn't installed in the current environment.

**Fix:**
```bash
cd /path/to/visor
uv sync
uv run visor --help
```

### "visor: command not found"

**Cause:** The CLI is only available via `uv run visor` unless you install it globally.

**Fix:**
```bash
# Option A: Install from PyPI (recommended)
pip install visor-mcp
visor fix "login crash"

# Option B: Use uv run (development)
cd /path/to/visor
uv run visor fix "login crash"
```

### "--json flag not working with trace/drift"

**Note:** The `--json` flag is currently only available for `context`, `fix`, and `explain` commands. `trace` always outputs JSON. `drift` outputs human-readable format.

---

## MCP Connection Issues

### "Agent can't see V.I.S.O.R. tools"

**Check your MCP config:**

The recommended config uses `uvx` which handles everything automatically:

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

Put this in `.vscode/mcp.json` (VS Code / Antigravity) or `~/.cursor/mcp.json` (Cursor).

**Common mistakes:**
- Not having `uv` installed — get it from [astral.sh/uv](https://docs.astral.sh/uv/getting-started/installation/)
- Using old `uv --directory ... run` pattern instead of `uvx visor-mcp`
- Forgetting to restart the IDE after editing the config

### "V.I.S.O.R. is indexing the wrong directory"

**Cause:** This was a known bug in versions before 1.0.2.

**Fix:** Update to the latest version. V.I.S.O.R. now resolves MCP roots when the client supplies them, then falls back to `--workspace`, `WORKSPACE_ROOT`, or a recognized local project.

```bash
pip install --upgrade visor-mcp
```

### "MCP server starts but no tools appear"

**Fix:** Restart your AI session after editing the MCP config. Most IDEs require a full restart or session reload.

---

## HUD / Extension Issues

### "3D HUD is blank"

**Cause:** The VS Code webview could not create a WebGL context, or hardware acceleration is disabled.

**Fix:** Reload the VS Code window and ensure hardware acceleration is enabled. V.I.S.O.R. uses Three.js through React Three Fiber; it does not require WebGPU.

### "acquireVsCodeApi() error"

**Cause:** VS Code only allows one call to `acquireVsCodeApi()` per webview lifecycle.

**Fix:** This is handled internally. If you see this error, try:
1. Close the V.I.S.O.R. sidebar
2. Reload the window: `Cmd+Shift+P` → "Developer: Reload Window"
3. Re-open V.I.S.O.R.
