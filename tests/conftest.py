import os
import shutil
import tempfile
from pathlib import Path

import pytest

_TEST_VISOR_HOME = tempfile.mkdtemp(prefix="visor-tests-")
os.environ["VISOR_HOME"] = _TEST_VISOR_HOME
os.environ.pop("WORKSPACE_ROOT", None)

from visor.db.client import VectorDBClient  # noqa: E402


def pytest_sessionfinish():
    shutil.rmtree(_TEST_VISOR_HOME, ignore_errors=True)


@pytest.fixture
def test_db(monkeypatch):
    """Create an isolated SQLite hub and spoke with sqlite-vec loaded."""
    with tempfile.TemporaryDirectory(prefix="visor-db-") as temp_dir:
        db_path = str(Path(temp_dir) / "graph.db")

        monkeypatch.setenv("VISOR_RETRIEVAL_MODE", "semantic")
        VectorDBClient._instance = None
        client = VectorDBClient(db_path=db_path)

        import visor.db.client as db_module
        import visor.tools.context_engine as ce_module
        import visor.tools.core as core_module

        monkeypatch.setattr(db_module, "db_client", client)
        monkeypatch.setattr(core_module, "db_client", client, raising=False)
        monkeypatch.setattr(ce_module, "db_client", client, raising=False)
        monkeypatch.setattr(core_module, "_graph_cache", None, raising=False)
        monkeypatch.setattr(core_module, "_graph_cache_key", None, raising=False)
        monkeypatch.setattr(ce_module, "_ctx_graph_cache", None, raising=False)
        monkeypatch.setattr(ce_module, "_ctx_graph_cache_key", None, raising=False)

        yield client

        client.spoke_conn.close()
        client.hub_conn.close()
        VectorDBClient._instance = None


@pytest.fixture
def mock_embedding():
    """Return a fake 384-dimensional all-MiniLM-L6-v2 vector."""
    return [0.1] * 384
