"""Action item extraction service."""

from app.prompts import action_items as action_prompts
from app.schemas.action_item import ActionItemListResponse
from app.services.llm_service import LLMService


async def extract_action_items(
    transcript: str, llm: LLMService
) -> ActionItemListResponse:
    """Extract structured action items from a transcript."""
    user_prompt = action_prompts.build_user_prompt(transcript)
    return await llm.generate_structured(
        system_prompt=action_prompts.SYSTEM_PROMPT,
        user_prompt=user_prompt,
        response_model=ActionItemListResponse,
    )