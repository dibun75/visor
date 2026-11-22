"""Shareable repository map: a self-contained HTML graph and a Markdown report.

``visor map`` reads the local index (no network, no IDE) and writes:

* ``visor-map.html`` — one file with the data and the renderer inlined, so it
  can be opened from disk, attached to an issue, or hosted as a static page.
* ``VISOR_REPORT.md`` — hub files, likely entry points, the most-depended-on
  symbols, and import cycles.

Only workspace-relative paths, symbol names, and counts are exported. Source
code, docstrings, and absolute paths never leave the index.
"""

from __future__ import annotations

import json
import os
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from importlib import resources
from pathlib import PurePosixPath
from typing import Any

import networkx as nx

DEFAULT_MAX_FILES = 600
MAX_CLUSTERS = 14
DATA_PLACEHOLDER = "/*__VISOR_MAP_DATA__*/"

_NOISE_PARTS = {
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
    ".git",
    ".agent",
}

_LANGUAGES = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".c": "C",
    ".h": "C",
    ".cc": "C++",
    ".cpp": "C++",
    ".cxx": "C++",
    ".hpp": "C++",
    ".hh": "C++",
    ".cs": "C#",
}

# File names that usually start a program. Checked case-insensitively.
_ENTRY_NAMES = {
    "__main__.py",
    "main.py",
    "cli.py",
    "server.py",
    "app.py",
    "manage.py",
    "wsgi.py",
    "asgi.py",
    "main.go",
    "main.rs",
    "lib.rs",
    "main.c",
    "main.cpp",
    "main.cc",
    "program.cs",
    "main.java",
    "application.java",
    "index.js",
    "index.ts",
    "index.tsx",
    "main.js",
    "main.ts",
    "main.tsx",
    "server.js",
    "server.ts",
    "app.js",
    "app.ts",
    "app.tsx",
    "cli.js",
    "cli.ts",
}


def _relative(path: str, root: str) -> str | None:
    """Return a POSIX workspace-relative path, or None if outside the root."""
    try:
        rel = os.path.relpath(path, root)
    except ValueError:  # different drive on Windows
        return None
    rel = rel.replace(os.sep, "/")
    if rel == "." or rel.startswith("../") or rel == "..":
        return None
    if any(part in _NOISE_PARTS for part in rel.split("/")):
        return None
    return rel


def _choose_clusters(rel_paths: list[str]) -> dict[str, str]:
    """Group files by directory, splitting the biggest groups while readable.

    Starts from top-level directories and repeatedly splits the largest
    cluster into its subdirectories, as long as the total stays at or under
    ``MAX_CLUSTERS``. Files directly inside a split directory keep its name.
    """
    dirs = {p: PurePosixPath(p).parent.parts for p in rel_paths}
    depth = {p: min(1, len(parts)) for p, parts in dirs.items()}

    def key(p: str) -> str:
        return "/".join(dirs[p][: depth[p]]) or "(root)"

    blocked: set[str] = set()
    while True:
        groups: dict[str, list[str]] = defaultdict(list)
        for p in rel_paths:
            groups[key(p)].append(p)
        candidates = [
            (len(members), name)
            for name, members in groups.items()
            if name not in blocked
            and len(members) > 1
            and any(len(dirs[p]) > depth[p] for p in members)
        ]
        if not candidates:
            break
        _, name = max(candidates, key=lambda c: (c[0], c[1]))
        members = groups[name]
        children = {
            "/".join(dirs[p][: depth[p] + 1]) if len(dirs[p]) > depth[p] else name
            for p in members
        }
        if len(groups) - 1 + len(children) > MAX_CLUSTERS:
            blocked.add(name)
            continue
        for p in members:
            if len(dirs[p]) > depth[p]:
                depth[p] += 1
    return {p: key(p) for p in rel_paths}


