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
        vector=[0.1]*384,
        file_hash="correcthash123"
    )
    
    drift_func = mcp_tools["get_drift_report"]
    
    # Case 1: Matching hashes -> no drift
    res_str = drift_func(["src/app.py"], loaded_at="2026-04-12T00:00:00Z", file_hashes={"src/app.py": "correcthash123"})
    res = json.loads(res_str)
    assert res["drift_detected"] is False
    assert len(res["stale_files"]) == 0
    
    # Case 2: Mismatching hashes -> drift
    res_str2 = drift_func(["src/app.py"], loaded_at="2026-04-12T00:00:00Z", file_hashes={"src/app.py": "oldhash999"})
    res2 = json.loads(res_str2)
    assert res2["drift_detected"] is True
    assert len(res2["stale_files"]) == 1
    assert res2["stale_files"][0]["path"] == "src/app.py"

def test_get_dependency_chain(test_db, mcp_tools):
    # Insert code nodes first so they exist when generating the chain
    test_db.upsert_node("A", "class", "A", "", [0.1]*384)
    test_db.upsert_node("B", "class", "B", "", [0.1]*384)
    test_db.upsert_node("C", "class", "C", "", [0.1]*384)

    # Insert A -> B -> C graph
    test_db.upsert_edge("A", "B", "IMPORTS")
    test_db.upsert_edge("B", "C", "IMPORTS")
    
    dep_func = mcp_tools["get_dependency_chain"]
    res_str = dep_func("A")
    res = json.loads(res_str)
    
    assert res["symbol"] == "A"
    assert "B" in res["dependency_chain"]
    assert "C" in res["dependency_chain"]
