"""Helpers for running the analysis endpoints on long transcripts.

Strategy:
  - short transcripts: pass straight through unchanged (one LLM call);
  - long transcripts: split into semantic chunks via the KAS /chunk endpoint,
    run the existing extraction per chunk, then merge the per-chunk results.

Summary uses map-reduce (`merge_summaries`); action items / decisions / topics
use per-chunk extraction plus keyed de-duplication.
"""

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
    """Return the pieces the analysis should run on.

    If there is no KAS client (offline/backwards compatible) or the transcript
    is within the context budget, a single piece (the whole transcript) is
    returned and no network call happens.
    """
    threshold = get_settings().chunk_threshold_chars

    if kas is None or len(transcript) <= threshold:
        return [transcript]

    chunks = await kas.chunk(meeting_id, transcript)
    cleaned = [chunk.strip() for chunk in chunks if chunk and chunk.strip()]

    # Even an aggressive chunker must not leave us with nothing.
    return cleaned or [transcript]


def _normalise(text: str) -> str:
    return " ".join(text.lower().split())


async def map_chunks(chunks: list[str], extract_chunk) -> list:
    """Run extract_chunk over every chunk, tolerating flaky local-model JSON.

    Small models occasionally return valid JSON with the wrong keys, most
    often on large chunks. Strategy: retry the failed chunk once, then skip
    it (losing that slice of detail beats failing the whole request).
    Raises only if EVERY chunk fails, i.e. we have nothing to merge.
    """
    results = []
    total = len(chunks)

    for position, chunk in enumerate(chunks, 1):
        try:
            results.append(await extract_chunk(chunk))
            continue
        except LLMInvalidResponse:
            logger.warning(
                "Chunk %d/%d returned invalid JSON; retrying once.",
                position,
                total,
            )
        try:
            results.append(await extract_chunk(chunk))
        except LLMInvalidResponse:
            logger.warning(
                "Chunk %d/%d failed again; skipping this chunk.", position, total
            )

    if not results:
        raise LLMInvalidResponse(
            f"All {total} chunk extraction attempts returned invalid JSON."
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