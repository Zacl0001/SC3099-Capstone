"""POST /chat -- grounded question answering over one meeting.

Pipeline: KAS retrieval (chunks) -> grounded prompt -> LLM answer + citations.
"""

from fastapi import APIRouter, Depends

from app.api.dependencies import get_chat_llm_service, get_kas_client
from app.schemas.chat import ChatRequest, ChatResponse
from app.services import chat_service
from app.services.kas_client import KASClient
from app.services.llm_service import LLMService

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    body: ChatRequest,
    llm: LLMService = Depends(get_chat_llm_service),
    kas: KASClient = Depends(get_kas_client),
) -> ChatResponse:
    """Answer a question about one meeting, grounded in its transcript chunks."""
    return await chat_service.answer_question(
        body, llm, kas, top_k=body.top_k
    )