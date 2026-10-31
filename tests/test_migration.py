import sqlite3

from visor.db.client import INDEX_SCHEMA_VERSION, VectorDBClient
from visor.db.migration import _migrate_spoke_data
import visor.parser.watcher as watcher


def test_legacy_spoke_migration_preserves_source_and_requires_reindex(tmp_path):
    old_path = tmp_path / "visor_memory.db"
    spoke_path = tmp_path / "graph.db"
    old_conn = sqlite3.connect(old_path)
    old_conn.execute(
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
    old_conn.execute(
        """
        CREATE TABLE edges (
            id INTEGER PRIMARY KEY,
            from_node TEXT,
            to_node TEXT,
            relation_type TEXT
        )
        """
    )
    old_conn.execute(
        "INSERT INTO code_nodes VALUES (1, ?, ?, ?, ?, ?, ?, ?)",
        ("/workspace/app.py", "function", "run", "", 1, 2, "hash"),
    )
    old_conn.execute(
        "INSERT INTO edges VALUES (1, ?, ?, ?)",
        ("/workspace/app.py", "util", "IMPORTS"),
    )
    old_conn.commit()

    _migrate_spoke_data(old_conn, str(spoke_path))

    assert old_path.exists()
    assert old_conn.execute("SELECT name FROM code_nodes").fetchall() == [("run",)]

    migrated = sqlite3.connect(spoke_path)
    metadata = dict(migrated.execute("SELECT key, value FROM index_metadata"))
    edge = migrated.execute("SELECT raw_target, resolution FROM edges").fetchone()

    assert metadata == {
        "version": str(INDEX_SCHEMA_VERSION),
        "status": "requires_reindex",
    }
    assert edge == ("util", "legacy")
    assert migrated.execute("SELECT COUNT(*) FROM indexed_files").fetchone()[0] == 0

    migrated.close()
    old_conn.close()


def test_index_readiness_rejects_missing_embeddings(test_db):
    test_db.conn.execute(
        "INSERT INTO code_nodes (file_path, node_type, name) VALUES (?, ?, ?)",
        ("/workspace/app.py", "function", "run"),
    )
    test_db.conn.execute(
        "UPDATE index_metadata SET value = 'ready' WHERE key = 'status'"
    )
    test_db.conn.commit()

    status = test_db.get_index_status()

    assert status["nodes"] == 1
    assert status["vectors"] == 0
    assert status["ready"] is False
    assert test_db.index_needs_rebuild() is True


def test_migrated_spoke_reindexes_and_becomes_searchable(
    tmp_path, monkeypatch, mock_embedding
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    source = workspace / "app.py"
    source.write_text("def run():\n    return 1\n", encoding="utf-8")
    spoke_path = tmp_path / "migrated.db"
    old_conn = sqlite3.connect(tmp_path / "old.db")
    old_conn.execute(
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
    old_conn.execute(
        """
        CREATE TABLE edges (
            id INTEGER PRIMARY KEY,
            from_node TEXT,
            to_node TEXT,
            relation_type TEXT
        )
        """
    )
    old_conn.execute(
        "INSERT INTO code_nodes VALUES (1, ?, 'function', 'stale', '', 1, 1, 'old')",
        (str(source),),
    )
    old_conn.commit()
    _migrate_spoke_data(old_conn, str(spoke_path))

    saved_instance = VectorDBClient._instance
    VectorDBClient._instance = None
    client = VectorDBClient(db_path=str(spoke_path))
    client.workspace_root = str(workspace)
    client.workspace_hash = "migrated"
    monkeypatch.setattr(watcher, "db_client", client)
    monkeypatch.setattr(watcher.embedder, "encode", lambda _text: mock_embedding)

    try:
        assert client.index_needs_rebuild() is True

        watcher.index_workspace(str(workspace))
        matches = client.search_similar(mock_embedding, limit=1)

        assert client.get_index_status()["ready"] is True
        assert matches[0]["name"] == "run"
        assert old_conn.execute("SELECT name FROM code_nodes").fetchone()[0] == "stale"
    finally:
        client.spoke_conn.close()
        client.hub_conn.close()
        old_conn.close()
        VectorDBClient._instance = saved_instance
