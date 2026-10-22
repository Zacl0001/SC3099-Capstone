"""Tests for the KAS HTTP client, using httpx.MockTransport (no real network)."""

import json

import httpx
import pytest

from app.services.exceptions import (
    KASHTTPError,
    KASInvalidResponse,
)
from app.services.kas_client import KASClient

SEARCH_BODY = {
    "query": "why",
    "results": [
        {
            "text": "Jamie: database connection error.",
            "score": 0.9,
            "meeting_id": "m1",
            "title": "Debugging",
            "meeting_date": "2026-09-30",
            "meeting_start_time": "09:15:00",
            "speakers": ["Alex", "Jamie"],
            "section_metadata": [
                {"section_id": "s2", "speaker": "Jamie", "timestamp": "00:00:08"}
            ],
        }
    ],
}

CHUNK_BODY = {
    "meeting_id": "m1",
    "chunks": [
        {"chunk_index": 0, "text": "Alice: release date should be October first."},
        {"chunk_index": 1, "text": "Bob: agreed."},
    ],
}


def make_client(
    handler, max_retries: int = 1, timeout_seconds: float = 5.0
) -> KASClient:
    transport = httpx.MockTransport(handler)
    return KASClient(
        base_url="http://test-kas",
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        top_k=5,
        transport=transport,
    )


async def test_search_parses_results_and_builds_url():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["method"] = request.method
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=SEARCH_BODY)

    client = make_client(handler)
    chunks = await client.search("m1", "why did it break?", top_k=7)

    assert captured["method"] == "POST"
    assert captured["url"] == "http://test-kas/search"
    assert captured["body"] == {"meeting_id": "m1", "query": "why did it break?", "top_k": 7}
    assert len(chunks) == 1
    assert chunks[0].text == SEARCH_BODY["results"][0]["text"]
    assert chunks[0].section_metadata[0].speaker == "Jamie"

    await client.close()


async def test_search_default_top_k():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"query": "q", "results": []})

    client = make_client(handler)
    await client.search("m1", "q")

    assert captured["body"]["top_k"] == 5

    await client.close()


async def test_chunk_returns_texts():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=CHUNK_BODY)

    client = make_client(handler)
    texts = await client.chunk("m1", "full transcript")

    assert captured["body"] == {"meeting_id": "m1", "transcript": "full transcript"}
    assert texts == ["Alice: release date should be October first.", "Bob: agreed."]

    await client.close()


async def test_chunk_sends_transcript_without_meeting_id_when_none():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"chunks": [{"chunk_index": 0, "text": "t"}]})

    client = make_client(handler)
    await client.chunk(None, "full transcript")

    assert captured["body"] == {"transcript": "full transcript"}

    await client.close()


async def test_server_error_is_retried_then_raised():
    attempts = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        return httpx.Response(500, text="boom")

    client = make_client(handler, max_retries=1)

    with pytest.raises(KASHTTPError):
        await client.search("m1", "q")

    assert len(attempts) == 2  # initial attempt + 1 retry

    await client.close()


async def test_client_error_is_permanent_no_retry():
    attempts = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        return httpx.Response(400, json={"detail": "bad request"})

    client = make_client(handler, max_retries=1)

    with pytest.raises(KASInvalidResponse):
        await client.search("m1", "q")

    assert len(attempts) == 1

    await client.close()


async def test_search_malformed_results_raise():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"query": "q", "results": [{}]})

    client = make_client(handler)

    with pytest.raises(KASInvalidResponse):
        await client.search("m1", "q")

    await client.close()


async def test_chunk_malformed_body_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"chunks": "not a list"})

    client = make_client(handler)

    with pytest.raises(KASInvalidResponse):
        await client.chunk("m1", "t")

    await client.close()