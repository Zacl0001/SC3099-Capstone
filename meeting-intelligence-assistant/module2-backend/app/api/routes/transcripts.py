# Endpoints:
#
# POST /meetings/{id}/transcript
# GET /meetings/{id}/transcript
# Handles uploads and retrieval.

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.routes.dependencies import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.transcript import TranscriptResponse
from app.services.transcript_service import process_transcript, get_saved_transcript


router = APIRouter(prefix="/api/meetings", tags=["Transcripts"])

@router.post("/{meeting_id}/transcript/process", response_model=TranscriptResponse)
def process_transcript_endpoint(
    meeting_id:int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    try:
        result = process_transcript(db, meeting_id, current_user.id)

    except ValueError as exc:
        raise  HTTPException(status_code=422, detail=str(exc)) from exc

    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Transcript file not found",) from exc

    if result is None:
        raise HTTPException(status_code=404, detail= "Transcript not found")

    return result



@router.get("/{meeting_id}/transcript", response_model= TranscriptResponse)
def get_transcript_endpoint(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    try:
        result = get_saved_transcript(db, meeting_id, current_user.id)

    except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    if result is None:
        raise HTTPException(status_code=404, detail = "Transcript not found")

    return result