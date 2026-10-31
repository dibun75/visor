from visor.tools.context_engine import (
    _score_node,
    _estimate_tokens,
    _read_snippet,
    _classify_intent,
    _generate_reasoning,
    INTENT_PROFILES,
)


def test_estimate_tokens():
    text = "def my_func(): pass"
    tokens = _estimate_tokens(text)
    assert tokens == len(text) // 4
    assert _estimate_tokens("") == 1


def test_score_node():
    mock_node = {
        "name": "AuthManager",
        "file_path": "src/auth.py",
        "distance": 0.5,  # 0.5 raw L2
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
        weights=INTENT_PROFILES["DEFAULT"],
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
    mock_node = {"name": "DbClient", "file_path": "src/db.py", "distance": 0.4}
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
        weights=INTENT_PROFILES["BUG_FIX"],
    )

    score_skill, _ = _score_node(
        node=mock_node,
        query_tokens=["dbclient"],
        anchor_file="src/db.py",
        anchor_embedding_distance=0.4,
        hop_map={"src/db.py": 0},
        recency_map={"src/db.py": 0.5},
        weights=custom_weights,
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
    assert reasons_minimal[0] == "Semantic similarity (score: 0.5)"


def test_lexical_retrieval_is_not_described_as_semantic_similarity():
    """A lexical hit must not turn a missing vector distance into similarity."""
    weights = INTENT_PROFILES["DEFAULT"]
    lexical = {
        "name": "resolve_local_workspace",
        "file_path": "src/visor/workspace.py",
        "retrieval": "lexical",
        "distance": 1.0,
    }
    other = {
        "name": "unrelated_helper",
        "file_path": "src/visor/other.py",
        "retrieval": "lexical",
        "distance": 1.0,
    }
    kwargs = {
        "query_tokens": ["resolve", "local", "workspace"],
        "anchor_file": "src/visor/workspace.py",
        "anchor_embedding_distance": 0.0,
        "hop_map": {"src/visor/workspace.py": 0, "src/visor/other.py": 2},
        "recency_map": {},
        "weights": weights,
    }
    lexical_score, lexical_signals = _score_node(node=lexical, **kwargs)
    other_score, other_signals = _score_node(node=other, **kwargs)

    assert lexical_signals["embedding"] == 0.0
    assert other_signals["embedding"] == 0.0
    assert lexical_score > other_score

    # The old placeholder distance of 1.0 added the same embed offset to every
    # lexical candidate, so dropping it does not change their order.
    placeholder_offset = weights["embed"] * 0.5
    assert round(lexical_score + placeholder_offset, 4) > round(
        other_score + placeholder_offset, 4
    )

    reasons = _generate_reasoning(lexical_signals, retrieval="lexical")
    assert "Matched query token in symbol name" in reasons
    assert "Co-located in same file as top lexical hit" in reasons
    assert all("Semantic similarity" not in reason for reason in reasons)
    assert _generate_reasoning(
        {
            "exact_match": 0,
            "proximity": 0,
            "embedding": 0,
            "dependency": 0,
            "recency": 0,
        },
        retrieval="lexical",
    ) == ["Lexical match"]


def test_semantic_distance_keeps_similarity_reasoning():
    node = {
        "name": "resolve_local_workspace",
        "file_path": "src/visor/workspace.py",
        "distance": 0.5,
    }
    score, signals = _score_node(
        node=node,
        query_tokens=["resolve"],
        anchor_file="src/visor/other.py",
        anchor_embedding_distance=0.5,
        hop_map={},
        recency_map={},
        weights=INTENT_PROFILES["DEFAULT"],
    )
    assert signals["embedding"] == 0.375
    assert score > 0
    reasons = _generate_reasoning(signals, retrieval="semantic")
    assert "Semantic similarity (score: 0.375)" in reasons
    assert all("lexical" not in reason.lower() for reason in reasons)


def test_token_metrics():
    """Verify token estimation math."""
    text = "a" * 400  # 400 chars → 100 tokens
    assert _estimate_tokens(text) == 100


def test_read_snippet_uses_one_based_inclusive_lines(tmp_path):
    source = tmp_path / "sample.py"
    source.write_text("first\nsecond\nthird\nlast\n", encoding="utf-8")

    assert _read_snippet(str(source), 1, 1) == "first\n"
    assert _read_snippet(str(source), 2, 3) == "second\nthird\n"
    assert _read_snippet(str(source), 4, 4) == "last\n"
    assert _read_snippet(str(source), 0, 1) == ""


def test_read_snippet_preserves_unicode_and_truncates_boundaries(tmp_path):
    source = tmp_path / "unicode.py"
    source.write_text(
        "α\nβ\nγ\nδ\nε\nζ\n",
        encoding="utf-8",
    )

    snippet = _read_snippet(str(source), 1, 6, max_lines=4)

    assert snippet.startswith("α\nβ\n")
    assert "2 lines truncated" in snippet
    assert snippet.endswith("ε\nζ\n")
    assert _estimate_tokens("ab") == 1  # Minimum 1
