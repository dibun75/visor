import sqlite3

import pytest

from visor.parser.dependencies import canonical_file, normalize_edges
from visor.parser.treesitter import ast_parser
import visor.parser.watcher as watcher


def _node(name, vector, *, node_type="function"):
    return {
        "node_type": node_type,
        "name": name,
        "docstring": "",
        "vector": vector,
        "start_line": 1,
        "end_line": 1,
    }


def test_replace_file_index_is_atomic_and_removes_stale_records(
    test_db, mock_embedding
):
    source = "/workspace/app.py"
    old_target = "/workspace/old.py"
    new_target = "/workspace/new.py"
    test_db.replace_file_index(
        file_path=source,
        file_hash="old-hash",
        nodes=[_node("old_name", mock_embedding)],
        edges=[
            {
                "to": old_target,
                "type": "IMPORTS",
                "raw_target": "old",
                "resolution": "internal",
            }
        ],
    )
    test_db.mark_index_ready()

    test_db.replace_file_index(
        file_path=source,
        file_hash="new-hash",
        nodes=[_node("new_name", mock_embedding)],
        edges=[
            {
                "to": new_target,
                "type": "IMPORTS",
                "raw_target": "new",
                "resolution": "internal",
            }
        ],
    )

    assert test_db.conn.execute(
        "SELECT name FROM code_nodes WHERE file_path = ?", (source,)
    ).fetchall() == [("new_name",)]
    assert test_db.conn.execute(
        "SELECT to_node FROM edges WHERE from_node = ?", (source,)
    ).fetchall() == [(new_target,)]
    assert test_db.get_indexed_file_hash(source) == "new-hash"
    assert test_db.get_index_status()["nodes"] == test_db.get_index_status()["vectors"]

    with pytest.raises(sqlite3.OperationalError):
        test_db.replace_file_index(
            file_path=source,
            file_hash="broken-hash",
            nodes=[_node("broken", [0.1])],
            edges=[],
        )

    assert test_db.conn.execute(
        "SELECT name FROM code_nodes WHERE file_path = ?", (source,)
    ).fetchall() == [("new_name",)]
    assert test_db.get_indexed_file_hash(source) == "new-hash"


def test_delete_file_index_removes_vectors_and_internal_references(
    test_db, mock_embedding
):
    source = "/workspace/app.py"
    test_db.replace_file_index(
        file_path=source,
        file_hash="hash",
        nodes=[_node("run", mock_embedding)],
        edges=[],
    )
    test_db.upsert_edge("/workspace/consumer.py", source, "IMPORTS")

    test_db.delete_file_index(source)

    assert (
        test_db.conn.execute(
            "SELECT COUNT(*) FROM code_nodes WHERE file_path = ?", (source,)
        ).fetchone()[0]
        == 0
    )
    assert (
        test_db.conn.execute(
            "SELECT COUNT(*) FROM indexed_files WHERE file_path = ?", (source,)
        ).fetchone()[0]
        == 0
    )
    assert (
        test_db.conn.execute(
            "SELECT COUNT(*) FROM edges WHERE from_node = ? OR to_node = ?",
            (source, source),
        ).fetchone()[0]
        == 0
    )
    assert test_db.get_index_status()["nodes"] == test_db.get_index_status()["vectors"]


def test_index_file_is_repeatable_and_replaces_changed_symbols(
    tmp_path, test_db, monkeypatch, mock_embedding
):
    util = tmp_path / "util.py"
    app = tmp_path / "app.py"
    util.write_text("def helper():\n    return 1\n", encoding="utf-8")
    app.write_text(
        "from util import helper\n\ndef old_name():\n    return helper()\n",
        encoding="utf-8",
    )

    test_db.workspace_root = str(tmp_path)
    monkeypatch.setattr(watcher, "db_client", test_db)
    monkeypatch.setattr(watcher.embedder, "encode", lambda _text: mock_embedding)

    watcher.index_file(str(util), skip_changelog=True)
    watcher.index_file(str(app), skip_changelog=True)
    first_revision = test_db.graph_revision
    watcher.index_file(str(app), skip_changelog=True)

    assert test_db.graph_revision == first_revision
    assert test_db.conn.execute(
        "SELECT to_node FROM edges WHERE from_node = ? AND relation_type = 'IMPORTS'",
        (canonical_file(app),),
    ).fetchall() == [(canonical_file(util),)]

    app.write_text("def new_name():\n    return 2\n", encoding="utf-8")
    watcher.index_file(str(app), skip_changelog=True)

    names = {
        row[0]
        for row in test_db.conn.execute(
            "SELECT name FROM code_nodes WHERE file_path = ?", (canonical_file(app),)
        )
    }
    assert "new_name" in names
    assert "old_name" not in names
    assert (
        test_db.conn.execute(
            "SELECT COUNT(*) FROM edges WHERE from_node = ?",
            (canonical_file(app),),
        ).fetchone()[0]
        == 0
    )
    test_db.mark_index_ready()
    assert test_db.get_index_status()["ready"] is True


