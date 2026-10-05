"""Tests for the /actions endpoint and action item extraction."""

from app.schemas.action_item import ActionItemListResponse
from app.services.exceptions import LLMInvalidResponse
from tests.conftest import SAMPLE_TRANSCRIPT

PAYLOAD = {
    "action_items": [
        {
            "task": "Prepare release notes",
            "assignee": "Carol",
            "deadline": "Friday",
            "evidence": "Carol, can you prepare the release notes?",
            "timestamp": None,
        }
    ]
}


def test_actions_endpoint_returns_action_items(client, fake_llm):
    fake_llm.payload = PAYLOAD

    response = client.post("/actions", json={"meeting_id": "1", "transcript": SAMPLE_TRANSCRIPT})

    assert response.status_code == 200
    body = response.json()
    assert len(body["action_items"]) == 1
    assert body["action_items"][0]["assignee"] == "Carol"


def test_actions_accepts_missing_optional_assignee(client, fake_llm):
    # The prompt says assignee may be null; make sure null survives validation.
    fake_llm.payload = {
        "action_items": [
            {
                "task": "Follow up on budget",
                "assignee": None,
                "deadline": None,
                "evidence": "we should follow up on the budget",
                "timestamp": None,
            }
        ]
    }

    response = client.post("/actions", json={"meeting_id": "1", "transcript": SAMPLE_TRANSCRIPT})

    assert response.status_code == 200
    assert response.json()["action_items"][0]["assignee"] is None


def test_actions_rejects_malformed_llm_output(client, fake_llm):
    # Simulate the LLM returning a list instead of an object -> validation fails.
    fake_llm.payload = ["not an object"]

    response = client.post("/actions", json={"meeting_id": "1", "transcript": SAMPLE_TRANSCRIPT})

    assert response.status_code == 502


def test_actions_empty_items_ok(client, fake_llm):
    fake_llm.payload = {"action_items": []}

    response = client.post("/actions", json={"meeting_id": "1", "transcript": SAMPLE_TRANSCRIPT})

    assert response.status_code == 200
    assert response.json()["action_items"] == []


async def test_action_service_returns_schema(fake_llm):
    from app.services import action_service

    fake_llm.payload = PAYLOAD
    result = await action_service.extract_action_items(SAMPLE_TRANSCRIPT, fake_llm)

    assert isinstance(result, ActionItemListResponse)
    assert result.action_items[0].task == "Prepare release notes"