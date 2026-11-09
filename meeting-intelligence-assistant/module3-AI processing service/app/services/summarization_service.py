
"""Meeting summarization service.

Pipeline:
    transcript -> (chunk if long) -> prompt -> LLM
    -> Pydantic validation -> SummaryResponse

Long transcripts: map-reduce (summarize each chunk, then merge).
"""

import time
import uuid

from app.prompts import summary as summary_prompts
from app.schemas.summary import SummaryResponse
from app.services.chunked_extraction import (
    chunk_analysis_input,
    map_chunks,
    merge_summaries,
)
from app.services.kas_client import KASClient
from app.services.llm_service import LLMService
from app.core.logging import get_logger

logger = get_logger(__name__)


async def summarize(
    transcript: str,
    llm: LLMService,
    kas: KASClient | None = None,
    meeting_id: str | None = None,
) -> SummaryResponse:
    """Summarize a meeting transcript."""

    # 1. Initialize operation logging
    operation_id = uuid.uuid4().hex[:8]
    started_at = time.perf_counter()

    logger.info(
        "[SUMMARY:%s] START | Meeting=%s | Transcript chars=%d",
        operation_id,
        meeting_id,
        len(transcript),
    )

    try:
        # 2. Split transcript into chunks
        chunks = await chunk_analysis_input(
            transcript,
            kas,
            meeting_id,
        )

        logger.info(
            "[SUMMARY:%s] CHUNKING COMPLETE | Chunks=%d | Lengths=%s",
            operation_id,
            len(chunks),
            [len(chunk) for chunk in chunks],
        )

        # 3. Summarize chunks
        partials = await map_chunks(
            chunks,
            lambda chunk: _summarize_chunk(chunk, llm),
        )

        # 4. Merge if multiple chunks
        if len(partials) == 1:
            result = partials[0]
        else:
            logger.info(
                "[SUMMARY:%s] MERGING | Partial summaries=%d",
                operation_id,
                len(partials),
            )

            result = await merge_summaries(partials, llm)

        # 5. Log successful completion
        logger.info(
            "[SUMMARY:%s] COMPLETE | Duration=%.2fs",
            operation_id,
            time.perf_counter() - started_at,
        )

        return result

    except Exception:
        logger.exception(
            "[SUMMARY:%s] FAILED | Duration=%.2fs",
            operation_id,
            time.perf_counter() - started_at,
        )
        raise


async def _summarize_chunk(
    chunk: str,
    llm: LLMService,
) -> SummaryResponse:
    """Summarize one transcript chunk."""

    user_prompt = summary_prompts.build_user_prompt(chunk)

    return await llm.generate_structured(
        system_prompt=summary_prompts.SYSTEM_PROMPT,
        user_prompt=user_prompt,
        response_model=SummaryResponse,
    )
