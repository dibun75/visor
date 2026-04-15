# V.I.S.O.R. — Troubleshooting

Common issues and their solutions.

---

## Database Issues

### "No relevant context found"

**Cause:** V.I.S.O.R. hasn't indexed your workspace yet.

**Fix:**
1. Run the MCP server to trigger the file watcher:
   ```bash
   uv run src/visor/server.py
   ```
2. Or use the IDE extension — it auto-starts the server and indexes on workspace open.

### Database location

V.I.S.O.R. stores its SQLite database in this priority order:

1. `$VISOR_DB_PATH` (if set)
2. `~/.cache/visor/visor_memory.db` (default)

To reset the database:
```bash
rm ~/.cache/visor/visor_memory.db
```

### "sqlite3.OperationalError: no such table"

**Cause:** Database was corrupted or partially migrated.

**Fix:** Delete and let V.I.S.O.R. recreate:
```bash
rm ~/.cache/visor/visor_memory.db
uv run src/visor/server.py
```

---

## Indexing Issues

### Files not being indexed

**Check these:**

1. **File extension**: V.I.S.O.R. indexes `.py`, `.ts`, `.tsx`, `.js`, `.jsx`, `.go`, `.rs`, `.java`, `.c`, `.h`, `.cpp`, `.cc`, `.cxx`, and `.hpp` files.
2. **Ignored paths**: Files in `node_modules/`, `.git/`, `__pycache__/`, and `dist/` are skipped.
3. **Hash cache**: If a file hasn't changed (same SHA-256), it won't re-index. Modify the file to trigger re-indexing.

### "Model download stuck"

**Cause:** First boot downloads `all-MiniLM-L6-v2` (~80MB) from HuggingFace.

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

```json
// ~/.gemini/antigravity/mcp_config.json
{
  "mcpServers": {
    "visor": {
      "command": "uv",
      "args": [
        "--directory", "/absolute/path/to/visor",
        "run", "-q", "/absolute/path/to/visor/src/visor/server.py"
      ],
      "env": {}
    }
  }
}
```

**Common mistakes:**
- Using relative paths (must be absolute)
- Missing `--directory` flag
- Not having `uv` on PATH

### "MCP server starts but no tools appear"

**Fix:** Restart your AI session after editing `mcp_config.json`. Most IDEs require a full restart or session reload.

---

## HUD / Extension Issues

### "WebGPU not supported"

**Cause:** Your browser/IDE webview doesn't support WebGPU.

**Fix:** The HUD falls back to WebGL. If neither works, ensure you're using a recent version of VS Code (1.80+).

### "acquireVsCodeApi() error"

**Cause:** VS Code only allows one call to `acquireVsCodeApi()` per webview lifecycle.

**Fix:** This is handled internally. If you see this error, try:
1. Close the V.I.S.O.R. sidebar
2. Reload the window: `Cmd+Shift+P` → "Developer: Reload Window"
3. Re-open V.I.S.O.R.
