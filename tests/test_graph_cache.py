import visor.tools.context_engine as context_engine


def test_graph_cache_rebuilds_for_new_workspace_with_same_edge_count(test_db):
    test_db.workspace_hash = "workspace-a"
    test_db.spoke_conn.execute(
        "INSERT INTO edges (from_node, to_node, relation_type, resolution) "
        "VALUES (?, ?, ?, ?)",
        ("alpha", "beta", "IMPORTS", "internal"),
    )
    test_db.spoke_conn.commit()

    first = context_engine._get_cached_edges_graph()
    assert first.has_edge("alpha", "beta")

    test_db.spoke_conn.execute("DELETE FROM edges")
    test_db.spoke_conn.execute(
        "INSERT INTO edges (from_node, to_node, relation_type, resolution) "
        "VALUES (?, ?, ?, ?)",
        ("gamma", "delta", "IMPORTS", "internal"),
    )
    test_db.spoke_conn.commit()
    test_db.workspace_hash = "workspace-b"

    second = context_engine._get_cached_edges_graph()
    assert second.has_edge("gamma", "delta")
    assert not second.has_edge("alpha", "beta")
