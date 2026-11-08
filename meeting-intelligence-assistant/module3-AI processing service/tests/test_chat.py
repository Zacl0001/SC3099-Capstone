"""Tests for the /chat endpoint (grounded Q&A) and citation building."""

from app.schemas.chat import ChatResponse
from app.schemas.search import RetrievedChunk, SectionRef
from app.services.chat_service import (
    NOT_FOUND_MESSAGE,
    build_citations,
    build_context_sections,
    ensure_citations,
)
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
            "text": "The logs show a database connection error. 'Too many clients already'.",
            "speaker": "Jamie",
            "timestamp": "00:00:08",
            "section_id": "section-002",
        },
        {
            "index": 2,
            "text": "We've decided to drop the mobile app feature from this release.",
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
    sections = build_context_sections([CHUNK_1, CHUNK_2])
    citations = build_citations(answer, sections)

    assert [c.index for c in citations] == [1]


MULTI_SECTION_CHUNK = RetrievedChunk(
    text=(
        "Alex [00:00:03]: Thanks everyone for joining.\n"
        "Jamie [00:00:12]: QA found two blockers in the parser.\n"
        "Taylor [00:00:27]: I think we should delay the launch."
    ),
    score=0.8,
    meeting_id="m1",
    section_metadata=[
        SectionRef(section_id="section-001", speaker="Alex", timestamp="00:00:03"),
        SectionRef(section_id="section-002", speaker="Jamie", timestamp="00:00:12"),
        SectionRef(section_id="section-003", speaker="Taylor", timestamp="00:00:27"),
    ],
)


def test_multi_section_chunk_becomes_several_context_blocks(fake_llm, fake_kas):
    fake_kas.search_results = [MULTI_SECTION_CHUNK]
    fake_llm.text_payload = "QA found blockers [2]. Launch should be delayed [3]."

    import asyncio

    from app.schemas.chat import ChatRequest
    from app.services import chat_service

    result = asyncio.run(
        chat_service.answer_question(
            ChatRequest(meeting_id="m1", question="What happened?"),
            fake_llm,
            fake_kas,
        )
    )

    prompt = fake_llm.calls[0][1]
    assert "[1] Alex [00:00:03]: Thanks everyone for joining." in prompt
    assert "[2] Jamie [00:00:12]: QA found two blockers in the parser." in prompt
    assert "[3] Taylor [00:00:27]: I think we should delay the launch." in prompt

    assert [(c.index, c.section_id) for c in result.citations] == [
        (2, "section-002"),
        (3, "section-003"),
    ]
    assert result.citations[0].speaker == "Jamie"
    assert result.citations[0].timestamp == "00:00:12"
    assert result.citations[1].text == "I think we should delay the launch."


def test_same_section_in_overlapping_chunks_is_one_context_block():
    overlapping = RetrievedChunk(
        text="Jamie [00:00:12]: QA found two blockers in the parser.",
        section_metadata=[
            SectionRef(section_id="section-002", speaker="Jamie", timestamp="00:00:12")
        ],
    )

    sections = build_context_sections([MULTI_SECTION_CHUNK, overlapping])

    assert [s.section_id for s in sections] == [
        "section-001",
        "section-002",
        "section-003",
    ]
    assert sections[1].text == "QA found two blockers in the parser."


def test_answer_without_markers_is_attributed_to_sections():
    """Local models sometimes omit every [n] marker despite the prompt."""
    sections = build_context_sections([MULTI_SECTION_CHUNK])
    answer = (
        "QA found two blockers in the parser. "
        "The launch should be delayed."
    )

    fixed, citations = ensure_citations(answer, sections)

    assert fixed == (
        "QA found two blockers in the parser [2]. "
        "The launch should be delayed [3]."
    )
    assert [(c.index, c.section_id) for c in citations] == [
        (2, "section-002"),
        (3, "section-003"),
    ]


def test_missing_markers_are_filled_without_touching_existing_ones():
    sections = build_context_sections([MULTI_SECTION_CHUNK])
    answer = "QA found two blockers [2]. The launch should be delayed."

    fixed, citations = ensure_citations(answer, sections)

    assert fixed == (
        "QA found two blockers [2]. The launch should be delayed [3]."
    )
    assert [c.index for c in citations] == [2, 3]


def test_a_marker_pointing_at_an_unrelated_section_is_corrected():
    sections = build_context_sections([MULTI_SECTION_CHUNK])
    # [1] is the opening thanks; the launch turn is block [3].
    answer = "The launch should be delayed [1]."

    fixed, citations = ensure_citations(answer, sections)

    assert fixed == "The launch should be delayed [3]."
    assert [(c.index, c.section_id) for c in citations] == [
        (3, "section-003")
    ]


def test_a_sentence_without_enough_overlap_stays_uncited():
    sections = build_context_sections([MULTI_SECTION_CHUNK])

    fixed, citations = ensure_citations("Thanks.", sections)

    assert fixed == "Thanks."
    assert citations == []


def test_out_of_range_markers_are_removed():
    sections = build_context_sections([MULTI_SECTION_CHUNK])

    fixed, citations = ensure_citations("A bogus claim [9].", sections)

    assert fixed == "A bogus claim."
    assert citations == []


def test_not_found_answer_is_never_cited():
    sections = build_context_sections([MULTI_SECTION_CHUNK])

    fixed, citations = ensure_citations(NOT_FOUND_MESSAGE, sections)

    assert fixed == NOT_FOUND_MESSAGE
    assert citations == []


def test_chunk_without_metadata_falls_back_to_one_block():
    chunk = RetrievedChunk(text="A plain transcript excerpt with no headers.")

    sections = build_context_sections([chunk])

    assert len(sections) == 1
    assert sections[0].text == "A plain transcript excerpt with no headers."
    assert sections[0].section_id is None


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