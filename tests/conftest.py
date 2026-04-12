import pytest
import tempfile
import time
from visor.db.client import VectorDBClient

@pytest.fixture
def test_db(monkeypatch):
    "Creates an isolated in-memory or tempfile SQLite DB with sqlite-vec loaded."
    # Using a fast temporary file instead of :memory: because sqlite-vec sometimes
    # struggles with loading extensions securely on purely ephemeral URI attachments
    temp_db = tempfile.NamedTemporaryFile(suffix=".db")
    db_path = temp_db.name
    
    # Initialize real schema against temporary path
    client = VectorDBClient(db_path=db_path)
    
    # Monkeypatch the global db_client so all tools use the test db
    import visor.db.client as db_module
    monkeypatch.setattr(db_module, "db_client", client)
    
    # Also patch it in core and context_engine if they imported the instance directly
    import visor.tools.core as core_module
    import visor.tools.context_engine as ce_module
    monkeypatch.setattr(core_module, "db_client", client, raising=False)
    monkeypatch.setattr(ce_module, "db_client", client, raising=False)
    
    yield client
    
    # Teardown
    client.conn.close()
    temp_db.close()
    VectorDBClient._instance = None

@pytest.fixture
def mock_embedding():
    "Returns a fake 384-dimensional vector mimicking all-MiniLM-L6-v2"
    return [0.1] * 384
