"""POST /decisions -- decision extraction."""

from fastapi import APIRouter, Depends

from app.api.dependencies import get_llm_service
from app.schemas.decision import DecisionListResponse
from app.schemas.transcript import TranscriptRequest
from app.services import decision_service
from app.services.llm_service import LLMService

router = APIRouter(tags=["decisions"])


@router.post("/decisions", response_model=DecisionListResponse)
async def decisions_endpoint(
    body: TranscriptRequest,
    llm: LLMService = Depends(get_llm_service),
) -> DecisionListResponse:
    """Extract decisions from a meeting transcript."""
    return await decision_service.extract_decisions(body.transcript, llm)