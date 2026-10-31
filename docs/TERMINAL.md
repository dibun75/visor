# Terminal-first workflow

V.I.S.O.R. works without an IDE, browser, network connection, or model
download. Run commands from a project directory, or pass `--workspace PATH`.

```bash
visor doctor
visor index
visor status
visor context "where is workspace resolution handled?" --json
visor trace /absolute/source.py /absolute/target.py
```

`doctor` is read-only and reports the resolved project, index health, and
whether optional semantic dependencies are available. `index` is explicit: no
terminal command starts a watcher or installs software.

## Retrieval modes

Lexical retrieval is the default. It indexes symbol names and docstrings with
SQLite FTS5, has no model dependency, and is suitable for offline and headless
use.

```bash
visor --retrieval-mode lexical index
```

Semantic retrieval remains available as an opt-in for installations that want
it. Install the optional extra first, then rebuild the index in that mode:

```bash
pip install 'visor-mcp[semantic]'
visor --retrieval-mode semantic index
```

Each index is tied to its retrieval mode. Switching modes requires a rebuild;
`visor status` reports this as not ready until the rebuild completes.

## Automation-safe behavior

The CLI validates that a workspace is a recognized project before opening its
database. Use `--workspace` or `WORKSPACE_ROOT` for an explicit location.
Malformed mode values and missing semantic dependencies produce actionable
errors; V.I.S.O.R. never downloads a model or modifies an IDE configuration as
part of indexing or retrieval.
