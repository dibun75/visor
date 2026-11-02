import pytest
import json
from visor.tools.core import register_tools
from unittest.mock import MagicMock


@pytest.fixture
def mcp_tools():
    """Extracts all tools registered to the MCP server for direct testing."""
    mock_mcp = MagicMock()
    tool_dict = {}

    # We mock the @mcp.tool() decorator so we can grab the underlying functions
    def mock_tool():
        def decorator(func):
            tool_dict[func.__name__] = func
            return func

        return decorator

    mock_mcp.tool = mock_tool
    register_tools(mock_mcp)

    return tool_dict


def test_get_drift_report_hash_based(test_db, mcp_tools):
    # Insert node
    test_db.upsert_node(
        file_path="src/app.py",
        node_type="file",
        name="app",
        docstring="",
        vector=[0.1] * 384,
        file_hash="correcthash123",
    )

    drift_func = mcp_tools["get_drift_report"]

    # Case 1: Matching hashes -> no drift
    res_str = drift_func(
        ["src/app.py"],
        loaded_at="2026-04-12T00:00:00Z",
        file_hashes={"src/app.py": "correcthash123"},
    )
    res = json.loads(res_str)
    assert res["drift_detected"] is False
    assert len(res["stale_files"]) == 0

    # Case 2: Mismatching hashes -> drift
    res_str2 = drift_func(
        ["src/app.py"],
        loaded_at="2026-04-12T00:00:00Z",
        file_hashes={"src/app.py": "oldhash999"},
    )
    res2 = json.loads(res_str2)
    assert res2["drift_detected"] is True
    assert len(res2["stale_files"]) == 1
    assert res2["stale_files"][0]["path"] == "src/app.py"


def test_get_dependency_chain(test_db, mcp_tools):
    # Insert code nodes first so they exist when generating the chain
    test_db.upsert_node("A", "class", "A", "", [0.1] * 384)
    test_db.upsert_node("B", "class", "B", "", [0.1] * 384)
    test_db.upsert_node("C", "class", "C", "", [0.1] * 384)

    # Insert A -> B -> C graph
    test_db.upsert_edge("A", "B", "IMPORTS")
    test_db.upsert_edge("B", "C", "IMPORTS")

    dep_func = mcp_tools["get_dependency_chain"]
    res_str = dep_func("A")
    res = json.loads(res_str)

    assert res["symbol"] == "A"
    assert "B" in res["dependency_chain"]
    assert "C" in res["dependency_chain"]


def test_graph_tools_use_verified_import_direction(test_db, mcp_tools):
    for path in ("app.py", "service.py", "model.py"):
        test_db.upsert_node(path, "function", path, "", [0.1] * 384)

    test_db.upsert_edge("app.py", "service.py", "IMPORTS")
    test_db.upsert_edge("service.py", "model.py", "IMPORTS")

    route = json.loads(mcp_tools["trace_route"]("app.py", "model.py"))
    impact = json.loads(mcp_tools["impact_analysis"]("model.py"))
    architecture = json.loads(mcp_tools["get_architecture_map"]())

    assert route["path"] == ["app.py", "service.py", "model.py"]
    assert set(impact["blast_radius"]) == {"app.py", "service.py"}

    paths_by_id = {node["id"]: node["file_path"] for node in architecture["nodes"]}
    architecture_edges = {
        (paths_by_id[edge["source"]], paths_by_id[edge["target"]])
        for edge in architecture["edges"]
    }
    assert ("app.py", "service.py") in architecture_edges
    assert ("service.py", "model.py") in architecture_edges


def test_dependency_chain_accepts_exact_file_path(test_db, mcp_tools):
    test_db.upsert_node("app.py", "function", "run", "", [0.1] * 384)
    test_db.upsert_node("util.py", "function", "helper", "", [0.1] * 384)
    test_db.upsert_edge("app.py", "util.py", "IMPORTS")

    result = json.loads(mcp_tools["get_dependency_chain"]("app.py"))

    assert result["source_file"] == "app.py"
    assert result["dependency_chain"] == ["util.py"]


def test_add_custom_skill_rejects_unknown_strategy_keys(test_db, mcp_tools):
    result = json.loads(
        mcp_tools["add_custom_skill"](
            "broken",
            "Invalid strategy",
            "Test invalid configuration.",
            json.dumps({"scoring_bias": {"dependency": 2.0}}),
        )
    )

    assert result["success"] is False
    assert "dependency" in result["error"]
    assert test_db.get_skill_by_name("broken") is None


def test_custom_skill_tool_priority_drives_recommended_next(test_db, mcp_tools):
    strategy = {
        "intent_override": "BUG_FIX",
        "scoring_bias": {"dep": 1.5, "recency": 0.5},
        "tool_priority": ["impact_analysis", "get_dependency_chain"],
    }
    added = json.loads(
        mcp_tools["add_custom_skill"](
            "triage",
            "Triage a change",
            "Inspect impact before editing.",
            json.dumps(strategy),
        )
    )
    assert added["success"] is True

    stored = test_db.get_skill_by_name("triage")
    assert stored is not None
    assert stored["strategy"] == strategy

    result = json.loads(mcp_tools["build_context"]("missing symbol", "triage"))
    assert result["recommended_next"] == [
        "impact_analysis",
        "get_dependency_chain",
    ]


@pytest.mark.parametrize(
    "strategy",
    [
        "not json",
        "[]",
        json.dumps({"intent_override": "NOT_REAL"}),
        json.dumps({"scoring_bias": {"dep": -1}}),
        json.dumps({"tool_priority": "impact_analysis"}),
    ],
)
def test_add_custom_skill_rejects_invalid_strategies(test_db, mcp_tools, strategy):
    result = json.loads(
        mcp_tools["add_custom_skill"](
            "invalid",
            "Invalid strategy",
            "Test invalid configuration.",
            strategy,
        )
    )

    assert result["success"] is False
    assert result["error"]
    assert test_db.get_skill_by_name("invalid") is None
