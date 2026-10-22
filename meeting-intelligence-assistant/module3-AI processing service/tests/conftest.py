"""Shared pytest fixtures.

The key idea: we never talk to a real LLM or a real KAS in tests.
FakeLLM and FakeKasClient stand in for the HTTP clients and return
whatever canned data a test sets.
"""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.dependencies import get_kas_client, get_llm_service
from app.main import app
from app.services.exceptions import LLMInvalidResponse

SAMPLE_TRANSCRIPT = """
Alice: Let's talk about the Q3 release timeline.
Bob: We should target October 1st.
Alice: Agreed, October 1st works. Carol, can you prepare the release notes?
Carol: Sure, I'll have them done by Friday.
Alice: We've decided to drop the mobile app feature from this release.
Bob: OK, mobile app goes to Q4.
Alice: Let's move on to the budget.
Carol: The budget is approved at 50k.
"""

# Short but valid structured payloads reused across tests.
SUMMARY_PAYLOAD = {
    "summary": "The team agreed on an October 1 release.",
    "key_points": ["Release date set", "Budget approved", "Mobile app dropped"],
}
ACTION_PAYLOAD = {
    "action_items": [
        {
            "task": "Prepare the release notes",
            "assignee": "Carol",
            "deadline": "Friday",
            "evidence": "Carol: I'll have them done by Friday.",
            "timestamp": None,
        }
    ]
}


class FakeLLM:
    """Drop-in replacement for LLMService.

    - `payload`: a dict validated against the requested response_model for
      generate_structured(). Set an Exception to simulate an LLM failure.
    - `text_payload`: the raw text returned by generate() (used by /chat).
    """

    def __init__(self, payload=None, text_payload=None):
        self.payload = payload
        self.text_payload = text_payload
        self.calls: list[tuple[str, str]] = []  # (system_prompt, user_prompt)

    async def generate(self, system_prompt, user_prompt) -> str:
        self.calls.append((system_prompt, user_prompt))
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.text_payload or ""

    async def generate_structured(self, system_prompt, user_prompt, response_model):
        self.calls.append((system_prompt, user_prompt))
        if isinstance(self.payload, Exception):
            raise self.payload
        # Mirror the real LLMService: validation failures surface as
        # LLMInvalidResponse (permanent, -> 502), not a raw 500.
        try:
            return response_model.model_validate(self.payload)
        except ValidationError as exc:
            raise LLMInvalidResponse("LLM output failed Pydantic validation") from exc


class FakeKasClient:
    """Drop-in replacement for KASClient.

    - `search_results`: list[RetrievedChunk] returned by search().
    - `chunks`: list[str] returned by chunk().
    - `search_raises` / `chunk_raises`: Exception to raise instead.
    """

    def __init__(
        self,
        search_results=None,
        chunks=None,
        search_raises=None,
        chunk_raises=None,
    ):
        self.search_results = list(search_results or [])
        self.chunks = list(chunks or [])
        self.search_raises = search_raises
        self.chunk_raises = chunk_raises
        self.search_calls: list[tuple[str | None, str, int | None]] = []
        self.chunk_calls: list[tuple[str | None, str]] = []

    async def search(self, meeting_id, query, top_k=None):
        self.search_calls.append((meeting_id, query, top_k))
        if self.search_raises is not None:
            raise self.search_raises
        return list(self.search_results)

    async def chunk(self, meeting_id, transcript):
        self.chunk_calls.append((meeting_id, transcript))
        if self.chunk_raises is not None:
            raise self.chunk_raises
        return list(self.chunks)


@pytest.fixture
def fake_llm():
    return FakeLLM()


@pytest.fixture
def fake_kas():
    return FakeKasClient()


@pytest.fixture
def client(fake_llm, fake_kas):
    """TestClient for the real app, with LLM + KAS dependencies pointed at fakes."""
    app.dependency_overrides[get_llm_service] = lambda: fake_llm
    app.dependency_overrides[get_kas_client] = lambda: fake_kas
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()