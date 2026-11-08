"""Tests for the module3 -> frontend chat citation adapter."""

from app.api.routes.chat import _adapt_chat_response


def test_adapts_module3_citations_and_renumbers_markers():
    result = {
        "answer": "The launch moved to 9 November [6]. QA signs off on the 6th [15].",
        "citations": [
            {
                "index": 6,
                "text": "Let's delay the launch to the following Monday, the 9th of November.",
                "speaker": "Alex",
                "timestamp": "00:00:39",
                "section_id": "section 004",
            },
            {
                "index": 15,
                "text": "we delay to 9 November, QA signs off on the 6th",
                "speaker": "Alex",
                "timestamp": "00:02:29",
                "section_id": "section 015",
            },
        ],
    }

    response = _adapt_chat_response(result)

    assert response.answer == (
        "The launch moved to 9 November [1]. QA signs off on the 6th [2]."
    )
    assert [citation.chunk_id for citation in response.citations] == [
        "section 004",
        "section 015",
    ]
    assert [citation.start_time for citation in response.citations] == [
        "00:00:39",
        "00:02:29",
    ]
    assert response.citations[0].speaker == "Alex"
    assert response.citations[0].text.startswith("Let's delay the launch")


def test_no_citations_leaves_the_answer_alone():
    result = {"answer": "I could not find this information in the meeting transcript."}

    response = _adapt_chat_response(result)

    assert response.answer == result["answer"]
    assert response.citations == []
