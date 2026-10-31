from unittest.mock import Mock

from fastapi.testclient import TestClient
from llama_index.core.schema import NodeRelationship, RelatedNodeInfo, TextNode
from llama_index.core.vector_stores import SimpleVectorStore

import app as kas


def test_delete_removes_both_document_formats_and_preserves_other_meetings(monkeypatch):
    store = SimpleVectorStore()
    for i, doc_id in enumerate(["meeting-7", "meeting:meeting-7", "7", "meeting:7", "meeting-8", "8"]):
        store.add([TextNode(
            id_=str(i), text="chunk", embedding=[1.0, 0.0],
            relationships={NodeRelationship.SOURCE: RelatedNodeInfo(node_id=doc_id)},
        )])
    monkeypatch.setattr(kas.state, "vector_store", store)
    client = TestClient(kas.app)  # No lifespan: no Ollama or database required.
    for _ in range(2):
        response = client.delete("/meetings/meeting-7")
        assert response.status_code == 200
        assert response.json() == {"meeting_id": "meeting-7", "status": "deleted"}
        assert set(store.data.embedding_dict) == {"4", "5"}


def test_demo_ids_do_not_alias_numeric_backend_ids(monkeypatch):
    store = Mock()
    monkeypatch.setattr(kas.state, "vector_store", store)
    assert TestClient(kas.app).delete("/meetings/meeting-001-demo").status_code == 200
    assert [call.args[0] for call in store.delete.call_args_list] == [
        "meeting-001-demo", "meeting:meeting-001-demo",
    ]


def test_unavailable_store_returns_503(monkeypatch):
    monkeypatch.setattr(kas.state, "vector_store", None)
    assert TestClient(kas.app).delete("/meetings/meeting-7").status_code == 503


def test_store_failure_is_not_reported_as_success(monkeypatch):
    store = Mock()
    store.delete.side_effect = RuntimeError("database offline")
    monkeypatch.setattr(kas.state, "vector_store", store)
    assert TestClient(kas.app).delete("/meetings/meeting-7").status_code == 503
