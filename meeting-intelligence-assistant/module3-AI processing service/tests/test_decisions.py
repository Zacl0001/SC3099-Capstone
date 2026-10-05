"""Tests for the /decisions endpoint."""

from app.schemas.decision import DecisionListResponse
from tests.conftest import SAMPLE_TRANSCRIPT

PAYLOAD = {
    "decisions": [
        {
            "decision": "Release date set to October 1st",
            "evidence": "Alice: Agreed, October 1st works.",
            "timestamp": None,
        }
    ]
}


def test_decisions_endpoint_returns_decisions(client, fake_llm):
    fake_llm.payload = PAYLOAD

    response = client.post("/decisions", json={"meeting_id": "1", "transcript": SAMPLE_TRANSCRIPT})

    assert response.status_code == 200
    body = response.json()
    assert len(body["decisions"]) == 1
    assert "October 1st" in body["decisions"][0]["decision"]


# The prompt says decisions must be distinguishable from suggestions;
# here we verify the pipeline handles "no decisions" without error.
def test_decisions_empty_is_valid(client, fake_llm):
    fake_llm.payload = {"decisions": []}

    response = client.post("/decisions", json={"meeting_id": "1", "transcript": SAMPLE_TRANSCRIPT})

    assert response.status_code == 200
    assert response.json()["decisions"] == []


async def test_decision_service_returns_schema(fake_llm):
    from app.services import decision_service

    fake_llm.payload = PAYLOAD
    result = await decision_service.extract_decisions(SAMPLE_TRANSCRIPT, fake_llm)

    assert isinstance(result, DecisionListResponse)