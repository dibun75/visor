"""Explicit retrieval feedback: ranking, storage, CLI, and MCP."""

import json
import os
import sqlite3
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

from visor.db.client import VectorDBClient
from visor.feedback import (
    FEEDBACK_MAX_ADJUSTMENT,
    FeedbackError,
    record_feedback,
)
from visor.tools.context_engine import _classify_intent, build_context


def _prepare(tmp_path, test_db, monkeypatch):
    monkeypatch.setenv("VISOR_RETRIEVAL_MODE", "lexical")
    import visor.parser.watcher as watcher

    monkeypatch.setattr(watcher, "db_client", test_db)
    test_db.workspace_root = str(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname='demo'\nversion='0'\n", encoding="utf-8"
    )
    files = {
        "anchor.py": 'def shared():\n    """anchor shared"""\n    return 1\n',
        "left.py": 'def shared():\n    """left"""\n    return 1\n',
        "right.py": 'def shared():\n    """right"""\n    return 1\n',
        "extra.py": "def extra():\n    return 2\n",
        "other.py": 'def database():\n    """migration plan"""\n    return 1\n',
    }
    for relative, source in files.items():
        path = tmp_path / relative
        path.write_text(source, encoding="utf-8")
        watcher.index_file(str(path), skip_changelog=True)
    return watcher


def _names(payload):
    return [item["name"] for item in payload["context"]]


def _score_for(payload, filename):
    for item in payload["context"]:
        if item["file_path"].endswith(filename):
            return item["relevance_score"]
    raise AssertionError(filename)


def _feedback_signal(payload, filename):
    for item in payload["context"]:
        if item["file_path"].endswith(filename):
            return payload["debug"]["scores"][str(item["id"])]["feedback"]
    raise AssertionError(filename)


def test_useful_exact_and_similar_feedback_moves_only_related_files(
    tmp_path, test_db, monkeypatch
):
    _prepare(tmp_path, test_db, monkeypatch)
    baseline = build_context("shared anchor")
    unrelated_before = build_context("database migration plan")
    assert _names(baseline).index("shared") >= 0
    assert baseline["context"][1]["file_path"].endswith("left.py")
    assert baseline["context"][2]["file_path"].endswith("right.py")
    assert _feedback_signal(baseline, "right.py") == 0

    record_feedback(
        query="shared anchor",
        file_path=str(tmp_path / "right.py"),
        verdict="useful",
        reason="kept the report",
        intent=_classify_intent("shared anchor"),
    )
    exact = build_context("shared anchor")
    similar = build_context("shared anchor export")
    unrelated_after = build_context("database migration plan")

    assert exact["context"][1]["file_path"].endswith("right.py")
    assert exact["context"][2]["file_path"].endswith("left.py")
    assert _feedback_signal(exact, "right.py") == FEEDBACK_MAX_ADJUSTMENT
    assert (
        "Boosted by prior developer feedback for a similar query"
        in exact["debug"]["reasoning"][str(exact["context"][1]["id"])]
    )
    assert similar["context"][1]["file_path"].endswith("right.py")
    assert [item["file_path"] for item in unrelated_before["context"]] == [
        item["file_path"] for item in unrelated_after["context"]
    ]
    assert [item["relevance_score"] for item in unrelated_before["context"]] == [
        item["relevance_score"] for item in unrelated_after["context"]
    ]


def test_irrelevant_feedback_lowers_rank_within_cap(tmp_path, test_db, monkeypatch):
    _prepare(tmp_path, test_db, monkeypatch)
    before = _score_for(build_context("shared anchor"), "left.py")
    record_feedback(
        query="shared anchor",
        file_path="left.py",
        verdict="irrelevant",
        intent="DEFAULT",
    )
    after = build_context("shared anchor")
    assert _score_for(after, "left.py") == round(before - FEEDBACK_MAX_ADJUSTMENT, 4)
    assert _feedback_signal(after, "left.py") == -FEEDBACK_MAX_ADJUSTMENT
    assert (
        "Reduced by prior developer feedback for a similar query"
        in after["debug"]["reasoning"][
            str(
                next(
                    item["id"]
                    for item in after["context"]
                    if item["file_path"].endswith("left.py")
                )
            )
        ]
    )
    assert _score_for(after, "anchor.py") > _score_for(after, "left.py")


def test_missing_feedback_adds_existing_file_only(tmp_path, test_db, monkeypatch):
    _prepare(tmp_path, test_db, monkeypatch)
    assert "extra" not in _names(build_context("shared anchor"))
    record_feedback(
        query="shared anchor",
        file_path="extra.py",
        verdict="missing",
        intent="DEFAULT",
    )
    found = build_context("shared anchor")
    assert "extra" in _names(found)
    assert _feedback_signal(found, "extra.py") == FEEDBACK_MAX_ADJUSTMENT

    for bad in ("/etc/passwd", str(tmp_path / "missing.py"), "../outside.py"):
        try:
            record_feedback(
                query="shared anchor",
                file_path=bad,
                verdict="missing",
                intent="DEFAULT",
            )
        except FeedbackError:
            continue
        raise AssertionError(bad)


