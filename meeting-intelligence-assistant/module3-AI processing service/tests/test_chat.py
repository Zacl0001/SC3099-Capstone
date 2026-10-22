"""Tests for the /chat endpoint (grounded Q&A) and citation building."""

from app.schemas.chat import ChatResponse
from app.schemas.search import RetrievedChunk, SectionRef
from app.services.chat_service import NOT_FOUND_MESSAGE, build_citations
from app.services.exceptions import KASConnectionError, LLMConnectionError

CHUNK_1 = RetrievedChunk(
    text="Jamie: The logs show a database connection error. 'Too many clients already'.",
    score=0.9,
    meeting_id="m1",
    title="Debugging session",
    meeting_date="2026-09-30",
    meeting_start_time="09:15:00",
    speakers=["Alex", "Jamie"],
    section_metadata=[
        SectionRef(section_id="section-002", speaker="Jamie", timestamp="00:00:08")
    ],
)

CHUNK_2 = RetrievedChunk(
    text="Alex: We've decided to drop the mobile app feature from this release.",
    score=0.6,
    meeting_id="m1",
    title="Debugging session",
    meeting_date="2026-09-30",
    meeting_start_time="09:15:00",
    speakers=["Alex", "Jamie"],
    section_metadata=[
        SectionRef(section_id="section-011", speaker="Alex", timestamp="00:00:55")
    ],
)


def test_chat_returns_answer_with_citations(client, fake_llm, fake_kas):
    fake_kas.search_results = [CHUNK_1, CHUNK_2]
    fake_llm.text_payload = (
        "It was a database connection limit problem [1]. "
        "They later decided to drop the mobile app feature [2]."
    )

    response = client.post(
        "/chat", json={"meeting_id": "m1", "question": "What was the issue?"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == fake_llm.text_payload

    assert body["citations"] == [
        {
            "index": 1,
            "text": CHUNK_1.text,
            "speaker": "Jamie",
            "timestamp": "00:00:08",
            "section_id": "section-002",
        },
        {
            "index": 2,
            "text": CHUNK_2.text,
            "speaker": "Alex",
            "timestamp": "00:00:55",
            "section_id": "section-011",
        },
    ]


def test_chat_scopes_search_to_meeting(client, fake_llm, fake_kas):
    fake_kas.search_results = [CHUNK_1]

    client.post("/chat", json={"meeting_id": "m1", "question": "Why?"})

    assert fake_kas.search_calls == [("m1", "Why?", None)]


def test_chat_uses_requested_top_k(client, fake_llm, fake_kas):
    fake_kas.search_results = [CHUNK_1]

    client.post("/chat", json={"meeting_id": "m1", "question": "Why?", "top_k": 3})

    assert fake_kas.search_calls == [("m1", "Why?", 3)]


def test_chat_with_no_results_skips_llm(client, fake_llm, fake_kas):
    fake_kas.search_results = []
    fake_llm.text_payload = "should not be used"

    response = client.post("/chat", json={"meeting_id": "m1", "question": "Why?"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == NOT_FOUND_MESSAGE
    assert body["citations"] == []
    assert fake_llm.calls == []


def test_chat_drops_out_of_range_citation_indices(client, fake_llm, fake_kas):
    fake_kas.search_results = [CHUNK_1, CHUNK_2]
    fake_llm.text_payload = "Only first is referenced [1], not a bogus [9]."

    response = client.post("/chat", json={"meeting_id": "m1", "question": "Why?"})

    body = response.json()
    assert [c["index"] for c in body["citations"]] == [1]


def test_chat_maps_llm_failure_to_502(client, fake_llm, fake_kas):
    fake_kas.search_results = [CHUNK_1]
    fake_llm.payload = LLMConnectionError("LLM unreachable")

    response = client.post("/chat", json={"meeting_id": "m1", "question": "Why?"})

    assert response.status_code == 502


def test_chat_maps_kas_failure_to_502(client, fake_llm, fake_kas):
    fake_kas.search_raises = KASConnectionError("KAS unreachable")

    response = client.post("/chat", json={"meeting_id": "m1", "question": "Why?"})

    assert response.status_code == 502


def test_chat_rejects_empty_question(client, fake_llm, fake_kas):
    response = client.post("/chat", json={"meeting_id": "m1", "question": ""})

    assert response.status_code == 422


def test_build_citations_drops_out_of_range_indices():
    answer = "The release date was set [1] and the feature dropped [9]."
    citations = build_citations(answer, [CHUNK_1, CHUNK_2])

    assert [c.index for c in citations] == [1]


async def test_answer_question_service_path(fake_llm, fake_kas):
    from app.schemas.chat import ChatRequest
    from app.services import chat_service

    fake_kas.search_results = [CHUNK_1]
    fake_llm.text_payload = "The tables are full [1]."

    result = await chat_service.answer_question(
        ChatRequest(meeting_id="m1", question="What happened?"),
        fake_llm,
        fake_kas,
    )

    assert isinstance(result, ChatResponse)
    assert result.answer == fake_llm.text_payload
    assert result.citations[0].speaker == "Jamie"