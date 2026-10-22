"""Topic identification service.

Long transcripts are chunked first; per-chunk results are de-duplicated.
"""

from app.prompts import topics as topic_prompts
from app.schemas.topic import TopicListResponse
from app.services.chunked_extraction import (
    chunk_analysis_input,
    map_chunks,
    merge_topics,
)
from app.services.kas_client import KASClient
from app.services.llm_service import LLMService


async def extract_topics(
    transcript: str,
    llm: LLMService,
    kas: KASClient | None = None,
    meeting_id: str | None = None,
) -> TopicListResponse:
    """Identify the major topics covered in a transcript."""
    chunks = await chunk_analysis_input(transcript, kas, meeting_id)

    if len(chunks) == 1:
        return await _extract_chunk(chunks[0], llm)

    responses = await map_chunks(chunks, lambda chunk: _extract_chunk(chunk, llm))
    return merge_topics(responses)


async def _extract_chunk(chunk: str, llm: LLMService) -> TopicListResponse:
    """Identify topics in a single piece of text."""
    user_prompt = topic_prompts.build_user_prompt(chunk)
    return await llm.generate_structured(
        system_prompt=topic_prompts.SYSTEM_PROMPT,
        user_prompt=user_prompt,
        response_model=TopicListResponse,
    )