def collect_graph(
    conn: sqlite3.Connection,
    workspace_root: str,
    max_files: int | None = DEFAULT_MAX_FILES,
) -> dict[str, Any]:
    """Build a file-level graph payload from an indexed spoke database."""
    root = os.path.realpath(workspace_root)
    rows = conn.execute(
        """
        SELECT file_path,
               COUNT(*),
               SUM(CASE WHEN node_type = 'class' THEN 1 ELSE 0 END),
               SUM(CASE WHEN node_type = 'function' THEN 1 ELSE 0 END)
        FROM code_nodes
        GROUP BY file_path
        """
    ).fetchall()

    files: dict[str, dict[str, Any]] = {}
    for abs_path, total, classes, functions in rows:
        rel = _relative(abs_path, root)
        if rel is None:
            continue
        files[abs_path] = {
            "path": rel,
            "classes": int(classes or 0),
            "functions": int(functions or 0),
            "symbols": int(classes or 0) + int(functions or 0),
        }

    imports: Counter[tuple[str, str]] = Counter()
    for src, dst in conn.execute(
        "SELECT from_node, to_node FROM edges "
        "WHERE relation_type = 'IMPORTS' AND resolution = 'internal'"
    ):
        if src in files and dst in files and src != dst:
            imports[(src, dst)] += 1

    calls: Counter[tuple[str, str]] = Counter()
    for src, dst in conn.execute(
        "SELECT from_node, to_node FROM edges "
        "WHERE relation_type = 'CALLS' AND resolution = 'internal'"
    ):
        if src in files and dst in files and src != dst:
            calls[(src, dst)] += 1

    graph = nx.DiGraph()
    graph.add_nodes_from(files)
    graph.add_edges_from(imports)

    in_deg = dict(graph.in_degree())
    out_deg = dict(graph.out_degree())
    total_files = len(files)

    ranked = sorted(
        files,
        key=lambda f: (
            -(in_deg[f] + out_deg[f]),
            -files[f]["symbols"],
            files[f]["path"],
        ),
    )
    if max_files is not None and max_files > 0:
        ranked = ranked[:max_files]
    kept = set(ranked)
    ordered = sorted(kept, key=lambda f: files[f]["path"])

    clusters = _choose_clusters([files[f]["path"] for f in ordered])
    ids = {f: i for i, f in enumerate(ordered)}

    top_symbols: dict[str, list[dict[str, str]]] = defaultdict(list)
    for abs_path, name, node_type in conn.execute(
        """
        SELECT file_path, name, node_type FROM code_nodes
        WHERE node_type IN ('class', 'function')
        ORDER BY file_path, CASE node_type WHEN 'class' THEN 0 ELSE 1 END,
                 start_line, name
        """
    ):
        bucket = top_symbols[abs_path]
        if abs_path in kept and len(bucket) < 12 and not name.startswith("func_"):
            bucket.append({"name": name, "type": node_type})

    nodes = []
    for f in ordered:
        info = files[f]
        rel = info["path"]
        nodes.append(
            {
                "id": ids[f],
                "path": rel,
                "name": PurePosixPath(rel).name,
                "cluster": clusters[rel],
                "language": _LANGUAGES.get(PurePosixPath(rel).suffix.lower(), "Other"),
                "classes": info["classes"],
                "functions": info["functions"],
                "symbols": info["symbols"],
                "imported_by": in_deg[f],
                "imports": out_deg[f],
                "top_symbols": top_symbols.get(f, []),
            }
        )

    edges = [
        {"source": ids[s], "target": ids[t], "type": "IMPORTS", "weight": w}
        for (s, t), w in sorted(
            imports.items(),
            key=lambda kv: (ids.get(kv[0][0], -1), ids.get(kv[0][1], -1)),
        )
        if s in kept and t in kept
    ]
    edges += [
        {"source": ids[s], "target": ids[t], "type": "CALLS", "weight": w}
        for (s, t), w in sorted(
            calls.items(), key=lambda kv: (ids.get(kv[0][0], -1), ids.get(kv[0][1], -1))
        )
        if s in kept and t in kept and (s, t) not in imports
    ]

    from visor import __version__

    return {
        "project": os.path.basename(root) or root,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "visor_version": __version__,
        "stats": {
            "files": total_files,
            "files_shown": len(nodes),
            "symbols": sum(info["symbols"] for info in files.values()),
            "import_links": len(imports),
            "call_links": len(calls),
            "clusters": len(set(clusters.values())),
            "languages": dict(Counter(n["language"] for n in nodes).most_common()),
        },
        "nodes": nodes,
        "edges": edges,
        "_graph": graph,  # removed before serialisation
        "_files": files,
    }


