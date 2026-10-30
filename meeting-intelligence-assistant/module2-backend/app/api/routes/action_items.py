# GET /api/meetings/{id}/action-items
#
# Proxies module3's POST /actions; the frontend accepts {action_items: [...]}.

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.routes.ai_context import transcript_context
from app.api.routes.dependencies import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.services import ai_service
from app.services.ai_service import AIServiceError
from app.services.transcript_service import kas_meeting_id

router = APIRouter(prefix="/api/meetings", tags=["AI"])


@router.get("/{meeting_id}/action-items")
def get_action_items(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _, transcript = transcript_context(db, meeting_id, current_user.id)

    try:
        return ai_service.extract_action_items(kas_meeting_id(meeting_id), transcript)
    except AIServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
