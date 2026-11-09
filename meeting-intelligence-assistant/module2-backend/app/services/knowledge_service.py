"""HTTP client for the Knowledge Assistant Service (module4, port 8002).

The KAS owns chunking, embeddings and the vector store; this module only
sends already-parsed transcripts and search queries over HTTP.
"""

from os import path
from typing import Any
from urllib.parse import quote

import httpx
import logging
import time

from app.core.config import KNOWLEDGE_SERVICE_URL, KNOWLEDGE_TIMEOUT_SECONDS


logger = logging.getLogger(__name__)

class KnowledgeServiceError(RuntimeError):
    """Raised when the knowledge service is unreachable or returns an error."""


def _post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    start_time = time.perf_counter()
    logger.info("Knowledge service request started | endpoint=%s", path)
    url = f"{KNOWLEDGE_SERVICE_URL}{path}"
    # Fail fast when the service is down, but allow long embedding runs.
    timeout = httpx.Timeout(KNOWLEDGE_TIMEOUT_SECONDS, connect=10.0)
    try:
        response = httpx.post(url, json=payload, timeout=timeout)
    except httpx.HTTPError as exc:
        logger.exception(
            "Knowledge service connection failed | endpoint=%s",
            path,
        )
        raise KnowledgeServiceError(
            f"Knowledge service unreachable at {KNOWLEDGE_SERVICE_URL}: {exc}"
        ) from exc

    if response.status_code >= 400:
        logger.error(
            "Knowledge service returned an error | endpoint=%s | status=%s",
            path,
            response.status_code,
        )
        raise KnowledgeServiceError(
            f"Knowledge service returned {response.status_code}: {response.text}"
        )

    try:
        return response.json()
    except ValueError as exc:
        raise KnowledgeServiceError(
            "Knowledge service returned a non-JSON response"
        ) from exc


def ingest_transcript(meeting: dict[str, Any]) -> dict[str, Any]:
    """POST /ingest. `meeting` must match the KAS IngestRequest shape."""
    return _post("/ingest", meeting)


def delete_meeting_chunks(meeting_id: str) -> None:
    """Delete KAS chunks before removing the backend meeting records."""
    url = f"{KNOWLEDGE_SERVICE_URL}/meetings/{quote(meeting_id, safe='')}"
    timeout = httpx.Timeout(KNOWLEDGE_TIMEOUT_SECONDS, connect=10.0)
    try:
        response = httpx.delete(url, timeout=timeout)
    except httpx.HTTPError as exc:
        raise KnowledgeServiceError(
            "Could not delete meeting chunks; meeting kept. Please retry."
        ) from exc
    if not 200 <= response.status_code < 300:
        raise KnowledgeServiceError(
            f"Chunk deletion returned {response.status_code}; meeting kept. Please retry."
        )


def search(meeting_id: str, query: str, top_k: int = 5) -> dict[str, Any]:
    """POST /search -> {query, results: [...]}."""
    return _post(
        "/search",
        {"meeting_id": meeting_id, "query": query, "top_k": top_k},
    )


def chunk(transcript: str, meeting_id: str | None = None) -> dict[str, Any]:
    """POST /chunk -> {meeting_id, chunks: [...]}."""
    payload: dict[str, Any] = {"transcript": transcript}
    if meeting_id is not None:
        payload["meeting_id"] = meeting_id
    return _post("/chunk", payload)
