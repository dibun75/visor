"""Tests for `visor map`: graph collection, analysis, HTML and report output."""

import json
import os
import re
import subprocess
import sys

import pytest

import visor.parser.watcher as watcher
from visor.map import (
    MAX_CLUSTERS,
    _choose_clusters,
    _script_safe_json,
    build_map,
    render_html,
    render_report,
)


def _write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_project(root):
    _write(root, "app/__init__.py", "")
    _write(
        root,
        "app/db.py",
        "class Store:\n    pass\n\n\ndef connect():\n    return Store()\n",
    )
    _write(
        root,
        "app/service.py",
        "from app.db import connect\n\n\ndef handle():\n    return connect()\n",
    )
    _write(
        root,
        "app/api.py",
        "from app.db import connect\nfrom app.service import handle\n\n\n"
        "def route():\n    connect()\n    return handle()\n",
    )
    _write(
        root,
        "main.py",
        "from app.api import route\n\n\ndef main():\n    route()\n",
    )
    # A two-file import cycle.
    _write(root, "loop/a.py", "from loop.b import bee\n\n\ndef ay():\n    bee()\n")
    _write(root, "loop/b.py", "from loop.a import ay\n\n\ndef bee():\n    ay()\n")
    _write(root, "lonely.py", "def alone():\n    return 1\n")
    _write(root, "pyproject.toml", '[project]\nname = "demo"\n')


@pytest.fixture
def indexed(tmp_path, test_db, monkeypatch, mock_embedding):
    project = tmp_path / "demo"
    project.mkdir()
    _make_project(project)
    test_db.workspace_root = str(project)
    monkeypatch.setattr(watcher, "db_client", test_db)
    monkeypatch.setattr(watcher.embedder, "encode", lambda _text: mock_embedding)
    watcher.index_workspace(str(project))
    return project, test_db


def test_build_map_collects_files_edges_and_analysis(indexed):
    project, db = indexed
    data = build_map(db.conn, str(project))

    paths = {n["path"] for n in data["nodes"]}
    assert {"app/db.py", "app/service.py", "app/api.py", "main.py"} <= paths
    assert data["project"] == "demo"
    assert not any(k.startswith("_") for k in data)

    by_path = {n["path"]: n for n in data["nodes"]}
    db_node = by_path["app/db.py"]
    assert db_node["imported_by"] == 2
    assert db_node["classes"] == 1 and db_node["functions"] == 1
    assert {s["name"] for s in db_node["top_symbols"]} == {"Store", "connect"}
    assert db_node["language"] == "Python"

    ids = {n["id"]: n["path"] for n in data["nodes"]}
    imports = {
        (ids[e["source"]], ids[e["target"]])
        for e in data["edges"]
        if e["type"] == "IMPORTS"
    }
    assert ("app/api.py", "app/db.py") in imports
    assert ("main.py", "app/api.py") in imports

    analysis = data["analysis"]
    assert analysis["hubs"][0]["path"] == "app/db.py"
    entry = {e["path"]: e["reasons"] for e in analysis["entry_points"]}
    assert "main.py" in entry
    assert "defines main()" in entry["main.py"]
    assert analysis["cycle_count"] == 1
    assert analysis["cycles"][0] == ["loop/a.py", "loop/b.py"]
    assert analysis["isolated_count"] >= 1
    symbols = {(s["name"], s["path"]): s["caller_files"] for s in analysis["symbols"]}
    assert symbols.get(("connect", "app/db.py")) == 2


def test_exported_data_has_no_absolute_paths_or_source(indexed):
    project, db = indexed
    data = build_map(db.conn, str(project))
    html = render_html(data)
    report = render_report(data, html_name="visor-map.html")

    for text in (html, report, json.dumps(data)):
        assert str(project) not in text
        assert os.path.realpath(str(project)) not in text
        assert "return Store()" not in text


def test_max_files_keeps_the_most_connected(indexed):
    project, db = indexed
    data = build_map(db.conn, str(project), max_files=2)
    assert data["stats"]["files_shown"] == 2
    assert data["stats"]["files"] > 2
    assert "app/db.py" in {n["path"] for n in data["nodes"]}
    shown = {n["id"] for n in data["nodes"]}
    assert all(e["source"] in shown and e["target"] in shown for e in data["edges"])


