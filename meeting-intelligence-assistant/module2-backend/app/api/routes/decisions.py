# GET /api/meetings/{id}/decisions
#
# Proxies module3's POST /decisions; the frontend accepts {decisions: [...]}.
# The result is cached in the database; pass ?refresh=true to regenerate.

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.routes.ai_context import cached_analysis, transcript_context
from app.api.routes.dependencies import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.services import ai_service
from app.services.ai_service import AIServiceError
from app.services.source_matching import enrich_analysis
from app.services.transcript_service import kas_meeting_id

router = APIRouter(prefix="/api/meetings", tags=["AI"])


@router.get("/{meeting_id}/decisions")
def get_decisions(
    meeting_id: int,
    refresh: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    context, transcript = transcript_context(db, meeting_id, current_user.id)

    try:
        payload = cached_analysis(
            db,
            meeting_id,
            "decisions",
            transcript,
            lambda: ai_service.extract_decisions(
                kas_meeting_id(meeting_id), transcript
            ),
            refresh=refresh,
        )
    except AIServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return enrich_analysis(payload, context["sections"], "decisions")