def analyze(
    payload: dict[str, Any], conn: sqlite3.Connection, limit: int = 10
) -> dict[str, Any]:
    """Derive hubs, entry points, depended-on symbols, and cycles."""
    graph: nx.DiGraph = payload["_graph"]
    files: dict[str, dict[str, Any]] = payload["_files"]

    def rel(f: str) -> str:
        return files[f]["path"]

    hubs = sorted(
        (f for f in graph if graph.in_degree(f) > 0),
        key=lambda f: (-graph.in_degree(f), rel(f)),
    )[:limit]

    has_main = {
        row[0]
        for row in conn.execute(
            "SELECT DISTINCT file_path FROM code_nodes "
            "WHERE node_type = 'function' AND name = 'main'"
        )
    }
    entries = []
    for f in graph:
        name = PurePosixPath(rel(f)).name.lower()
        reasons = []
        if name in _ENTRY_NAMES:
            reasons.append("conventional entry file name")
        if f in has_main:
            reasons.append("defines main()")
        if graph.in_degree(f) == 0 and graph.out_degree(f) > 0:
            reasons.append("imports others, imported by none")
        if reasons and not _looks_like_test(rel(f)):
            entries.append((f, reasons))
    entries.sort(
        key=lambda item: (
            -len(item[1]),
            -graph.out_degree(item[0]),
            rel(item[0]),
        )
    )

    symbol_callers: dict[tuple[str, str], set[str]] = defaultdict(set)
    defined = {
        (fp, name)
        for fp, name in conn.execute(
            "SELECT file_path, name FROM code_nodes "
            "WHERE node_type IN ('class', 'function')"
        )
    }
    for src, dst, symbol in conn.execute(
        "SELECT from_node, to_node, target_symbol FROM edges "
        "WHERE relation_type = 'CALLS' AND resolution = 'internal'"
    ):
        if src == dst or src not in files or dst not in files:
            continue
        # Call edges resolve by name; skip cross-language matches, which are
        # almost always coincidences (Python parse_args -> a Rust fixture).
        if _family(src) != _family(dst):
            continue
        if symbol and (dst, symbol) in defined:
            symbol_callers[(dst, symbol)].add(src)
    symbols = sorted(
        symbol_callers.items(),
        key=lambda kv: (-len(kv[1]), rel(kv[0][0]), kv[0][1]),
    )[:limit]

    cycles = sorted(
        (
            sorted(rel(f) for f in comp)
            for comp in nx.strongly_connected_components(graph)
            if len(comp) > 1
        ),
        key=lambda c: (-len(c), c),
    )

    isolated = sorted(rel(f) for f in graph if graph.degree(f) == 0)

    return {
        "hubs": [
            {
                "path": rel(f),
                "imported_by": graph.in_degree(f),
                "imports": graph.out_degree(f),
            }
            for f in hubs
        ],
        "entry_points": [
            {"path": rel(f), "reasons": reasons, "imports": graph.out_degree(f)}
            for f, reasons in entries[:limit]
        ],
        "symbols": [
            {
                "name": name,
                "path": rel(fp),
                "caller_files": len(callers),
            }
            for (fp, name), callers in symbols
        ],
        "cycles": cycles[:limit],
        "cycle_count": len(cycles),
        "isolated_count": len(isolated),
    }


_FAMILIES = {"TypeScript": "JavaScript", "C++": "C"}


def _family(path: str) -> str:
    lang = _LANGUAGES.get(PurePosixPath(path).suffix.lower(), "Other")
    return _FAMILIES.get(lang, lang)


def _looks_like_test(rel_path: str) -> bool:
    parts = rel_path.lower().split("/")
    name = parts[-1]
    return (
        any(p in {"tests", "test", "__tests__", "e2e"} for p in parts[:-1])
        or name.startswith("test_")
        or ".test." in name
        or ".spec." in name
        or name.endswith("_test.go")
    )


