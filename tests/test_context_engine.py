from visor.tools.context_engine import _score_node, _estimate_tokens, _classify_intent, INTENT_PROFILES

def test_estimate_tokens():
    text = "def my_func(): pass"
    tokens = _estimate_tokens(text)
    assert tokens == len(text) // 4
    assert _estimate_tokens("") == 1

def test_score_node():
    mock_node = {
        "name": "AuthManager",
        "file_path": "src/auth.py",
        "distance": 0.5  # 0.5 raw L2
    }
    query_tokens = ["auth", "manager"]
    hop_map = {"src/auth.py": 0}  # 0 hops away
    
    score = _score_node(
        node=mock_node,
        query_tokens=query_tokens,
        anchor_file="src/auth.py",
        anchor_embedding_distance=0.5,
        hop_map=hop_map,
        weights=INTENT_PROFILES["DEFAULT"]
    )
    
    # Hand-verify the expected DEFAULT score:
    # EXACT_MATCH = 1.0 -> 1.0 * 1.0 = 1.0
    # SAME_FILE = 0.7 -> 1.0 * 0.7 = 0.7
    # EMBEDDING = 0.5 -> sim: max(0.0, 1.0 - (0.5/2.0)) = 0.75 -> 0.5 * 0.75 = 0.375
    # DEPENDENCY = 0.3 -> dep: 1.0 / (1.0 + 0) = 1.0 -> 0.3 * 1.0 = 0.3
    # Total = 1.0 + 0.7 + 0.375 + 0.3 = 2.375
    
    assert score == 2.375

def test_classify_intent():
    assert _classify_intent("How do I fix this null pointer exception") == "BUG_FIX"
    assert _classify_intent("We need to refactor the Auth manager") == "REFACTOR"
    assert _classify_intent("Please explain the architecture of the graph") == "EXPLAIN"
    assert _classify_intent("Add a new feature to the UI") == "DEFAULT"
