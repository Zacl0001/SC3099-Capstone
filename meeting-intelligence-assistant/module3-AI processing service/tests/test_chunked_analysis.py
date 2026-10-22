"""Tests for chunk-aware analysis: long transcripts go through KAS /chunk,
per-chunk extraction, then merge / map-reduce."""

from app.schemas.summary import SummaryResponse
from app.services.exceptions import KASConnectionError
from tests.conftest import ACTION_PAYLOAD, SAMPLE_TRANSCRIPT, SUMMARY_PAYLOAD

# Longer than the default CHUNK_THRESHOLD_CHARS (20000) so /chunk is triggered.
LONG_TRANSCRIPT = SAMPLE_TRANSCRIPT * 60


def test_short_transcript_never_touches_kas(client, fake_llm, fake_kas):
    fake_llm.payload = SUMMARY_PAYLOAD

    response = client.post(
        "/summarize", json={"meeting_id": "m1", "transcript": SAMPLE_TRANSCRIPT}
    )

    assert response.status_code == 200
    assert fake_kas.chunk_calls == []
    assert len(fake_llm.calls) == 1


def test_summarize_long_transcript_chunks_and_map_reduces(client, fake_llm, fake_kas):
    fake_kas.chunks = ["chunk one", "chunk two", "chunk three"]
    fake_llm.payload = SUMMARY_PAYLOAD

    response = client.post(
        "/summarize", json={"meeting_id": "m1", "transcript": LONG_TRANSCRIPT}
    )

    assert response.status_code == 200
    assert fake_kas.chunk_calls == [("m1", LONG_TRANSCRIPT)]
    # 3 map calls (one per chunk) + 1 reduce call.
    assert len(fake_llm.calls) == 4
    body = response.json()
    assert body["summary"] == SUMMARY_PAYLOAD["summary"]
    assert isinstance(SummaryResponse(**body), SummaryResponse)


def test_actions_on_long_transcript_merge_and_dedupe(client, fake_llm, fake_kas):
    fake_kas.chunks = ["chunk one", "chunk two"]
    fake_llm.payload = ACTION_PAYLOAD  # same action appears in every chunk

    response = client.post(
        "/actions", json={"meeting_id": "m1", "transcript": LONG_TRANSCRIPT}
    )

    assert response.status_code == 200
    assert len(fake_llm.calls) == 2  # one extraction per chunk
    body = response.json()
    assert len(body["action_items"]) == 1  # de-duplicated


def test_long_transcript_with_kas_down_maps_to_502(client, fake_llm, fake_kas):
    fake_kas.chunk_raises = KASConnectionError("KAS unreachable")

    response = client.post(
        "/summarize", json={"meeting_id": "m1", "transcript": LONG_TRANSCRIPT}
    )

    assert response.status_code == 502
    assert fake_llm.calls == []


async def test_merge_decisions_dedupes(fake_llm):
    from app.schemas.decision import Decision, DecisionListResponse
    from app.services.chunked_extraction import merge_decisions

    responses = [
        DecisionListResponse(
            decisions=[
                Decision(decision="Use pgvector", evidence="quote 1", timestamp=None)
            ]
        ),
        DecisionListResponse(
            decisions=[
                Decision(decision="use pgvector", evidence="quote 2", timestamp=None)
            ]
        ),
    ]

    merged = merge_decisions(responses)

    assert len(merged.decisions) == 1
    assert merged.decisions[0].decision == "Use pgvector"


async def test_merge_topics_keeps_highest_importance(fake_llm):
    from app.schemas.topic import Topic, TopicListResponse
    from app.services.chunked_extraction import merge_topics

    responses = [
        TopicListResponse(
            topics=[Topic(name="Budget", description="discussion", importance="LOW")]
        ),
        TopicListResponse(
            topics=[Topic(name="budget", description="approved 50k", importance="HIGH")]
        ),
    ]

    merged = merge_topics(responses)

    assert len(merged.topics) == 1
    assert merged.topics[0].importance == "HIGH"


class _SequenceLLM:
    """Fake LLM that returns a different payload on each structured call.

    Mimics LLMService.generate_structured: invalid payloads raise
    LLMInvalidResponse, not raw ValidationError.
    """

    def __init__(self, payloads):
        self._payloads = list(payloads)
        self.calls = []

    async def generate_structured(self, system_prompt, user_prompt, response_model):
        from pydantic import ValidationError

        from app.services.exceptions import LLMInvalidResponse

        self.calls.append((system_prompt, user_prompt))
        try:
            return response_model.model_validate(self._payloads.pop(0))
        except ValidationError as exc:
            raise LLMInvalidResponse(f"LLM output failed validation: {exc}") from exc


_PARTIALS = [
    SummaryResponse(summary="The team discussed the deployment.", key_points=["Deployment"]),
    SummaryResponse(summary="Pgvector rollout was planned.", key_points=["Pgvector rollout"]),
]

# A valid-JSON-but-wrong-keys shape, like what a small local model produced live.
_WRONG_SHAPE = {"topic": "Meeting", "points": [{"point": "Deployment", "details": "discussed"}]}


async def test_merge_summaries_retries_once_and_recovers():
    from app.services.chunked_extraction import merge_summaries

    llm = _SequenceLLM([_WRONG_SHAPE, SUMMARY_PAYLOAD])

    merged = await merge_summaries(_PARTIALS, llm)

    assert merged.summary == SUMMARY_PAYLOAD["summary"]
    assert len(llm.calls) == 2  # first attempt + one stricter retry


async def test_merge_summaries_falls_back_when_retry_also_invalid():
    from app.services.chunked_extraction import merge_summaries

    llm = _SequenceLLM([_WRONG_SHAPE, _WRONG_SHAPE])

    merged = await merge_summaries(_PARTIALS, llm)

    assert len(llm.calls) == 2  # does not loop forever
    assert merged.summary == "The team discussed the deployment. Pgvector rollout was planned."
    assert merged.key_points == ["Deployment", "Pgvector rollout"]


async def test_map_chunks_retries_failed_chunk_once():
    from app.services.chunked_extraction import map_chunks
    from app.services.exceptions import LLMInvalidResponse

    attempts: dict[str, int] = {}

    async def extractor(chunk: str) -> str:
        attempts[chunk] = attempts.get(chunk, 0) + 1
        if chunk == "flaky" and attempts[chunk] == 1:
            raise LLMInvalidResponse("wrong JSON keys")
        return f"ok:{chunk}"

    results = await map_chunks(["a", "flaky", "c"], extractor)

    assert results == ["ok:a", "ok:flaky", "ok:c"]
    assert attempts["flaky"] == 2


async def test_map_chunks_skips_persistently_bad_chunk():
    from app.services.chunked_extraction import map_chunks
    from app.services.exceptions import LLMInvalidResponse

    async def extractor(chunk: str) -> str:
        if chunk == "bad":
            raise LLMInvalidResponse("wrong JSON keys")
        return f"ok:{chunk}"

    results = await map_chunks(["a", "bad", "c"], extractor)

    assert results == ["ok:a", "ok:c"]  # degraded, but not a 502


async def test_map_chunks_raises_only_when_all_chunks_fail():
    import pytest

    from app.services.chunked_extraction import map_chunks
    from app.services.exceptions import LLMInvalidResponse

    async def extractor(chunk: str) -> str:
        raise LLMInvalidResponse("wrong JSON keys")

    with pytest.raises(LLMInvalidResponse):
        await map_chunks(["a", "b"], extractor)