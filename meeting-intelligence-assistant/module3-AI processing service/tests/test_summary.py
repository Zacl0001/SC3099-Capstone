"""Tests for the /summarize endpoint and summarization flow."""

from app.schemas.summary import SummaryResponse
from app.services.exceptions import LLMConnectionError
from tests.conftest import SAMPLE_TRANSCRIPT

PAYLOAD = {
    "summary": "The team agreed on an October 1 release.",
    "key_points": ["Release date set", "Budget approved", "Mobile app dropped"],
}


def test_summarize_endpoint_returns_validated_response(client, fake_llm):
    fake_llm.payload = PAYLOAD

    response = client.post("/summarize", json={"meeting_id": "1", "transcript": SAMPLE_TRANSCRIPT})

    assert response.status_code == 200
    body = response.json()
    assert body["summary"] == PAYLOAD["summary"]
    assert body["key_points"] == PAYLOAD["key_points"]
    # Pydantic validated and returned an actual SummaryResponse instance.
    assert SummaryResponse(**body) == SummaryResponse(**PAYLOAD)


def test_summarize_passes_transcript_into_prompt(client, fake_llm):
    fake_llm.payload = PAYLOAD

    client.post("/summarize", json={"meeting_id": "1", "transcript": SAMPLE_TRANSCRIPT})

    assert fake_llm.calls, "endpoint should have called the LLM"
    _, user_prompt = fake_llm.calls[0]
    assert SAMPLE_TRANSCRIPT in user_prompt


def test_summarize_rejects_empty_transcript(client, fake_llm):
    fake_llm.payload = PAYLOAD

    response = client.post("/summarize", json={"meeting_id": "1", "transcript": ""})

    assert response.status_code == 422


def test_summarize_maps_llm_failure_to_502(client, fake_llm):
    fake_llm.payload = LLMConnectionError("Cannot reach LLM at http://localhost:11434/v1")

    response = client.post("/summarize", json={"meeting_id": "1", "transcript": SAMPLE_TRANSCRIPT})

    assert response.status_code == 502


async def test_summarization_service_returns_schema(fake_llm):
    from app.services import summarization_service

    fake_llm.payload = PAYLOAD
    result = await summarization_service.summarize(SAMPLE_TRANSCRIPT, fake_llm)

    assert isinstance(result, SummaryResponse)
    assert result.summary == PAYLOAD["summary"]