"""Checks that keep the README, BENCHMARKS.md, and the hero image honest."""

from __future__ import annotations

import importlib.util
import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).parents[1]
DOCS = [ROOT / "README.md", ROOT / "BENCHMARKS.md"]
LINK = re.compile(r"""(?:\]\(|src=["'])(\./[^)"'#\s]+)""")


def _load_renderer():
    spec = importlib.util.spec_from_file_location(
        "render_repo_map", ROOT / "demo" / "render_repo_map.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_relative_links_resolve():
    missing = []
    for doc in DOCS:
        for target in LINK.findall(doc.read_text(encoding="utf-8")):
            if not (doc.parent / target).exists():
                missing.append(f"{doc.name}: {target}")
    assert not missing, missing


def test_readme_tool_count_matches_registrations():
    sources = [
        ROOT / "src" / "visor" / "tools" / "core.py",
        ROOT / "src" / "visor" / "server.py",
    ]
    registered = sum(p.read_text(encoding="utf-8").count("@mcp.tool(") for p in sources)
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    counts = {int(n) for n in re.findall(r"(\d+) (?:stdio )?tools", readme)}
    assert counts == {registered}, (counts, registered)


def test_benchmarks_moved_out_of_readme():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "95% CI" not in readme
    assert "BENCHMARKS.md" in readme
    assert "95% CI" in (ROOT / "BENCHMARKS.md").read_text(encoding="utf-8")


def test_hero_image_is_valid_svg():
    svg = ROOT / "docs" / "assets" / "repo-map.svg"
    tree = ET.parse(svg)
    assert tree.getroot().tag.endswith("svg")
    assert "/home/" not in svg.read_text(encoding="utf-8")


def test_render_svg_highlights_selected_files():
    renderer = _load_renderer()
    root = "/repo"
    graph = {
        "nodes": [
            {"id": 0, "file_path": "/repo/src/visor/workspace.py", "node_count": 9},
            {"id": 1, "file_path": "/repo/src/visor/server.py", "node_count": 20},
            {"id": 2, "file_path": "/repo/tests/test_x.py", "node_count": 3},
        ],
        "edges": [
            {"source": 1, "target": 0, "type": "IMPORTS"},
            {"source": 2, "target": 0, "type": "IMPORTS"},
        ],
    }
    svg = renderer.render_svg(
        graph, {"/repo/src/visor/workspace.py"}, root, "find root"
    )

    tree = ET.fromstring(svg)
    texts = [
        "".join(t.itertext()) for t in tree.iter("{http://www.w3.org/2000/svg}text")
    ]
    assert "src/visor/workspace.py" in texts
    assert "src/visor/server.py" not in texts  # only selected files are labelled
    assert any("3 files, 2 import edges" in t for t in texts)
    assert "/repo/" not in svg
    assert svg.count(renderer.HIGHLIGHT) >= 2  # ring plus panel bullet


def test_render_svg_handles_empty_graph():
    renderer = _load_renderer()
    svg = renderer.render_svg({"nodes": [], "edges": []}, set(), "/repo")
    assert ET.fromstring(svg).tag.endswith("svg")
