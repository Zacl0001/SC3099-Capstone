"""Helpers for running the analysis endpoints on long transcripts.

Strategy:
  - short transcripts: pass straight through unchanged (one LLM call);
  - long transcripts: split into semantic chunks via the KAS /chunk endpoint,
    run the existing extraction per chunk, then merge the per-chunk results.

Summary uses map-reduce (`merge_summaries`); action items / decisions / topics
use per-chunk extraction plus keyed de-duplication.
"""
import time
import uuid

from app.core.config import get_settings
from app.core.logging import get_logger
from app.prompts import chunked_summary as chunked_prompts
from app.schemas.action_item import ActionItem, ActionItemListResponse
from app.schemas.decision import Decision, DecisionListResponse
from app.schemas.summary import SummaryResponse
from app.schemas.topic import Importance, Topic, TopicListResponse
from app.services.exceptions import LLMInvalidResponse
from app.services.kas_client import KASClient
from app.services.llm_service import LLMService

logger = get_logger(__name__)

_IMPORTANCE_RANK = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}



async def chunk_analysis_input(
    transcript: str,
    kas: KASClient | None,
    meeting_id: str | None = None,
) -> list[str]:

    settings = get_settings()
    threshold = settings.chunk_threshold_chars

    logger.info(
        "[CHUNKING] Transcript=%d | Threshold=%d",
        len(transcript),
        threshold,
    )

    if kas is None or len(transcript) <= threshold:
        logger.info("[CHUNKING] Skipping chunking")
        return [transcript]

    chunks = await kas.chunk(meeting_id, transcript)

    cleaned = [
        chunk.strip()
        for chunk in chunks
        if chunk and chunk.strip()
    ]

    logger.info(
        "[CHUNKING] KAS returned %d chunks | Sizes=%s",
        len(cleaned),
        [len(chunk) for chunk in cleaned],
    )

    if not cleaned:
        logger.warning(
            "[CHUNKING] Empty KAS response; using original transcript"
        )
        return [transcript]

    return cleaned



def _normalise(text: str) -> str:
    return " ".join(text.lower().split())


async def map_chunks(chunks: list[str], extract_chunk) -> list:
    """Process chunks sequentially with detailed logging."""

    results = []
    total = len(chunks)
    operation_id = uuid.uuid4().hex[:8]

    logger.info(
        "[CHUNKS:%s] START | Total chunks=%d",
        operation_id,
        total,
    )

    for position, chunk in enumerate(chunks, 1):
        chunk_started = time.perf_counter()

        logger.info(
            "[CHUNKS:%s] PROCESSING | Chunk=%d/%d | Characters=%d",
            operation_id,
            position,
            total,
            len(chunk),
        )

        try:
            result = await extract_chunk(chunk)
            results.append(result)

            elapsed = time.perf_counter() - chunk_started

            logger.info(
                "[CHUNKS:%s] SUCCESS | Chunk=%d/%d | Duration=%.2fs",
                operation_id,
                position,
                total,
                elapsed,
            )

        except LLMInvalidResponse as exc:
            logger.warning(
                "[CHUNKS:%s] FIRST ATTEMPT FAILED | Chunk=%d/%d | Error=%s",
                operation_id,
                position,
                total,
                exc,
            )

            try:
                result = await extract_chunk(chunk)
                results.append(result)

                logger.info(
                    "[CHUNKS:%s] RETRY SUCCESS | Chunk=%d/%d",
                    operation_id,
                    position,
                    total,
                )

            except LLMInvalidResponse as retry_exc:
                logger.error(
                    "[CHUNKS:%s] CHUNK SKIPPED | Chunk=%d/%d | Error=%s",
                    operation_id,
                    position,
                    total,
                    retry_exc,
                )

        except Exception:
            logger.exception(
                "[CHUNKS:%s] UNEXPECTED FAILURE | Chunk=%d/%d",
                operation_id,
                position,
                total,
            )
            raise

    logger.info(
        "[CHUNKS:%s] FINISHED | Successful=%d | Failed=%d",
        operation_id,
        len(results),
        total - len(results),
    )

    if not results:
        raise LLMInvalidResponse(
            f"All {total} chunk extraction attempts failed."
        )

    return results


