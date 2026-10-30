# Regression tests for the AI/RAG proxy layer (module3 + module4 clients).
#
# These do not need a running database or LLM: they cover the pure data
# translation between module2 and the two downstream services.

import re

from app.api.routes.chat import _adapt_chat_response
from app.services.transcript_service import kas_meeting_id, sections_to_text, to_kas_meeting


def test_kas_meeting_id_namespaces_numeric_ids():
    assert kas_meeting_id(1) == "meeting-1"
    assert kas_meeting_id("1") == "meeting-1"
    # Already namespaced ids are left alone.
    assert kas_meeting_id("meeting-1") == "meeting-1"


def test_sections_to_text_rebuilds_speaker_lines():
    sections = [
        {"speaker_name": "Alex", "timestamp": "00:00:03", "text": "Hello"},
        {"speaker_name": "Jamie", "timestamp": None, "text": "Hi"},
    ]

    assert sections_to_text(sections) == "[00:00:03] Alex: Hello\nJamie: Hi"


def test_to_kas_meeting_matches_ingest_contract():
    context = {
        "meeting_id": 7,
        "title": "Launch planning",
        "meeting_date": None,
        "meeting_start_time": None,
        "sections": [
            {"section_id": "section 001", "speaker_name": "Alex", "timestamp": "00:00:03", "text": "Hello"},
        ],
    }

    payload = to_kas_meeting(context)

    assert payload["meeting_id"] == "meeting-7"
    assert payload["sections"] == [
        {
            "section_id": "section 001",
            "speaker_name": "Alex",
            "timestamp": "00:00:03",
            "text": "Hello",
        }
    ]


def test_to_kas_meeting_fills_missing_section_fields():
    payload = to_kas_meeting(
        {"meeting_id": 1, "title": "T", "sections": [{"text": "Hello"}]}
    )

    assert payload["sections"][0]["section_id"] == "section-001"
    assert payload["sections"][0]["speaker_name"] == "Unknown"
    assert payload["sections"][0]["timestamp"] == ""


def test_adapt_chat_response_maps_citations_and_renumbers_markers():
    result = {
        "answer": "The launch moved [1] and QA signs off [3].",
        "citations": [
            {
                "index": 1,
                "section_id": "section 007",
                "timestamp": "00:01:08",
                "speaker": "Alex",
                "text": "launch moves to Monday 9 November",
            },
            {
                "index": 3,
                "section_id": "section 012",
                "timestamp": "00:01:50",
                "speaker": "Taylor",
                "text": "QA sign-off",
            },
        ],
    }

    response = _adapt_chat_response(result)

    # Citations keep their order, but markers are renumbered to 1..n so the
    # frontend's citations[n - 1] lookup stays correct.
    assert response.answer == "The launch moved [1] and QA signs off [2]."
    assert [c.chunk_id for c in response.citations] == ["section 007", "section 012"]
    assert response.citations[0].start_time == "00:01:08"
    assert response.citations[0].end_time is None
    assert response.citations[0].speaker == "Alex"


def test_adapt_chat_response_does_not_invent_citations():
    response = _adapt_chat_response(
        {"answer": "Not enough information.", "citations": []}
    )

    assert response.answer == "Not enough information."
    assert response.citations == []
    assert re.search(r"\[\d+\]", response.answer) is None