def test_feedback_is_workspace_scoped_and_upserted(tmp_path, test_db, monkeypatch):
    _prepare(tmp_path, test_db, monkeypatch)
    first = record_feedback(
        query="shared anchor",
        file_path="right.py",
        verdict="useful",
        reason="first",
        intent="DEFAULT",
    )
    second = record_feedback(
        query="shared anchor",
        file_path="right.py",
        verdict="useful",
        reason="second",
        intent="DEFAULT",
    )
    assert first["id"] == second["id"]
    assert second["reason"] == "second"
    assert (
        test_db.spoke_conn.execute("SELECT COUNT(*) FROM context_feedback").fetchone()[
            0
        ]
        == 1
    )
    stored = test_db.spoke_conn.execute(
        "SELECT relative_path FROM context_feedback"
    ).fetchone()[0]
    assert stored == "right.py"
    assert str(Path.home()) not in stored

    original_hash = test_db.workspace_hash
    boosted = build_context("shared anchor")
    test_db.workspace_hash = "other-workspace"
    isolated = build_context("shared anchor")
    test_db.workspace_hash = original_hash
    assert _feedback_signal(boosted, "right.py") == FEEDBACK_MAX_ADJUSTMENT
    assert _feedback_signal(isolated, "right.py") == 0


def test_old_feedback_decays(tmp_path, test_db, monkeypatch):
    _prepare(tmp_path, test_db, monkeypatch)
    from visor import feedback as feedback_module

    fixed = feedback_module.utcnow()
    monkeypatch.setattr(feedback_module, "utcnow", lambda: fixed)
    record_feedback(
        query="shared anchor",
        file_path="right.py",
        verdict="useful",
        intent="DEFAULT",
    )
    stale = (fixed - timedelta(days=30)).isoformat()
    test_db.spoke_conn.execute("UPDATE context_feedback SET updated_at = ?", (stale,))
    test_db.spoke_conn.commit()
    payload = build_context("shared anchor")
    assert _feedback_signal(payload, "right.py") == round(
        FEEDBACK_MAX_ADJUSTMENT * 0.5, 4
    )


def test_delete_and_clear_remove_ranking_effect(tmp_path, test_db, monkeypatch):
    _prepare(tmp_path, test_db, monkeypatch)
    from visor.feedback import clear_feedback, delete_feedback

    edges_before = test_db.spoke_conn.execute("SELECT COUNT(*) FROM edges").fetchone()[
        0
    ]
    right = record_feedback(
        query="shared anchor",
        file_path="right.py",
        verdict="useful",
        intent="DEFAULT",
    )
    left = record_feedback(
        query="shared anchor",
        file_path="left.py",
        verdict="irrelevant",
        intent="DEFAULT",
    )
    assert delete_feedback(right["id"]) is True
    after_delete = build_context("shared anchor")
    assert _feedback_signal(after_delete, "right.py") == 0
    assert _feedback_signal(after_delete, "left.py") == -FEEDBACK_MAX_ADJUSTMENT
    assert clear_feedback() == 1
    cleared = build_context("shared anchor")
    assert _feedback_signal(cleared, "left.py") == 0
    assert (
        test_db.spoke_conn.execute("SELECT COUNT(*) FROM context_feedback").fetchone()[
            0
        ]
        == 0
    )
    edges_after = test_db.spoke_conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
    assert edges_before == edges_after
    assert left["id"] != right["id"]


def test_no_feedback_leaves_retrieval_unchanged(tmp_path, test_db, monkeypatch):
    _prepare(tmp_path, test_db, monkeypatch)
    first = build_context("shared anchor")
    second = build_context("shared anchor")
    assert [item["relevance_score"] for item in first["context"]] == [
        item["relevance_score"] for item in second["context"]
    ]
    assert all(
        first["debug"]["scores"][str(item["id"])]["feedback"] == 0
        for item in first["context"]
    )


