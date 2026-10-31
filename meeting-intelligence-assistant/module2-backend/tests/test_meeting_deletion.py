from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import meetings
from app.services import knowledge_service, meeting_service
from app.services.knowledge_service import KnowledgeServiceError


@pytest.fixture
def stored_meeting(tmp_path, monkeypatch):
    monkeypatch.setattr(meeting_service, "STORAGE_ROOT", tmp_path)
    file = tmp_path / "transcript.txt"
    file.write_text("Alex: Hello")
    db = Mock()
    db.scalar.side_effect = [SimpleNamespace(id=7), SimpleNamespace(storage_key=file.name)]
    return db, file


def test_cleanup_precedes_database_deletion(stored_meeting, monkeypatch):
    db, file = stored_meeting
    events = []
    cleanup = Mock(side_effect=lambda _: events.append("chunks"))
    monkeypatch.setattr(knowledge_service, "delete_meeting_chunks", cleanup)
    db.execute.side_effect = lambda _: events.append("row")
    db.commit.side_effect = lambda: events.append("commit")

    assert meeting_service.delete_meeting(db, 1, 7)
    cleanup.assert_called_once_with("meeting-7")
    assert events == ["chunks", "row", "row", "commit"]
    assert not file.exists()


def test_cleanup_failure_preserves_rows_and_file(stored_meeting, monkeypatch):
    db, file = stored_meeting
    monkeypatch.setattr(knowledge_service, "delete_meeting_chunks", Mock(side_effect=KnowledgeServiceError("offline")))
    with pytest.raises(KnowledgeServiceError):
        meeting_service.delete_meeting(db, 1, 7)
    db.execute.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()
    assert file.exists()


def test_database_failure_keeps_file(stored_meeting, monkeypatch):
    db, file = stored_meeting
    monkeypatch.setattr(knowledge_service, "delete_meeting_chunks", Mock())
    db.commit.side_effect = RuntimeError("database unavailable")
    with pytest.raises(RuntimeError):
        meeting_service.delete_meeting(db, 1, 7)
    db.rollback.assert_called_once()
    assert file.exists()


def test_missing_or_unowned_meeting_never_calls_kas(monkeypatch):
    cleanup = Mock()
    monkeypatch.setattr(knowledge_service, "delete_meeting_chunks", cleanup)
    db = Mock()
    db.scalar.return_value = None
    assert not meeting_service.delete_meeting(db, 1, 7)
    cleanup.assert_not_called()
    db.execute.assert_not_called()


@pytest.mark.parametrize("status", [200, 204, 503, 307])
def test_kas_delete_client_checks_response(status, monkeypatch):
    delete = Mock(return_value=httpx.Response(status))
    monkeypatch.setattr(httpx, "delete", delete)
    if status >= 300:
        with pytest.raises(KnowledgeServiceError):
            knowledge_service.delete_meeting_chunks("meeting-7")
    else:
        knowledge_service.delete_meeting_chunks("meeting-7")
    assert delete.call_args.args[0].endswith("/meetings/meeting-7")


def test_kas_delete_client_wraps_connection_failure(monkeypatch):
    monkeypatch.setattr(httpx, "delete", Mock(side_effect=httpx.ConnectError("offline")))
    with pytest.raises(KnowledgeServiceError):
        knowledge_service.delete_meeting_chunks("meeting-7")


def test_delete_endpoint_returns_retryable_503(monkeypatch):
    app = FastAPI()
    app.include_router(meetings.router)
    app.dependency_overrides[meetings.get_current_user] = lambda: SimpleNamespace(id=1)
    app.dependency_overrides[meetings.get_db] = lambda: Mock()
    monkeypatch.setattr(meetings, "delete_meeting", Mock(side_effect=KnowledgeServiceError("meeting kept; retry")))
    response = TestClient(app).delete("/api/meetings/7")
    assert response.status_code == 503
    assert "retry" in response.json()["detail"]