def test_html_is_self_contained_and_embeds_valid_data(indexed):
    project, db = indexed
    data = build_map(db.conn, str(project))
    html = render_html(data)

    assert html.startswith("<!doctype html>")
    assert "/*__VISOR_MAP_DATA__*/" not in html
    assert "__VISOR_MAP_TITLE__" not in html
    assert "<title>demo · V.I.S.O.R. map</title>" in html
    # No network fetches: no external scripts, stylesheets, or fonts.
    assert not re.search(r"<script[^>]+src=", html)
    assert not re.search(r"<link[^>]+stylesheet", html)
    assert "@import" not in html

    match = re.search(
        r'<script id="visor-data" type="application/json">(.*?)</script>',
        html,
        re.S,
    )
    assert match
    embedded = json.loads(match.group(1))
    assert embedded["stats"] == data["stats"]
    assert len(embedded["nodes"]) == len(data["nodes"])


def test_script_safe_json_cannot_break_out_of_script_tag():
    payload = {"name": "</script><script>alert(1)</script>", "x": "a&b "}
    text = _script_safe_json(payload)
    assert "</script" not in text.lower()
    assert "<" not in text and ">" not in text and "&" not in text
    assert json.loads(text) == payload


def test_title_is_html_escaped():
    data = {
        "project": "<b>x</b>",
        "nodes": [],
        "edges": [],
    }
    html = render_html(data)
    assert "<title>&lt;b&gt;x&lt;/b&gt; · V.I.S.O.R. map</title>" in html


def test_report_sections(indexed):
    project, db = indexed
    report = render_report(build_map(db.conn, str(project)), "visor-map.html")
    assert report.startswith("# demo: architecture report")
    for heading in (
        "## At a glance",
        "## Hub files",
        "## Likely entry points",
        "## Most-depended-on symbols",
        "## Import cycles",
    ):
        assert heading in report
    assert "| `app/db.py` | 2 |" in report
    assert "`loop/a.py` ↔ `loop/b.py`" in report
    assert "[visor-map.html](visor-map.html)" in report


def test_report_on_empty_index(test_db, tmp_path):
    data = build_map(test_db.conn, str(tmp_path))
    assert data["nodes"] == [] and data["edges"] == []
    report = render_report(data)
    assert "_No internal imports were resolved._" in report
    assert "_No import cycles._" in report
    assert render_html(data).startswith("<!doctype html>")


def test_choose_clusters_splits_large_groups_and_stays_bounded():
    paths = [f"src/pkg/mod{i}/f{j}.py" for i in range(30) for j in range(2)]
    paths += ["README_helper.py", "tests/test_a.py", "src/pkg/core.py"]
    clusters = _choose_clusters(paths)
    assert set(clusters) == set(paths)
    assert len(set(clusters.values())) <= MAX_CLUSTERS
    assert clusters["README_helper.py"] == "(root)"
    assert clusters["tests/test_a.py"] == "tests"

    small = _choose_clusters(["a/x/1.py", "a/y/2.py", "a/y/3.py", "b/4.py"])
    assert small["a/x/1.py"] == "a/x"
    assert small["a/y/2.py"] == "a/y"
    assert small["b/4.py"] == "b"


def test_cli_map_writes_html_and_report(tmp_path):
    project = tmp_path / "cli-demo"
    project.mkdir()
    _make_project(project)
    out_dir = tmp_path / "out"
    env = dict(
        os.environ,
        VISOR_HOME=str(tmp_path / "home"),
        VISOR_RETRIEVAL_MODE="lexical",
    )
    env.pop("WORKSPACE_ROOT", None)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "visor.cli",
            "--workspace",
            str(project),
            "map",
            "--out",
            str(out_dir / "map.html"),
            "--report",
            str(out_dir / "VISOR_REPORT.md"),
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "import cycle" in result.stdout
    html = (out_dir / "map.html").read_text(encoding="utf-8")
    report = (out_dir / "VISOR_REPORT.md").read_text(encoding="utf-8")
    assert "app/db.py" in html
    assert "[map.html](map.html)" in report
    assert str(project) not in html


def test_cli_map_json_and_no_report(tmp_path):
    project = tmp_path / "json-demo"
    project.mkdir()
    _make_project(project)
    env = dict(
        os.environ,
        VISOR_HOME=str(tmp_path / "home"),
        VISOR_RETRIEVAL_MODE="lexical",
    )
    env.pop("WORKSPACE_ROOT", None)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "visor.cli",
            "--workspace",
            str(project),
            "map",
            "--json",
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=tmp_path,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["stats"]["files"] >= 5
    assert not (tmp_path / "visor-map.html").exists()
    assert not (tmp_path / "VISOR_REPORT.md").exists()
