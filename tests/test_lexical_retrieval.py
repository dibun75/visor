import pytest

from visor.db.embeddings import retrieval_mode
from visor.parser import watcher


def test_lexical_indexing_never_loads_embedding_model(
    tmp_path, test_db, monkeypatch
):
    source = tmp_path / "service.py"
    source.write_text(
        "def resolve_workspace():\n    return 'ready'\n", encoding="utf-8"
    )
    monkeypatch.setenv("VISOR_RETRIEVAL_MODE", "lexical")
    monkeypatch.setattr(watcher, "db_client", test_db)
    monkeypatch.setattr(
        watcher.embedder,
        "encode",
        lambda _text: (_ for _ in ()).throw(AssertionError("embedding used")),
    )
    test_db.workspace_root = str(tmp_path)

    watcher.index_file(str(source), skip_changelog=True)

    assert retrieval_mode() == "lexical"
    assert test_db.get_index_status()["vectors"] == 0
    assert test_db.search_lexical("resolve workspace")
    test_db.mark_index_ready()
    assert test_db.get_index_status()["ready"] is True


def test_semantic_mode_requires_explicit_dependency(monkeypatch):
    from visor.db.embeddings import EmbeddingUnavailableError, SemanticEmbedder

    monkeypatch.setattr("visor.db.embeddings.semantic_dependencies_available", lambda: False)
    SemanticEmbedder._instance = None
    with pytest.raises(EmbeddingUnavailableError):
        SemanticEmbedder().encode("search")
