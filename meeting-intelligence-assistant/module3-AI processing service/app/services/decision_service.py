"""Decision extraction service.

Long transcripts are chunked first; per-chunk results are de-duplicated.
"""

from app.prompts import decisions as decision_prompts
from app.schemas.decision import DecisionListResponse
from app.services.chunked_extraction import (
    chunk_analysis_input,
    map_chunks,
    merge_decisions,
)
from app.services.kas_client import KASClient
from app.services.llm_service import LLMService


async def extract_decisions(
    transcript: str,
    llm: LLMService,
    kas: KASClient | None = None,
    meeting_id: str | None = None,
) -> DecisionListResponse:
    """Extract structured decisions from a transcript."""
    chunks = await chunk_analysis_input(transcript, kas, meeting_id)

    if len(chunks) == 1:
        return await _extract_chunk(chunks[0], llm)

    responses = await map_chunks(chunks, lambda chunk: _extract_chunk(chunk, llm))
    return merge_decisions(responses)


async def _extract_chunk(chunk: str, llm: LLMService) -> DecisionListResponse:
    """Extract decisions from a single piece of text."""
    user_prompt = decision_prompts.build_user_prompt(chunk)
    return await llm.generate_structured(
        system_prompt=decision_prompts.SYSTEM_PROMPT,
        user_prompt=user_prompt,
        response_model=DecisionListResponse,
    )