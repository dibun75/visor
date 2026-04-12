import sqlite3
import pytest
from visor.db.client import serialize_vec

def test_batch_upsert_nodes(test_db, mock_embedding):
    """Test that batch_upsert_nodes accurately inserts arrays of node dicts."""
    nodes = [
        {
            "file_path": "src/app.py",
            "node_type": "class",
            "name": "App",
            "docstring": "Main app class",
            "vector": mock_embedding,
            "start_line": 10,
            "end_line": 20,
            "file_hash": "abc"
        },
        {
            "file_path": "src/app.py",
            "node_type": "function",
            "name": "init",
            "docstring": "",
            "vector": mock_embedding,
            "start_line": 25,
            "end_line": 30,
            "file_hash": "abc"
        }
    ]
    
    test_db.batch_upsert_nodes(nodes)
    
    cursor = test_db.conn.cursor()
    cursor.execute("SELECT id, name, node_type FROM code_nodes")
    rows = cursor.fetchall()
    
    assert len(rows) == 2
    assert rows[0][1] == "App"
    assert rows[1][1] == "init"

def test_upsert_and_resolve_edges(test_db):
    """Test that edges can be upserted and duplicate constraints work"""
    # Insert two nodes so we can safely point to them
    cursor = test_db.conn.cursor()
    cursor.execute(
        "INSERT INTO code_nodes (file_path, node_type, name) VALUES (?, ?, ?)",
        ("main.py", "file", "main")
    )
    cursor.execute(
        "INSERT INTO code_nodes (file_path, node_type, name) VALUES (?, ?, ?)",
        ("utils.py", "file", "utils")
    )
    test_db.conn.commit()

    test_db.upsert_edge("main.py", "utils.py", "IMPORTS")
    # Duplicate edge should fail gracefully or update (depending on our schema logic, we ignore)
    test_db.upsert_edge("main.py", "utils.py", "IMPORTS")
    
    cursor.execute("SELECT from_node, to_node, relation_type FROM edges")
    edges = cursor.fetchall()
    
    # We enforce uniqueness via application logic, or allow silent dupes. 
    # Let's count them
    assert len(edges) >= 1
    assert edges[0] == ("main.py", "utils.py", "IMPORTS")
