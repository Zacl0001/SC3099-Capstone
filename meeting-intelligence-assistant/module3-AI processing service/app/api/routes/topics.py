"""POST /topics -- topic identification."""

from fastapi import APIRouter, Depends

from app.api.dependencies import get_llm_service
from app.schemas.topic import TopicListResponse
from app.schemas.transcript import TranscriptRequest
from app.services import topic_service
from app.services.llm_service import LLMService

router = APIRouter(tags=["topics"])


@router.post("/topics", response_model=TopicListResponse)
async def topics_endpoint(
    body: TranscriptRequest,
    llm: LLMService = Depends(get_llm_service),
) -> TopicListResponse:
    """Identify the major topics in a meeting transcript."""
    return await topic_service.extract_topics(body.transcript, llm)