"""Tests for section matching and assignee backfilling."""

from app.services.source_matching import (
    derive_assignee,
    enrich_analysis,
    match_section,
)

SECTIONS = [
    {
        "section_id": "section 001",
        "speaker_name": "Alex",
        "timestamp": "00:00:03",
        "text": (
            "Thanks everyone for joining. The purpose of this meeting is to "
            "decide whether we launch the assistant next Monday."
        ),
    },
    {
        "section_id": "section 004",
        "speaker_name": "Alex",
        "timestamp": "00:00:39",
        "text": (
            "I agree. Let's delay the launch to the following Monday, the "
            "9th of November."
        ),
    },
    {
        "section_id": "section 005",
        "speaker_name": "Jamie",
        "timestamp": "00:00:47",
        "text": (
            "That works for engineering. I will fix the PDF parser by "
            "Wednesday the 4th."
        ),
    },
    {
        "section_id": "section 009",
        "speaker_name": "Alex",
        "timestamp": "00:01:30",
        "text": (
            "Priya, can you own the user guide? Please have a draft ready by "
            "Friday the 6th as well."
        ),
    },
]


def test_first_person_evidence_matches_speaking_section_and_assignee():
    payload = {
        "action_items": [
            {
                "task": "Fix the PDF parser",
                "assignee": None,
                "deadline": "Wednesday",
                "evidence": "Jamie: I'll fix the PDF parser by Wednesday the 4th.",
                "timestamp": None,
            }
        ]
    }

    result = enrich_analysis(payload, SECTIONS, "action_items")
    item = result["action_items"][0]

    assert item["assignee"] == "Jamie"
    assert item["section_id"] == "section 005"
    assert item["timestamp"] == "00:00:47"


def test_named_assignment_is_used_even_when_speaker_is_someone_else():
    evidence = "Alex: Priya, can you own the user guide?"

    section = match_section(evidence, None, SECTIONS)

    assert section is not None
    assert section["section_id"] == "section 009"
    assert derive_assignee(evidence, section) == "Priya"


def test_named_capability_wording_is_also_an_assignee():
    section = match_section("Priya can own the user guide", None, SECTIONS)

    assert section is not None
    assert derive_assignee("Priya can own the user guide", section) == "Priya"


def test_existing_assignee_and_timestamp_are_not_overwritten():
    payload = {
        "action_items": [
            {
                "task": "Prepare the user guide",
                "assignee": "Priya S.",
                "evidence": "Priya, can you own the user guide?",
                "timestamp": "00:01:30",
            }
        ]
    }

    item = enrich_analysis(payload, SECTIONS, "action_items")["action_items"][0]

    assert item["assignee"] == "Priya S."
    assert item["timestamp"] == "00:01:30"
    assert item["section_id"] == "section 009"


def test_a_wrong_llm_timestamp_is_corrected_to_the_matched_section():
    payload = {
        "action_items": [
            {
                "task": "Fix the PDF parser",
                "assignee": None,
                "evidence": "I will fix the PDF parser by Wednesday the 4th.",
                "timestamp": "00:00:03",
            }
        ]
    }

    item = enrich_analysis(payload, SECTIONS, "action_items")["action_items"][0]

    assert item["section_id"] == "section 005"
    assert item["timestamp"] == "00:00:47"


def test_ambiguous_evidence_is_left_unassigned():
    payload = {
        "action_items": [
            {
                "task": "Follow up on the budget",
                "assignee": None,
                "evidence": "we should follow up on the budget at some point",
                "timestamp": None,
            }
        ]
    }

    item = enrich_analysis(payload, SECTIONS, "action_items")["action_items"][0]

    assert item["assignee"] is None
    assert "section_id" not in item


def test_timestamp_is_used_when_evidence_is_too_weak_to_score():
    section = match_section("", "00:00:47", SECTIONS)

    assert section is not None
    assert section["section_id"] == "section 005"


def test_weak_evidence_does_not_pick_a_short_generic_section():
    section = match_section("thanks", None, SECTIONS)

    assert section is None


def test_decisions_get_a_section_id_without_an_assignee_field():
    payload = {
        "decisions": [
            {
                "decision": "Delay the launch by one week",
                "evidence": (
                    "Let's delay the launch to the following Monday, the 9th "
                    "of November."
                ),
                "timestamp": None,
            }
        ]
    }

    item = enrich_analysis(payload, SECTIONS, "decisions")["decisions"][0]

    assert item["section_id"] == "section 004"
    assert item["timestamp"] == "00:00:39"
    assert "assignee" not in item
