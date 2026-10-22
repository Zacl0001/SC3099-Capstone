"""Action item extraction service.

Long transcripts are chunked first; per-chunk results are de-duplicated.
"""

from app.prompts import action_items as action_prompts
from app.schemas.action_item import ActionItemListResponse
from app.services.chunked_extraction import (
    chunk_analysis_input,
    map_chunks,
    merge_action_items,
)
from app.services.kas_client import KASClient
from app.services.llm_service import LLMService


async def extract_action_items(
    transcript: str,
    llm: LLMService,
    kas: KASClient | None = None,
    meeting_id: str | None = None,
) -> ActionItemListResponse:
    """Extract structured action items from a transcript."""
    chunks = await chunk_analysis_input(transcript, kas, meeting_id)

    if len(chunks) == 1:
        return await _extract_chunk(chunks[0], llm)

    responses = await map_chunks(chunks, lambda chunk: _extract_chunk(chunk, llm))
    return merge_action_items(responses)


async def _extract_chunk(chunk: str, llm: LLMService) -> ActionItemListResponse:
    """Extract action items from a single piece of text."""
    user_prompt = action_prompts.build_user_prompt(chunk)
    return await llm.generate_structured(
        system_prompt=action_prompts.SYSTEM_PROMPT,
        user_prompt=user_prompt,
        response_model=ActionItemListResponse,
    )