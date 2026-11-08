# GET /api/meetings/{id}/summary
#
# Proxies module3's POST /summarize using the stored transcript sections.
# The result is cached in the database; pass ?refresh=true to regenerate.

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.routes.ai_context import cached_analysis, transcript_context
from app.api.routes.dependencies import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.services import ai_service
from app.services.ai_service import AIServiceError
from app.services.transcript_service import kas_meeting_id

router = APIRouter(prefix="/api/meetings", tags=["AI"])


@router.get("/{meeting_id}/summary")
def get_summary(
    meeting_id: int,
    refresh: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _, transcript = transcript_context(db, meeting_id, current_user.id)

    try:
        return cached_analysis(
            db,
            meeting_id,
            "summary",
            transcript,
            lambda: ai_service.generate_summary(
                kas_meeting_id(meeting_id), transcript
            ),
            refresh=refresh,
        )
    except AIServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
