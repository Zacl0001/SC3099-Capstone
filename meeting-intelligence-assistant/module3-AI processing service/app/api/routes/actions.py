"""POST /actions -- action item extraction."""

from fastapi import APIRouter, Depends

from app.api.dependencies import get_kas_client, get_llm_service
from app.schemas.action_item import ActionItemListResponse
from app.schemas.transcript import TranscriptRequest
from app.services import action_service
from app.services.kas_client import KASClient
from app.services.llm_service import LLMService

router = APIRouter(tags=["actions"])


@router.post("/actions", response_model=ActionItemListResponse)
async def actions_endpoint(
    body: TranscriptRequest,
    llm: LLMService = Depends(get_llm_service),
    kas: KASClient = Depends(get_kas_client),
) -> ActionItemListResponse:
    """Extract action items from a meeting transcript."""
    return await action_service.extract_action_items(
        body.transcript, llm, kas=kas, meeting_id=body.meeting_id
    )