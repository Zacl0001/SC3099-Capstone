"""HTTP client for the AI processing service (module3, port 8001).

This module only moves data over HTTP. Prompting and LLM logic stay in
module3; these helpers keep the backend routes thin.

Every analysis endpoint in module3 takes:
    {"meeting_id": "<string>", "transcript": "<full text>"}
"""

from typing import Any

import httpx

from app.core.config import AI_SERVICE_URL, AI_TIMEOUT_SECONDS


class AIServiceError(RuntimeError):
    """Raised when module3 is unreachable or returns an error."""


def _post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"{AI_SERVICE_URL}{path}"
    try:
        response = httpx.post(url, json=payload, timeout=AI_TIMEOUT_SECONDS)
    except httpx.HTTPError as exc:
        raise AIServiceError(f"AI service unreachable at {AI_SERVICE_URL}: {exc}") from exc

    if response.status_code >= 400:
        raise AIServiceError(
            f"AI service returned {response.status_code}: {response.text}"
        )

    try:
        return response.json()
    except ValueError as exc:
        raise AIServiceError("AI service returned a non-JSON response") from exc


def generate_summary(meeting_id: str, transcript: str) -> dict[str, Any]:
    """POST /summarize -> {summary, key_points}."""
    return _post("/summarize", {"meeting_id": meeting_id, "transcript": transcript})


def extract_action_items(meeting_id: str, transcript: str) -> dict[str, Any]:
    """POST /actions -> {action_items: [...]}."""
    return _post("/actions", {"meeting_id": meeting_id, "transcript": transcript})


def extract_decisions(meeting_id: str, transcript: str) -> dict[str, Any]:
    """POST /decisions -> {decisions: [...]}."""
    return _post("/decisions", {"meeting_id": meeting_id, "transcript": transcript})


def extract_topics(meeting_id: str, transcript: str) -> dict[str, Any]:
    """POST /topics -> {topics: [...]}."""
    return _post("/topics", {"meeting_id": meeting_id, "transcript": transcript})


def ask_question(
    meeting_id: str, question: str, top_k: int | None = None
) -> dict[str, Any]:
    """POST /chat -> {answer, citations: [...]}."""
    payload: dict[str, Any] = {"meeting_id": meeting_id, "question": question}
    if top_k is not None:
        payload["top_k"] = top_k
    return _post("/chat", payload)
