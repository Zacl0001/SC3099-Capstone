
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.meeting import Meeting
from app.models.transcript import Transcript
from app.services.file_service import extract_transcript_txt


def parse_transcript_section(text: str) -> list[dict[str,str]]:
    sections = []
    speaker_ids = {}

    for line_num, line in enumerate(text.splitlines(), start = 1):
        line = line.strip()

        if not line: #skip empty lines
            continue

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
            "text": spoken_text,

        })

    if not sections:
        raise ValueError("transcript has no speaker sections.")

    return sections


def get_extracted_transcript(db: Session, meeting_id: int, user_id: int,
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

    return{
        "meeting_id" : meeting.id,
        "title": meeting.title,
        "sections": sections,
    }


    