# POST /api/meetings/{id}/chat
#
# Proxies module3's POST /chat, which retrieves chunks from KAS and asks the
# LLM to answer with [n] citations. Module3's citation shape is adapted to
# the frontend's {chunk_id, start_time, end_time, speaker, text}.

import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.routes.ai_context import transcript_context
from app.api.routes.dependencies import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.chat import ChatRequest, ChatResponse, CitationResponse
from app.services import ai_service, knowledge_service
from app.services.ai_service import AIServiceError
from app.services.knowledge_service import KnowledgeServiceError
from app.services.transcript_service import to_kas_meeting, kas_meeting_id

router = APIRouter(prefix="/api/meetings", tags=["AI"])


@router.post("/{meeting_id}/chat", response_model=ChatResponse)
def ask_question(
    meeting_id: int,
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatResponse:
    # Also verifies that the meeting belongs to this user.
    transcript_context(db, meeting_id, current_user.id)

    try:
        result = ai_service.ask_question(
            kas_meeting_id(meeting_id), body.question, top_k=body.top_k
        )
    except AIServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return _adapt_chat_response(result)


@router.post("/{meeting_id}/index")
def index_meeting(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """(Re)index one meeting in the knowledge service. Used after processing
    and useful when KAS was down during the original upload."""
    context, _ = transcript_context(db, meeting_id, current_user.id)

    try:
        return knowledge_service.ingest_transcript(to_kas_meeting(context))
    except KnowledgeServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _adapt_chat_response(result: dict) -> ChatResponse:
    """Map module3 citations onto the frontend's citation contract.

    Module3 numbers citations with the retrieved chunk index (for example
    [1] and [3]). The frontend resolves [n] to citations[n - 1], so the
    answer markers are renumbered to match the adapted list.
    """
    raw_citations = result.get("citations") or []

    mapping: dict[int, int] = {}
    citations: list[CitationResponse] = []
    for position, citation in enumerate(raw_citations, start=1):
        original = citation.get("index")
        if isinstance(original, int):
            mapping[original] = position

        citations.append(
            CitationResponse(
                chunk_id=citation.get("section_id")
                or f"chunk-{citation.get('index', position)}",
                start_time=citation.get("timestamp"),
                end_time=None,
                speaker=citation.get("speaker"),
                text=citation.get("text", ""),
            )
        )

    answer = result.get("answer", "")
    if mapping:
        answer = re.sub(
            r"\[(\d+)\]",
            lambda match: f"[{mapping[int(match.group(1))]}]"
            if int(match.group(1)) in mapping
            else match.group(0),
            answer,
        )

    return ChatResponse(answer=answer, citations=citations)
