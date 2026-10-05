"""Decision extraction service."""

from app.prompts import decisions as decision_prompts
from app.schemas.decision import DecisionListResponse
from app.services.llm_service import LLMService


async def extract_decisions(
    transcript: str, llm: LLMService
) -> DecisionListResponse:
    """Extract structured decisions from a transcript."""
    user_prompt = decision_prompts.build_user_prompt(transcript)
    return await llm.generate_structured(
        system_prompt=decision_prompts.SYSTEM_PROMPT,
        user_prompt=user_prompt,
        response_model=DecisionListResponse,
    )