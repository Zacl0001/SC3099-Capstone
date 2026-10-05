"""Topic identification service."""

from app.prompts import topics as topic_prompts
from app.schemas.topic import TopicListResponse
from app.services.llm_service import LLMService


async def extract_topics(transcript: str, llm: LLMService) -> TopicListResponse:
    """Identify the major topics covered in a transcript."""
    user_prompt = topic_prompts.build_user_prompt(transcript)
    return await llm.generate_structured(
        system_prompt=topic_prompts.SYSTEM_PROMPT,
        user_prompt=user_prompt,
        response_model=TopicListResponse,
    )