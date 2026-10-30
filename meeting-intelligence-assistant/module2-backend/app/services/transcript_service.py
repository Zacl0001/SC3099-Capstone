import re

from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.meeting import Meeting
from app.models.transcript import Transcript
from app.services.file_service import extract_transcript_txt


def parse_transcript_section(text: str) -> list[dict[str, str | None]]:
    sections = []
    speaker_ids = {}

    for line_num, line in enumerate(text.splitlines(), start = 1):
        line = line.strip()

        if not line: #skip empty lines
            continue

        timestamp = None
        timestamp_match = re.match(
            r"^\[(?P<timestamp>\d{1,3}:[0-5]\d:[0-5]\d)\]\s*(?P<content>.+)$",
            line,
        )
        if timestamp_match:
            timestamp = timestamp_match.group("timestamp")
            line = timestamp_match.group("content")

        speaker_name, separator, spoken_text = line.partition(":")
        speaker_name = speaker_name.strip()
        spoken_text = spoken_text.strip()


        if not separator or not speaker_name or not spoken_text:
            raise ValueError(f"Line {line_num} must use the format of Speaker : text")

        if speaker_name not in speaker_ids:
            speaker_ids[speaker_name] = f"speaker {len(speaker_ids) +1:03d}" #assign speaker an id

        sections.append({
            "section_id": f"section {len(sections) + 1:03d}",
            "speaker_id": speaker_ids[speaker_name],
            "speaker_name": speaker_name,
            "timestamp": timestamp,
            "text": spoken_text,

        })

    if not sections:
        raise ValueError("transcript has no speaker sections.")

    return sections


def process_transcript(db: Session, meeting_id: int, user_id: int,
) -> dict | None: 
    meeting = db.scalar(
            select(Meeting).where (
            Meeting.id == meeting_id, 
            Meeting.user_id == user_id,
            )
        )

    if meeting is None:
        return None

    transcript = db.scalar(select(Transcript).where(Transcript.meeting_id == meeting.id))

    if transcript is None:
        return None

    text = extract_transcript_txt(transcript.storage_key)
    sections = parse_transcript_section(text)
    transcript.sections = sections

    try:
        db.commit()
    
    except Exception:
        db.rollback()
        raise
    

    return{
        "meeting_id" : meeting.id,
        "title": meeting.title,
        "meeting_date": meeting.meeting_date,
        "meeting_start_time": meeting.meeting_start_time,
        "sections": sections,
    }


def kas_meeting_id(meeting_id: int | str) -> str:
    """Stable, non-numeric meeting id used by module3 and KAS.

    pgvector infers a numeric cast for metadata values that look like numbers,
    which breaks filtering as soon as one meeting id is non-numeric. Prefixing
    keeps every id a plain string.
    """
    value = str(meeting_id)
    return value if value.startswith("meeting-") else f"meeting-{value}"


def sections_to_text(sections: list[dict]) -> str:
    """Rebuild the ``Speaker: text`` transcript that module3 expects."""
    lines = []
    for section in sections:
        speaker = section.get("speaker_name") or "Speaker"
        timestamp = section.get("timestamp")
        header = f"[{timestamp}] {speaker}" if timestamp else speaker
        lines.append(f"{header}: {section.get('text', '')}")
    return "\n".join(lines)


def to_kas_meeting(context: dict) -> dict:
    """Convert a stored transcript into the KAS IngestRequest shape.

    KAS already accepts date/time objects through ``_isoformat``; the values
    are stringified here because they travel as JSON over HTTP.
    """
    return {
        "meeting_id": kas_meeting_id(context["meeting_id"]),
        "title": context.get("title") or "",
        "meeting_date": _isoformat(context.get("meeting_date")),
        "meeting_start_time": _isoformat(context.get("meeting_start_time")),
        "sections": [
            {
                "section_id": section.get("section_id") or f"section-{i + 1:03d}",
                "speaker_name": section.get("speaker_name") or "Unknown",
                "timestamp": section.get("timestamp") or "",
                "text": section.get("text", ""),
            }
            for i, section in enumerate(context.get("sections") or [])
        ],
    }


def _isoformat(value) -> str:
    if value is None:
        return ""
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def get_saved_transcript(
    db: Session,
    meeting_id: int,
    user_id: int,
) -> dict | None:
    meeting = db.scalar(
        select(Meeting).where(
            Meeting.id == meeting_id,
            Meeting.user_id == user_id,
        )
    )

    if meeting is None:
        return None

    transcript = db.scalar(
        select(Transcript).where(Transcript.meeting_id == meeting.id)
    )

    if transcript is None:
        return None

    if transcript.sections is None:
        raise ValueError("Transcript has not been processed yet")

    return {
        "meeting_id": meeting.id,
        "title": meeting.title,
        "meeting_date": meeting.meeting_date,
        "meeting_start_time": meeting.meeting_start_time,
        "sections": transcript.sections,
    }


    

