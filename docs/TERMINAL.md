# Terminal-first workflow

V.I.S.O.R. works without an IDE, browser, network connection, or model
download. Run commands from a project directory, or pass `--workspace PATH`.

```bash
visor doctor
visor index
visor status
visor context "where is workspace resolution handled?" --json
visor trace /absolute/source.py /absolute/target.py
visor map --open
```

`doctor` is read-only and reports the resolved project, index health, and
whether optional semantic dependencies are available. `index` is explicit: no
terminal command starts a watcher or installs software.

## Shareable map

```bash
visor map            # writes visor-map.html and VISOR_REPORT.md
visor map --open     # and opens the map in your browser
```

`visor map` exports the indexed import graph as one self-contained HTML file:
the renderer and data are inlined, it makes no network requests, and it works
from disk, as a CI artifact, or on any static host. Nodes are files colored by
directory cluster and sized by how many files import them. Click a file to see
what it imports and what imports it; search by file or symbol name; save the
current view as a PNG. Links of the form `visor-map.html#file=src/app.py` open
with that file selected.

`VISOR_REPORT.md` lists hub files (most imported), likely entry points, the
most-depended-on symbols (by distinct caller files), and import cycles.

Both files contain workspace-relative paths, symbol names, and counts only. No
source code, docstrings, or absolute paths are exported. If the index is not
ready, `visor map` indexes the workspace first.

| Option | Effect |
| --- | --- |
| `--out PATH` | HTML path (default `visor-map.html`) |
| `--report PATH` | Report path (default `VISOR_REPORT.md`) |
| `--no-report` | Skip the Markdown report |
| `--max-files N` | Draw the N most connected files (default 600, `0` for all) |
| `--open` | Open the HTML in the default browser |
| `--json` | Print the map data as JSON and write no files |

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
