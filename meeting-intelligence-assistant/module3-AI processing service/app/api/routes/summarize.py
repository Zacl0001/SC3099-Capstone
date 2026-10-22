"""POST /summarize -- meeting summarization."""

from fastapi import APIRouter, Depends

from app.api.dependencies import get_kas_client, get_llm_service
from app.schemas.summary import SummaryResponse
from app.schemas.transcript import TranscriptRequest
from app.services import summarization_service
from app.services.kas_client import KASClient
from app.services.llm_service import LLMService

router = APIRouter(tags=["summarize"])


@router.post("/summarize", response_model=SummaryResponse)
async def summarize_endpoint(
    body: TranscriptRequest,
    llm: LLMService = Depends(get_llm_service),
    kas: KASClient = Depends(get_kas_client),
) -> SummaryResponse:
    """Summarize a meeting transcript."""
    return await summarization_service.summarize(
        body.transcript, llm, kas=kas, meeting_id=body.meeting_id
    )