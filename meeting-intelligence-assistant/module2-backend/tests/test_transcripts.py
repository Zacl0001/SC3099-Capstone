# Test:
#
# upload
# invalid file
# empty transcript
# processing status
from app.services.transcript_service import parse_transcript_section


def test_parse_transcript_section_includes_timestamp():
    sections = parse_transcript_section("[00:00:02] Alex: Hello there")

    assert sections == [
        {
            "section_id": "section 001",
            "speaker_id": "speaker 001",
            "speaker_name": "Alex",
            "timestamp": "00:00:02",
            "text": "Hello there",
        }
    ]


def test_parse_transcript_section_keeps_untimestamped_format_compatible():
    sections = parse_transcript_section("Alex: Hello there")

    assert sections[0]["timestamp"] is None
