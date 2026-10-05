"""Meeting summarization service.

Pipeline:
    transcript -> prompt -> LLM -> Pydantic validation -> SummaryResponse
"""

from app.prompts import summary as summary_prompts
from app.schemas.summary import SummaryResponse
from app.services.llm_service import LLMService


async def summarize(transcript: str, llm: LLMService) -> SummaryResponse:
    """Summarize a meeting transcript."""
    user_prompt = summary_prompts.build_user_prompt(transcript)
    return await llm.generate_structured(
        system_prompt=summary_prompts.SYSTEM_PROMPT,
        user_prompt=user_prompt,
        response_model=SummaryResponse,
    )