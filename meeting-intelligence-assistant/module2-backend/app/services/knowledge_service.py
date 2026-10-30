"""HTTP client for the Knowledge Assistant Service (module4, port 8002).

The KAS owns chunking, embeddings and the vector store; this module only
sends already-parsed transcripts and search queries over HTTP.
"""

from typing import Any

import httpx

from app.core.config import KNOWLEDGE_SERVICE_URL, KNOWLEDGE_TIMEOUT_SECONDS


class KnowledgeServiceError(RuntimeError):
    """Raised when the knowledge service is unreachable or returns an error."""


def _post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"{KNOWLEDGE_SERVICE_URL}{path}"
    # Fail fast when the service is down, but allow long embedding runs.
    timeout = httpx.Timeout(KNOWLEDGE_TIMEOUT_SECONDS, connect=10.0)
    try:
        response = httpx.post(url, json=payload, timeout=timeout)
    except httpx.HTTPError as exc:
        raise KnowledgeServiceError(
            f"Knowledge service unreachable at {KNOWLEDGE_SERVICE_URL}: {exc}"
        ) from exc

    if response.status_code >= 400:
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