def public_payload(payload: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    """Strip private helpers and attach the analysis for the HTML page."""
    data = {k: v for k, v in payload.items() if not k.startswith("_")}
    data["analysis"] = analysis
    return data


def _script_safe_json(data: Any) -> str:
    """JSON that cannot close or confuse an inline <script> element."""
    text = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    return (
        text.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace(" ", "\\u2028")
        .replace(" ", "\\u2029")
    )


def render_html(data: dict[str, Any]) -> str:
    """Inline the payload into the bundled template."""
    template = resources.files("visor").joinpath("map_template.html").read_text("utf-8")
    if DATA_PLACEHOLDER not in template:
        raise RuntimeError("visor map template is missing its data placeholder")
    title = f"{data['project']} · V.I.S.O.R. map"
    title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return template.replace("__VISOR_MAP_TITLE__", title).replace(
        DATA_PLACEHOLDER, _script_safe_json(data)
    )


def _md_escape(text: str) -> str:
    return text.replace("|", "\\|").replace("`", "'")


def render_report(data: dict[str, Any], html_name: str | None = None) -> str:
    """Render VISOR_REPORT.md from the public payload."""
    stats = data["stats"]
    analysis = data["analysis"]
    langs = ", ".join(f"{k} ({v})" for k, v in stats["languages"].items()) or "none"
    lines = [
        f"# {data['project']}: architecture report",
        "",
        f"Generated by [V.I.S.O.R.](https://github.com/dibun75/visor) "
        f"{data['visor_version']} on {data['generated_at']} from the local index.",
    ]
    if html_name:
        lines += ["", f"Interactive map: [{html_name}]({html_name})"]
    lines += [
        "",
        "## At a glance",
        "",
        f"- **{stats['files']}** source files, **{stats['symbols']}** classes and functions",
        f"- **{stats['import_links']}** internal import links, "
        f"**{stats['call_links']}** cross-file call links",
        f"- **{stats['clusters']}** directory clusters; languages: {langs}",
        f"- **{analysis['cycle_count']}** import cycle(s), "
        f"**{analysis['isolated_count']}** file(s) with no internal imports either way",
    ]
    if stats["files_shown"] < stats["files"]:
        lines.append(
            f"- The map shows the {stats['files_shown']} most connected files."
        )

    lines += [
        "",
        "## Hub files",
        "",
        "The files most other files import. Changes here ripple furthest.",
        "",
    ]
    if analysis["hubs"]:
        lines += ["| File | Imported by | Imports |", "| --- | ---: | ---: |"]
        lines += [
            f"| `{_md_escape(h['path'])}` | {h['imported_by']} | {h['imports']} |"
            for h in analysis["hubs"]
        ]
    else:
        lines.append("_No internal imports were resolved._")

    lines += [
        "",
        "## Likely entry points",
        "",
        "Heuristic: conventional file names, a `main()` function, or files that import others but nothing imports them.",
        "",
    ]
    if analysis["entry_points"]:
        lines += ["| File | Why |", "| --- | --- |"]
        lines += [
            f"| `{_md_escape(e['path'])}` | {', '.join(e['reasons'])} |"
            for e in analysis["entry_points"]
        ]
    else:
        lines.append("_None found._")

    lines += [
        "",
        "## Most-depended-on symbols",
        "",
        "Counted by distinct files that call the symbol, from resolved call edges.",
        "",
    ]
    if analysis["symbols"]:
        lines += ["| Symbol | Defined in | Caller files |", "| --- | --- | ---: |"]
        lines += [
            f"| `{_md_escape(s['name'])}` | `{_md_escape(s['path'])}` | {s['caller_files']} |"
            for s in analysis["symbols"]
        ]
    else:
        lines.append("_No cross-file calls were resolved._")

    lines += ["", "## Import cycles", ""]
    if analysis["cycles"]:
        for cycle in analysis["cycles"]:
            lines.append("- " + " ↔ ".join(f"`{_md_escape(p)}`" for p in cycle))
        if analysis["cycle_count"] > len(analysis["cycles"]):
            lines.append(
                f"- …and {analysis['cycle_count'] - len(analysis['cycles'])} more"
            )
    else:
        lines.append("_No import cycles._")

    lines += [
        "",
        "---",
        "",
        "Paths and symbol names only; no source code is included. "
        "Regenerate with `visor map`.",
        "",
    ]
    return "\n".join(lines)


def build_map(
    conn: sqlite3.Connection,
    workspace_root: str,
    max_files: int | None = DEFAULT_MAX_FILES,
) -> dict[str, Any]:
    """Collect and analyse the graph; return the public payload."""
    payload = collect_graph(conn, workspace_root, max_files=max_files)
    return public_payload(payload, analyze(payload, conn))
