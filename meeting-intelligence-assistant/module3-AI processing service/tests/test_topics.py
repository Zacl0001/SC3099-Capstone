"""Tests for the /topics endpoint."""

from app.schemas.topic import TopicListResponse
from tests.conftest import SAMPLE_TRANSCRIPT

PAYLOAD = {
    "topics": [
        {
            "name": "Release Timeline",
            "description": "Decided on an October 1st release date.",
            "importance": "HIGH",
        }
    ]
}


def test_topics_endpoint_returns_topics(client, fake_llm):
    fake_llm.payload = PAYLOAD

    response = client.post("/topics", json={"meeting_id": "1", "transcript": SAMPLE_TRANSCRIPT})

    assert response.status_code == 200
    body = response.json()
    assert body["topics"][0]["name"] == "Release Timeline"
    assert body["topics"][0]["importance"] == "HIGH"


# Pydantic should reject an importance value outside HIGH/MEDIUM/LOW
# by contract; check that invalid payload is surfaced as 502.
def test_topics_rejects_invalid_importance(client, fake_llm):
    fake_llm.payload = {
        "topics": [
            {
                "name": "Budget",
                "description": "Budget discussed.",
                "importance": "CRITICAL_MOST_MEGA",
            }
        ]
    }

    response = client.post("/topics", json={"meeting_id": "1", "transcript": SAMPLE_TRANSCRIPT})

    assert response.status_code == 502


async def test_topic_service_returns_schema(fake_llm):
    from app.services import topic_service

    fake_llm.payload = PAYLOAD
    result = await topic_service.extract_topics(SAMPLE_TRANSCRIPT, fake_llm)

    assert isinstance(result, TopicListResponse)