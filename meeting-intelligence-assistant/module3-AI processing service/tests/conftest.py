"""Shared pytest fixtures.

The key idea: we never talk to a real LLM in tests. FakeLLM stands in
for LLMService and returns whatever canned JSON payload a test sets.
"""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.dependencies import get_llm_service
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


class FakeLLM:
    """Drop-in replacement for LLMService.

    Tests set `payload`: either a dict to validate against the requested
    response_model, or an Exception instance to simulate an LLM failure.
    """

    def __init__(self, payload=None):
        self.payload = payload
        self.calls: list[tuple[str, str]] = []  # (system_prompt, user_prompt)

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


@pytest.fixture
def fake_llm():
    return FakeLLM()


@pytest.fixture
def client(fake_llm):
    """TestClient for the real app, with the LLM dependency point at FakeLLM."""
    app.dependency_overrides[get_llm_service] = lambda: fake_llm
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()