def merge_action_items(
    responses: list[ActionItemListResponse],
) -> ActionItemListResponse:
    """Merge per-chunk action items, de-duplicating by normalized task."""
    by_key: dict[str, ActionItem] = {}
    order: list[str] = []

    for response in responses:
        for item in response.action_items:
            key = _normalise(item.task)
            if key not in by_key:
                by_key[key] = item
                order.append(key)
            else:
                existing = by_key[key]
                if existing.assignee is None and item.assignee is not None:
                    by_key[key] = item

    return ActionItemListResponse(action_items=[by_key[key] for key in order])


def merge_decisions(responses: list[DecisionListResponse]) -> DecisionListResponse:
    """Merge per-chunk decisions, de-duplicating by normalized decision."""
    by_key: dict[str, Decision] = {}
    order: list[str] = []

    for response in responses:
        for item in response.decisions:
            key = _normalise(item.decision)
            if key not in by_key:
                by_key[key] = item
                order.append(key)

    return DecisionListResponse(decisions=[by_key[key] for key in order])


def merge_topics(responses: list[TopicListResponse]) -> TopicListResponse:
    """Merge per-chunk topics; keep the highest importance per name."""
    by_key: dict[str, Topic] = {}
    order: list[str] = []

    for response in responses:
        for topic in response.topics:
            key = _normalise(topic.name)
            if key not in by_key:
                by_key[key] = topic
                order.append(key)
            else:
                existing = by_key[key]
                if _IMPORTANCE_RANK[topic.importance] > _IMPORTANCE_RANK[existing.importance]:
                    by_key[key] = topic

    return TopicListResponse(topics=[by_key[key] for key in order])


async def merge_summaries(
    partials: list[SummaryResponse], llm: LLMService
) -> SummaryResponse:
    """Reduce per-chunk summaries into one final summary.

    Small local models sometimes return valid JSON with the wrong keys
    (e.g. {"topic": ..., "points": ...}). We retry once with a stricter
    reminder, then fall back to merging the partials programmatically so a
    mislabelled JSON object degrades the answer instead of failing the API.
    """
    user_prompt = chunked_prompts.build_reduce_user_prompt(partials)
    try:
        return await llm.generate_structured(
            system_prompt=chunked_prompts.REDUCE_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=SummaryResponse,
        )
    except LLMInvalidResponse:
        logger.warning("Reduce step returned invalid JSON; retrying with stricter reminder.")
        try:
            return await llm.generate_structured(
                system_prompt=chunked_prompts.REDUCE_SYSTEM_PROMPT,
                user_prompt=user_prompt
                + '\nCRITICAL: output ONE JSON object with exactly two keys: '
                '"summary" (string) and "key_points" (list of strings). '
                "No other keys.\n",
                response_model=SummaryResponse,
            )
        except LLMInvalidResponse:
            logger.warning("Reduce retry also invalid; merging partials programmatically.")
            return _fallback_merge_summaries(partials)


def _fallback_merge_summaries(
    partials: list[SummaryResponse],
) -> SummaryResponse:
    """Deterministic reduce: join unique partial summaries and key points."""
    summaries: list[str] = []
    points: list[str] = []
    seen_summaries: set[str] = set()
    seen_points: set[str] = set()

    for partial in partials:
        summary = partial.summary.strip()
        if summary and _normalise(summary) not in seen_summaries:
            seen_summaries.add(_normalise(summary))
            summaries.append(summary)
        for point in partial.key_points:
            if _normalise(point) not in seen_points:
                seen_points.add(_normalise(point))
                points.append(point)

    return SummaryResponse(summary=" ".join(summaries), key_points=points[:7])