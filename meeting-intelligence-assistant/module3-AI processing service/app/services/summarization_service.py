"""Meeting summarization service.

Pipeline:
    transcript -> (chunk if long) -> prompt -> LLM -> Pydantic validation -> SummaryResponse
Long transcripts: map-reduce (summarize each chunk, then merge).
"""

from app.prompts import summary as summary_prompts
from app.schemas.summary import SummaryResponse
from app.services.chunked_extraction import (
    chunk_analysis_input,
    map_chunks,
    merge_summaries,
)
from app.services.kas_client import KASClient
from app.services.llm_service import LLMService


async def summarize(
    transcript: str,
    llm: LLMService,
    kas: KASClient | None = None,
    meeting_id: str | None = None,
) -> SummaryResponse:
    """Summarize a meeting transcript."""
    chunks = await chunk_analysis_input(transcript, kas, meeting_id)

    if len(chunks) == 1:
        return await _summarize_chunk(chunks[0], llm)

    partials = await map_chunks(chunks, lambda chunk: _summarize_chunk(chunk, llm))
    return await merge_summaries(partials, llm)


async def _summarize_chunk(chunk: str, llm: LLMService) -> SummaryResponse:
    """Summarize a single piece of text (transcript or one chunk)."""
    user_prompt = summary_prompts.build_user_prompt(chunk)
    return await llm.generate_structured(
        system_prompt=summary_prompts.SYSTEM_PROMPT,
        user_prompt=user_prompt,
        response_model=SummaryResponse,
    )