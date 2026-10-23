"""Live integration tests: module3 -> KAS HTTP API -> pgvector -> Ollama.

Skipped unless INTEGRATION=1. Preconditions (all must be running):
  1. Postgres with pgvector: ``docker start meeting-db`` (:5432, see
     module2-backend/README.md)
  2. KAS HTTP API on :8002 - run ``uvicorn app:app --port 8002`` in the
     ``module4-knowledge assistant service`` folder
  3. Ollama with qwen2.5:7b-instruct + nomic-embed-text

These tests use the REAL dependency wiring (no FakeLLM/FakeKasClient) and
therefore make real HTTP calls. Runtime depends on the chunk threshold: the
conductor runs the long-transcript test with CHUNK_THRESHOLD_CHARS=4000 by
default (~5-10 min); a direct run uses the production 20,000 default.

Run (PowerShell):
    $env:INTEGRATION='1'; python -m pytest tests/test_integration_live.py -v
Or through the conductor (checks prerequisites first):
    python run_tests.py --tier live
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

# The conductor lowers this via CHUNK_THRESHOLD_CHARS to keep runs practical.
CHUNK_THRESHOLD = int(os.getenv("CHUNK_THRESHOLD_CHARS", "20000"))

_LONG_LINE = (
    "Speaker {i} [{h:02d}:{m:02d}:00]: Okay, next point - about the deployment, "
    "the database connection pooling, and the timeline for the pgvector rollout, "
    "plus who owns the frontend search UI next week.\n"
)


def _build_long_transcript() -> str:
    """A transcript just over the configured chunk threshold."""
    lines: list[str] = []
    length = 0
    index = 0
    while length <= CHUNK_THRESHOLD + 500:
        line = _LONG_LINE.format(i=index, h=index // 60, m=index % 60)
        lines.append(line)
        length += len(line)
        index += 1
    return "".join(lines)


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
    transcript = _build_long_transcript()
    assert len(transcript) > CHUNK_THRESHOLD

    response = live_client.post(
        "/summarize",
        json={"meeting_id": "live-long-transcript", "transcript": transcript},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["summary"].strip()
    assert isinstance(body["key_points"], list)
