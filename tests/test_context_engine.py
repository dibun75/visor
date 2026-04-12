from visor.tools.context_engine import _score_node, _estimate_tokens, _classify_intent, _generate_reasoning, INTENT_PROFILES

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
    score, signals = _score_node(
        node=mock_node,
        query_tokens=query_tokens,
        anchor_file="src/auth.py",
        anchor_embedding_distance=0.5,
        hop_map=hop_map,
        recency_map={"src/auth.py": 1.0},
        weights=INTENT_PROFILES["DEFAULT"]
    )
    
    # Hand-verify the expected DEFAULT score:
    # EXACT_MATCH = 1.0 -> 1.0 * 1.0 = 1.0
    # SAME_FILE = 0.7 -> 1.0 * 0.7 = 0.7
    # EMBEDDING = 0.5 -> sim: max(0.0, 1.0 - (0.5/2.0)) = 0.75 -> 0.5 * 0.75 = 0.375
    # DEPENDENCY = 0.3 -> dep: 1.0 / (1.0 + 0) = 1.0 -> 0.3 * 1.0 = 0.3
    # RECENCY = 0.2 -> recency: 1.0 -> 0.2 * 1.0 = 0.2
    # Total = 1.0 + 0.7 + 0.375 + 0.3 + 0.2 = 2.575
    
    assert score == 2.575

def test_classify_intent():
    assert _classify_intent("How do I fix this null pointer exception") == "BUG_FIX"
    assert _classify_intent("We need to refactor the Auth manager") == "REFACTOR"
    assert _classify_intent("Please explain the architecture of the graph") == "EXPLAIN"
    assert _classify_intent("Add a new feature to the UI") == "DEFAULT"

def test_skill_strategy_override():
    """Verify that skill scoring_bias overrides default weights."""
    mock_node = {
        "name": "DbClient",
        "file_path": "src/db.py",
        "distance": 0.4
    }
    # Simulate a skill with custom scoring bias
    custom_weights = dict(INTENT_PROFILES["BUG_FIX"])
    custom_weights["recency"] = 2.0  # Override recency to 2.0

    score_default, _ = _score_node(
        node=mock_node,
        query_tokens=["dbclient"],
        anchor_file="src/db.py",
        anchor_embedding_distance=0.4,
        hop_map={"src/db.py": 0},
        recency_map={"src/db.py": 0.5},
        weights=INTENT_PROFILES["BUG_FIX"]
    )

    score_skill, _ = _score_node(
        node=mock_node,
        query_tokens=["dbclient"],
        anchor_file="src/db.py",
        anchor_embedding_distance=0.4,
        hop_map={"src/db.py": 0},
        recency_map={"src/db.py": 0.5},
        weights=custom_weights
    )

    # The skill version with recency=2.0 vs default recency=1.0 should score higher
    assert score_skill > score_default

def test_reasoning_generation():
    """Verify human-readable reasoning strings are generated."""
    signals_full = {
        "exact_match": 1.0,
        "proximity": 0.7,
        "embedding": 0.375,
        "dependency": 0.3,
        "recency": 0.2,
    }
    reasons = _generate_reasoning(signals_full)
    assert "Matched query token in symbol name" in reasons
    assert "Co-located in same file as top semantic hit" in reasons
    assert "Recently modified file (boosted)" in reasons
    assert "Reachable via dependency chain" in reasons

    # Node with only embedding match
    signals_minimal = {
        "exact_match": 0.0,
        "proximity": 0.0,
        "embedding": 0.5,
        "dependency": 0.0,
        "recency": 0.0,
    }
    reasons_minimal = _generate_reasoning(signals_minimal)
    assert len(reasons_minimal) == 1
    assert "Semantic similarity" in reasons_minimal[0]

def test_token_metrics():
    """Verify token estimation math."""
    text = "a" * 400  # 400 chars → 100 tokens
    assert _estimate_tokens(text) == 100
    assert _estimate_tokens("ab") == 1  # Minimum 1