@pytest.mark.parametrize(
    ("source_rel", "target_rel", "source_text"),
    [
        ("app.py", "util.py", "from util import helper\n"),
        ("app.ts", "util.ts", 'import { helper } from "./util";\n'),
        ("app.js", "util.js", 'import { helper } from "./util";\n'),
        (
            "main.go",
            "util/util.go",
            'package main\nimport "example.com/project/util"\n',
        ),
        ("src/main.rs", "src/util.rs", "use crate::util::helper;\n"),
        (
            "src/main/java/com/example/App.java",
            "src/main/java/com/example/Util.java",
            "package com.example;\nimport com.example.Util;\nclass App {}\n",
        ),
        ("main.c", "util.h", '#include "util.h"\n'),
        ("main.cpp", "util.hpp", '#include "util.hpp"\n'),
        (
            "src/Demo/App.cs",
            "src/Demo/Lib.cs",
            "using Demo.Lib;\nnamespace Demo { class App {} }\n",
        ),
    ],
)
def test_real_parser_edges_resolve_to_workspace_files(
    tmp_path, test_db, source_rel, target_rel, source_text
):
    source = tmp_path / source_rel
    target = tmp_path / target_rel
    source.parent.mkdir(parents=True, exist_ok=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(source_text, encoding="utf-8")
    target.write_text("\n", encoding="utf-8")

    parsed = ast_parser.parse_file(str(source))
    normalized = normalize_edges(
        source_file=str(source),
        parser_edges=parsed.edges,
        workspace_root=str(tmp_path),
        db_client=test_db,
    )

    assert parsed.error is None
    assert any(edge["type"] == "IMPORTS" for edge in parsed.edges)
    assert any(
        edge["type"] == "IMPORTS"
        and edge["resolution"] == "internal"
        and edge["to"] == canonical_file(target)
        for edge in normalized
    )


def test_unresolved_and_external_imports_are_explicit(tmp_path, test_db):
    source = tmp_path / "app.ts"
    source.write_text(
        'import missing from "./missing";\nimport react from "react";\n',
        encoding="utf-8",
    )
    parsed = ast_parser.parse_file(str(source))
    normalized = normalize_edges(
        source_file=str(source),
        parser_edges=parsed.edges,
        workspace_root=str(tmp_path),
        db_client=test_db,
    )

    resolutions = {edge["raw_target"]: edge["resolution"] for edge in normalized}
    assert resolutions["./missing"] == "unresolved"
    assert resolutions["react"] == "external"


def test_unchanged_file_with_missing_vector_is_repaired(
    tmp_path, test_db, monkeypatch, mock_embedding
):
    source = tmp_path / "app.py"
    source.write_text("def run():\n    return 1\n", encoding="utf-8")
    test_db.workspace_root = str(tmp_path)
    monkeypatch.setattr(watcher, "db_client", test_db)
    monkeypatch.setattr(watcher.embedder, "encode", lambda _text: mock_embedding)

    watcher.index_file(str(source), skip_changelog=True)
    node_id = test_db.conn.execute(
        "SELECT id FROM code_nodes WHERE file_path = ?", (canonical_file(source),)
    ).fetchone()[0]
    test_db.conn.execute("DELETE FROM vec_code_nodes WHERE rowid = ?", (node_id,))
    test_db.conn.commit()

    assert (
        test_db.is_file_index_current(
            canonical_file(source),
            test_db.get_indexed_file_hash(canonical_file(source)),
        )
        is False
    )

    watcher.index_file(str(source), skip_changelog=True)

    assert (
        test_db.conn.execute("SELECT COUNT(*) FROM vec_code_nodes").fetchone()[0] == 1
    )
    test_db.mark_index_ready()
    assert test_db.get_index_status()["ready"] is True


def test_workspace_scan_purges_deleted_files(
    tmp_path, test_db, monkeypatch, mock_embedding
):
    source = tmp_path / "obsolete.py"
    source.write_text("def obsolete():\n    pass\n", encoding="utf-8")
    test_db.workspace_root = str(tmp_path)
    monkeypatch.setattr(watcher, "db_client", test_db)
    monkeypatch.setattr(watcher.embedder, "encode", lambda _text: mock_embedding)

    watcher.index_workspace(str(tmp_path))
    indexed_path = canonical_file(source)
    assert test_db.get_indexed_file_hash(indexed_path)

    source.unlink()
    watcher.index_workspace(str(tmp_path))

    assert test_db.get_indexed_file_hash(indexed_path) is None
    assert (
        test_db.conn.execute(
            "SELECT COUNT(*) FROM code_nodes WHERE file_path = ?", (indexed_path,)
        ).fetchone()[0]
        == 0
    )
    assert test_db.get_index_status()["ready"] is True


def test_changed_target_invalidates_stale_internal_call_edges(test_db, mock_embedding):
    target = "/workspace/target.py"
    test_db.replace_file_index(
        file_path=target,
        file_hash="old",
        nodes=[_node("old_name", mock_embedding)],
        edges=[],
    )
    test_db.upsert_edge(
        "/workspace/caller.py",
        target,
        "CALLS",
        raw_target="old_name",
        target_symbol="old_name",
    )

    test_db.replace_file_index(
        file_path=target,
        file_hash="new",
        nodes=[_node("new_name", mock_embedding)],
        edges=[],
    )

    assert test_db.conn.execute(
        "SELECT to_node, target_symbol, resolution FROM edges "
        "WHERE from_node = '/workspace/caller.py'"
    ).fetchone() == ("old_name", "old_name", "unresolved")


def test_csharp_system_using_is_external(tmp_path, test_db):
    source = tmp_path / "App.cs"
    source.write_text("using System;\nclass App {}\n", encoding="utf-8")
    parsed = ast_parser.parse_file(str(source))
    normalized = normalize_edges(
        source_file=str(source),
        parser_edges=parsed.edges,
        workspace_root=str(tmp_path),
        db_client=test_db,
    )
    using = next(edge for edge in normalized if edge["raw_target"] == "System")
    assert using["resolution"] == "external"


def test_csharp_reindex_and_deletion(tmp_path, test_db, monkeypatch):
    source = tmp_path / "Service.cs"
    source.write_text(
        "namespace Demo {\n  public class Service {\n    public void Apply() {}\n  }\n}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("VISOR_RETRIEVAL_MODE", "lexical")
    monkeypatch.setattr(watcher, "db_client", test_db)
    test_db.workspace_root = str(tmp_path)

    watcher.index_file(str(source), skip_changelog=True)
    indexed = canonical_file(source)
    names = {
        row[0]
        for row in test_db.conn.execute(
            "SELECT name FROM code_nodes WHERE file_path = ?", (indexed,)
        )
    }
    assert "Service" in names
    assert "Apply" in names

    source.write_text(
        "namespace Demo {\n  public class Service {\n    public void Replace() {}\n  }\n}\n",
        encoding="utf-8",
    )
    watcher.index_file(str(source), skip_changelog=True)
    names = {
        row[0]
        for row in test_db.conn.execute(
            "SELECT name FROM code_nodes WHERE file_path = ?", (indexed,)
        )
    }
    assert "Replace" in names
    assert "Apply" not in names

    source.unlink()
    watcher.index_workspace(str(tmp_path))
    assert test_db.get_indexed_file_hash(indexed) is None
    assert (
        test_db.conn.execute(
            "SELECT COUNT(*) FROM code_nodes WHERE file_path = ?", (indexed,)
        ).fetchone()[0]
        == 0
    )


def test_csharp_context_retrieval_finds_symbols(tmp_path, test_db, monkeypatch):
    source = tmp_path / "Service.cs"
    source.write_text(
        "namespace Demo {\n  public class Service {\n    public void ApplyDiscount() {}\n  }\n}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("VISOR_RETRIEVAL_MODE", "lexical")
    monkeypatch.setattr(watcher, "db_client", test_db)
    test_db.workspace_root = str(tmp_path)
    watcher.index_file(str(source), skip_changelog=True)
    test_db.mark_index_ready()

    from visor.tools.context_engine import build_context

    payload = build_context("ApplyDiscount service")
    names = {item["name"] for item in payload["context"]}
    assert "ApplyDiscount" in names or "Service" in names
    assert payload["debug"]["retrieval_mode"] == "lexical"


def test_system_include_is_external_not_missing_workspace_file(tmp_path, test_db):
    source = tmp_path / "main.c"
    source.write_text("#include <stdio.h>\n", encoding="utf-8")
    parsed = ast_parser.parse_file(str(source))

    normalized = normalize_edges(
        source_file=str(source),
        parser_edges=parsed.edges,
        workspace_root=str(tmp_path),
        db_client=test_db,
    )

    assert normalized[0]["raw_target"] == "<stdio.h>"
    assert normalized[0]["resolution"] == "external"


def test_ambiguous_workspace_import_is_not_claimed_as_internal(tmp_path, test_db):
    source = tmp_path / "app.py"
    source.write_text("from util import helper\n", encoding="utf-8")
    for directory in ("one", "two"):
        candidate = tmp_path / directory / "util.py"
        candidate.parent.mkdir()
        candidate.write_text("def helper():\n    pass\n", encoding="utf-8")

    parsed = ast_parser.parse_file(str(source))
    normalized = normalize_edges(
        source_file=str(source),
        parser_edges=parsed.edges,
        workspace_root=str(tmp_path),
        db_client=test_db,
    )

    import_edge = next(edge for edge in normalized if edge["type"] == "IMPORTS")
    assert import_edge["resolution"] == "unresolved"
    assert import_edge["to"] == "util"
