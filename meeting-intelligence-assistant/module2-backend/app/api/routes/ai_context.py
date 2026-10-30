"""Shared helpers for the AI-backed meeting routes."""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.services.transcript_service import (
    get_saved_transcript,
    sections_to_text,
)


def transcript_context(
    db: Session, meeting_id: int, user_id: int
) -> tuple[dict, str]:
    """Return (stored transcript context, plain-text transcript).

    404 if the meeting/transcript does not exist, 409 if the transcript has
    not been processed into speaker sections yet.
    """
    try:
        context = get_saved_transcript(db, meeting_id, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if context is None:
        raise HTTPException(status_code=404, detail="Transcript not found")

    return context, sections_to_text(context["sections"])
