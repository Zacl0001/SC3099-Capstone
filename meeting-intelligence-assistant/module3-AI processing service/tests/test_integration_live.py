"""Live integration tests: module3 -> KAS HTTP API -> pgvector -> Ollama.

Skipped unless INTEGRATION=1. Preconditions (all must be running):
  1. Postgres with pgvector: ``docker compose up -d`` in the KAS folder (:5433)
  2. KAS HTTP API on :8002 
  3. Ollama with qwen2.5:7b-instruct + nomic-embed-text

These tests use the REAL dependency wiring (no FakeLLM/FakeKasClient) and
therefore make real HTTP calls. Runtime is minutes: each /chat call runs a
~1-2 min CPU LLM generation and the long-transcript test takes ~10 minutes.

Run:  set INTEGRATION=1 && python -m pytest tests/test_integration_live.py -v
"""

import json
import os
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    os.getenv("INTEGRATION") != "1",
    reason="set INTEGRATION=1 (with KAS + Ollama running) to run live tests",
)

KAS_URL = os.getenv("KAS_BASE_URL", "http://localhost:8002")
MEETING_ID = "meeting-001-kas-failure-debug"
NOT_FOUND_MESSAGE = "I could not find this information in the meeting transcript."

_MEETING_FILE = (
    Path(__file__).resolve().parent.parent.parent
    / "module4-knowledge assistant service"
    / "data"
    / "sample_meeting1.json"
)

# Over the 20k chunk threshold, so /summarize must use the /chunk map path.
_LONG_LINE = (
    "Speaker {i} [{h:02d}:{m:02d}:00]: Okay, next point - about the deployment, "
    "the database connection pooling, and the timeline for the pgvector rollout, "
    "plus who owns the frontend search UI next week.\n"
)


@pytest.fixture(scope="session", autouse=True)
def ingest_fixture_meeting():
    """Ingest sample_meeting1.json through the KAS HTTP API (idempotent)."""
    meeting = json.loads(_MEETING_FILE.read_text(encoding="utf-8"))
    response = httpx.post(f"{KAS_URL}/ingest", json=meeting, timeout=180.0)
    assert response.status_code == 200, response.text
    assert response.json()["meeting_id"] == MEETING_ID


@pytest.fixture()
def live_client():
    """TestClient with the REAL lifespan (real LLM + KAS clients)."""
    from app.main import app

    with TestClient(app) as client:
        yield client


def test_chat_returns_grounded_answer_with_citations(live_client):
    response = live_client.post(
        "/chat",
        json={
            "meeting_id": MEETING_ID,
            "question": "Why was the database connection limit being exhausted?",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] != NOT_FOUND_MESSAGE
    assert "connection" in body["answer"].lower()
    assert body["citations"], "grounded answer must carry at least one citation"
    citation = body["citations"][0]
    assert citation["speaker"], "citation must map back to a speaker"
    assert citation["timestamp"], "citation must map back to a timestamp"


def test_chat_unknown_meeting_skips_llm(live_client):
    response = live_client.post(
        "/chat",
        json={"meeting_id": "meeting-999-nonexistent", "question": "What was decided?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == NOT_FOUND_MESSAGE
    assert body["citations"] == []


def test_long_summarize_uses_chunk_map_path(live_client):
    transcript = "".join(
        _LONG_LINE.format(i=i, h=i // 60, m=i % 60) for i in range(120)
    )
    assert len(transcript) > 20000

    response = live_client.post(
        "/summarize",
        json={"meeting_id": "live-long-transcript", "transcript": transcript},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["summary"].strip()
    assert isinstance(body["key_points"], list)
