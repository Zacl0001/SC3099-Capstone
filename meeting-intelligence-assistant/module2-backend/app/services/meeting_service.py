# Responsible for:
#
# Create meeting
# Get meeting
# List meetings
# Delete meeting
# Validate ownership
# Important:
#
# A user must not be able to access another user's meeting by changing the meeting ID.

from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.meeting import Meeting
from app.models.transcript import Transcript
from app.services.file_service import save_transcript_file, STORAGE_ROOT
from fastapi import UploadFile

def create_meeting(db: Session, user_id: int, title: str) -> Meeting:
    meeting = Meeting(user_id = user_id, title= title)

    db.add(meeting)
    db.flush()
    return meeting

def upload_meeting(db: Session, user_id: int, title: str, file: UploadFile) -> Meeting:
    file_name = file.filename or ""

    if not file_name or len(file_name) > 255:
        raise ValueError("filename must be between 1 and 255 characters")

    storage_key = save_transcript_file(file)

    try:
        meeting = create_meeting(db, user_id, title)

        transcript = Transcript(meeting_id=meeting.id, file_name =file_name, storage_key = storage_key, )

        db.add(transcript)
        db.commit()

    except Exception:
        db.rollback()
        (STORAGE_ROOT / storage_key).unlink(missing_ok=True)
        raise

    db.refresh(meeting)
    return meeting


def list_meetings(db: Session, user_id: int) -> list[Meeting]: #returns list of meeting objects (TO FE)
    statement = (
        select(Meeting).where(Meeting.user_id == user_id).order_by(Meeting.created_at.desc(), Meeting.id.desc()))

    return list(db.scalars(statement).all())