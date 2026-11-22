#!/usr/bin/env python3
"""Render the README hero image from V.I.S.O.R.'s real output.

The map comes from the ``get_architecture_map`` MCP tool (file-level nodes and
import edges). Files that ``build_context`` selects for the demo query are
highlighted, so the image shows the repository and the slice an agent receives.

Reproduce from a checkout::

    VISOR_HOME=$(mktemp -d) WORKSPACE_ROOT=$PWD uv run visor index
    VISOR_HOME=<same dir> WORKSPACE_ROOT=$PWD uv run python demo/render_repo_map.py

The output is written to ``docs/assets/repo-map.svg``.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from html import escape
from pathlib import Path

import networkx as nx

DEMO_QUERY = "resolve local workspace project root"
WIDTH, HEIGHT = 1200, 560
MAP_LEFT, MAP_TOP, MAP_RIGHT, MAP_BOTTOM = 40, 70, 860, 530

# Group colours (readable on the dark background in both GitHub themes).
GROUPS = [
    ("src/visor/tools", "MCP tools", "#2dd4bf"),
    ("src/visor/parser", "Parser", "#a78bfa"),
    ("src/visor/db", "Storage", "#f59e0b"),
    ("src/visor", "Core", "#38bdf8"),
    ("benchmarks", "Benchmarks", "#f472b6"),
    ("tests", "Tests", "#64748b"),
]
OTHER = ("", "Other", "#94a3b8")
HIGHLIGHT = "#4ade80"


def relative(path: str, root: str) -> str:
    root = root.rstrip("/") + "/"
    return path[len(root) :] if path.startswith(root) else path


def group_for(rel_path: str) -> tuple[str, str, str]:
    for group in GROUPS:
        prefix = group[0]
        if rel_path == prefix or rel_path.startswith(prefix + "/"):
            return group
    return OTHER


def render_svg(
    graph: dict, selected_files: set[str], root: str, query: str = DEMO_QUERY
) -> str:
    """Return an SVG string for an architecture map payload.

    ``graph`` is the parsed ``get_architecture_map`` output. ``selected_files``
    holds absolute file paths that ``build_context`` returned.
    """
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    g = nx.Graph()
    for node in nodes:
        g.add_node(node["id"])
    for edge in edges:
        if edge["source"] in g and edge["target"] in g:
            g.add_edge(edge["source"], edge["target"])

    pos = nx.spring_layout(g, seed=7, k=0.9) if len(g) else {}
    xs = [p[0] for p in pos.values()] or [0.0]
    ys = [p[1] for p in pos.values()] or [0.0]
    min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
    span_x = (max_x - min_x) or 1.0
    span_y = (max_y - min_y) or 1.0

    def place(node_id: int) -> tuple[float, float]:
        x, y = pos[node_id]
        px = MAP_LEFT + 30 + (x - min_x) / span_x * (MAP_RIGHT - MAP_LEFT - 60)
        py = MAP_TOP + 30 + (y - min_y) / span_y * (MAP_BOTTOM - MAP_TOP - 60)
        return px, py

    by_id = {node["id"]: node for node in nodes}
    max_count = max((node.get("node_count", 1) for node in nodes), default=1) or 1

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" '
        f'width="{WIDTH}" height="{HEIGHT}" font-family="ui-sans-serif, system-ui, '
        '-apple-system, Segoe UI, Helvetica, Arial, sans-serif">',
        f'<rect width="{WIDTH}" height="{HEIGHT}" rx="16" fill="#0b1020"/>',
        '<text x="40" y="44" fill="#e2e8f0" font-size="20" font-weight="600">'
        "Repository map</text>",
        f'<text x="200" y="44" fill="#94a3b8" font-size="14">{len(nodes)} files, '
        f'{len(edges)} import edges, from <tspan font-family="ui-monospace, '
        'SFMono-Regular, Menlo, monospace">get_architecture_map</tspan></text>',
    ]

    # Edges first, so nodes sit on top.
    for edge in edges:
        if edge["source"] not in pos or edge["target"] not in pos:
            continue
        x1, y1 = place(edge["source"])
        x2, y2 = place(edge["target"])
        both = (
            by_id[edge["source"]]["file_path"] in selected_files
            and by_id[edge["target"]]["file_path"] in selected_files
        )
        stroke = HIGHLIGHT if both else "#334155"
        width = 2 if both else 1
        parts.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{stroke}" stroke-width="{width}" stroke-opacity="0.8"/>'
        )

    labels: list[str] = []
    for node in nodes:
        if node["id"] not in pos:
            continue
        x, y = place(node["id"])
        rel = relative(node["file_path"], root)
        _, _, colour = group_for(rel)
        radius = 4 + 10 * (node.get("node_count", 1) / max_count) ** 0.5
        is_selected = node["file_path"] in selected_files
        if is_selected:
            parts.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius + 5:.1f}" '
                f'fill="none" stroke="{HIGHLIGHT}" stroke-width="2.5"/>'
            )
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" fill="{colour}" '
            f'fill-opacity="{1.0 if is_selected else 0.75}"><title>'
            f"{escape(rel)}</title></circle>"
        )
        if is_selected:
            labels.append(
                f'<text x="{x + radius + 8:.1f}" y="{y + 4:.1f}" fill="#e2e8f0" '
                f'font-size="13" font-weight="600" paint-order="stroke" '
                f'stroke="#0b1020" stroke-width="4">{escape(rel)}</text>'
            )
    parts.extend(labels)

    # Side panel: query, selected files, legend.
    panel_x = 890
    parts.append(
        f'<rect x="{panel_x - 10}" y="70" width="290" height="460" rx="12" '
        'fill="#111827" stroke="#1f2937"/>'
    )
    parts.append(
        f'<text x="{panel_x + 6}" y="100" fill="#94a3b8" font-size="12" '
        'letter-spacing="1">QUERY</text>'
    )
    parts.append(
        f'<text x="{panel_x + 6}" y="122" fill="#e2e8f0" font-size="14">'
        f"&#8220;{escape(query)}&#8221;</text>"
    )
    parts.append(
        f'<text x="{panel_x + 6}" y="158" fill="#94a3b8" font-size="12" '
        'letter-spacing="1">FILES IN THE CONTEXT SLICE</text>'
    )
    selected_rel = sorted(relative(path, root) for path in selected_files)
    line_y = 180
    for rel in selected_rel[:8]:
        parts.append(
            f'<circle cx="{panel_x + 12}" cy="{line_y - 4}" r="4" fill="{HIGHLIGHT}"/>'
        )
        parts.append(
            f'<text x="{panel_x + 24}" y="{line_y}" fill="#e2e8f0" font-size="12" '
            'font-family="ui-monospace, SFMono-Regular, Menlo, monospace">'
            f"{escape(rel)}</text>"
        )
        line_y += 20
    if len(selected_rel) > 8:
        parts.append(
            f'<text x="{panel_x + 24}" y="{line_y}" fill="#94a3b8" font-size="12">'
            f"+{len(selected_rel) - 8} more</text>"
        )
        line_y += 20

    legend_y = max(line_y + 24, 380)
    parts.append(
        f'<text x="{panel_x + 6}" y="{legend_y}" fill="#94a3b8" font-size="12" '
        'letter-spacing="1">LEGEND</text>'
    )
    legend_y += 22
    for _, label, colour in [*GROUPS, OTHER]:
        parts.append(
            f'<circle cx="{panel_x + 12}" cy="{legend_y - 4}" r="5" fill="{colour}"/>'
        )
        parts.append(
            f'<text x="{panel_x + 24}" y="{legend_y}" fill="#cbd5e1" '
            f'font-size="12">{label}</text>'
        )
        legend_y += 18
        if legend_y > 520:
            break

    parts.append("</svg>")
    return "\n".join(parts) + "\n"


async def _collect(query: str) -> tuple[dict, set[str]]:
    from visor.server import mcp

    async def call(name: str, arguments: dict) -> dict:
        content, _ = await mcp.call_tool(name, arguments)
        return json.loads(content[0].text)

    graph = await call("get_architecture_map", {"depth": 1})
    context = await call("build_context", {"query": query})
    selected = {
        item["file_path"]
        for item in context.get("context", context.get("nodes", []))
        if isinstance(item, dict) and item.get("file_path")
    }
    return graph, selected


def main() -> int:
    root = os.environ.get("WORKSPACE_ROOT") or os.getcwd()
    query = sys.argv[1] if len(sys.argv) > 1 else DEMO_QUERY
    graph, selected = asyncio.run(_collect(query))
    out = Path(__file__).resolve().parents[1] / "docs" / "assets" / "repo-map.svg"
    out.write_text(render_svg(graph, selected, root, query), encoding="utf-8")
    print(
        f"wrote {out} ({len(graph.get('nodes', []))} files, {len(selected)} selected)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