def test_existing_database_gains_feedback_table(tmp_path):
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE code_nodes (
            id INTEGER PRIMARY KEY,
            file_path TEXT,
            node_type TEXT,
            name TEXT,
            docstring TEXT,
            start_line INTEGER,
            end_line INTEGER,
            file_hash TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO code_nodes (file_path, node_type, name) VALUES ('a.py', 'function', 'run')"
    )
    conn.commit()
    conn.close()

    VectorDBClient._instance = None
    client = VectorDBClient(db_path=str(db_path))
    try:
        names = {
            row[0]
            for row in client.spoke_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert "context_feedback" in names
        assert (
            client.spoke_conn.execute("SELECT name FROM code_nodes").fetchone()[0]
            == "run"
        )
    finally:
        client.spoke_conn.close()
        client.hub_conn.close()
        VectorDBClient._instance = None


def test_feedback_retrieval_benchmark():
    repo = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "benchmarks/feedback_retrieval.py"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["passed"] is True
    assert payload["exact_query"].index("right.py") < payload["exact_query"].index(
        "left.py"
    )
    assert payload["unrelated_before"] == payload["unrelated_after"]


def test_language_extensions_remain_registered():
    from visor.parser.treesitter import _EXT_MAP

    for extension in (
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".go",
        ".rs",
        ".java",
        ".c",
        ".h",
        ".cpp",
        ".cs",
    ):
        assert extension in _EXT_MAP


def test_feedback_cli_human_and_json(tmp_path):
    project = tmp_path / "proj"
    source = project / "src"
    source.mkdir(parents=True)
    (project / "pyproject.toml").write_text(
        "[project]\nname='demo'\n", encoding="utf-8"
    )
    (source / "app.py").write_text("def shared():\n    return 1\n", encoding="utf-8")
    env = os.environ.copy()
    env["VISOR_HOME"] = str(tmp_path / "visor-home")
    env["VISOR_RETRIEVAL_MODE"] = "lexical"
    env.pop("WORKSPACE_ROOT", None)
    command = [
        sys.executable,
        "-m",
        "visor.cli",
        "--workspace",
        str(project),
        "--retrieval-mode",
        "lexical",
    ]

    recorded = subprocess.run(
        command
        + ["feedback", "useful", "src/app.py", "--query", "shared anchor", "--json"],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert recorded.returncode == 0, recorded.stderr
    payload = json.loads(recorded.stdout)
    assert payload["ok"] is True
    assert payload["feedback"]["relative_path"] == "src/app.py"
    assert payload["feedback"]["verdict"] == "useful"
    assert str(Path.home()) not in recorded.stdout

    listed = subprocess.run(
        command + ["feedback", "list"],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert listed.returncode == 0
    assert "src/app.py" in listed.stdout
    assert "useful" in listed.stdout
    assert str(Path.home()) not in listed.stdout

    refused = subprocess.run(
        command + ["feedback", "clear", "--json"],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert refused.returncode == 2
    assert json.loads(refused.stdout)["ok"] is False

    removed = subprocess.run(
        command + ["feedback", "delete", payload["feedback"]["id"], "--json"],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert removed.returncode == 0
    assert json.loads(removed.stdout)["deleted"] is True

    cleared = subprocess.run(
        command
        + [
            "feedback",
            "irrelevant",
            "src/app.py",
            "--query",
            "shared anchor",
            "--json",
        ],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert cleared.returncode == 0
    wiped = subprocess.run(
        command + ["feedback", "clear", "--yes", "--json"],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert wiped.returncode == 0
    assert json.loads(wiped.stdout)["deleted"] == 1


def test_feedback_mcp_tools_validate_and_return_json(tmp_path, test_db, monkeypatch):
    _prepare(tmp_path, test_db, monkeypatch)
    from unittest.mock import MagicMock

    from visor.tools.core import register_tools

    tools = {}

    def mock_tool():
        def decorator(func):
            tools[func.__name__] = func
            return func

        return decorator

    mcp = MagicMock()
    mcp.tool = mock_tool
    register_tools(mcp)

    bad = json.loads(
        tools["record_context_feedback"]("shared anchor", "right.py", "maybe")
    )
    assert bad["ok"] is False
    outside = json.loads(
        tools["record_context_feedback"]("shared anchor", "/etc/passwd", "useful")
    )
    assert outside["ok"] is False
    saved = json.loads(
        tools["record_context_feedback"](
            "shared anchor", "right.py", "useful", "checked"
        )
    )
    assert saved["ok"] is True
    listed = json.loads(tools["list_context_feedback"]("shared anchor"))
    assert listed["feedback"][0]["relative_path"] == "right.py"
    unconfirmed = json.loads(tools["clear_context_feedback"](False))
    assert unconfirmed["ok"] is False
    deleted = json.loads(tools["delete_context_feedback"](saved["feedback"]["id"]))
    assert deleted["deleted"] is True
    again = json.loads(
        tools["record_context_feedback"]("shared anchor", "left.py", "irrelevant")
    )
    cleared = json.loads(tools["clear_context_feedback"](True))
    assert cleared["deleted"] == 1
    assert again["ok"] is True
