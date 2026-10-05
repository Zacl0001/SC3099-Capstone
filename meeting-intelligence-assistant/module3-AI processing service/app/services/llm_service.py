"""Single abstraction around the LLM provider.

This is the module's central "response generation" piece. Everything
else (summarization, actions, decisions, topics) goes through this class,
so swapping the local model for OpenAI/Anthropic later means changing
only the base URL / model name here.

It talks to Ollama's OpenAI-compatible chat completions endpoint:
    POST {base_url}/chat/completions
"""

import json
import re
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.logging import get_logger
from app.services.exceptions import (
    LLMConnectionError,
    LLMHTTPError,
    LLMInvalidResponse,
    LLMTimeoutError,
    LLMTransientError,
)

logger = get_logger(__name__)

# A Pydantic model type, e.g. SummaryResponse. Used by generate_structured.
TModel = TypeVar("TModel", bound=BaseModel)

# Guard so a runaway LLM response cannot consume unbounded memory.
_MAX_RESPONSE_CHARS = 100_000


class LLMService:
    """Thin async client for chat-completion LLM calls."""

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
        temperature: float = 0.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.max_retries = max_retries
        self.temperature = temperature
        # httpx.AsyncClient pools connections and is reused across requests.
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds))

    async def close(self) -> None:
        """Release the underlying HTTP connection pool."""
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Send a chat request and return the raw text response."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return await self._chat(messages)

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[TModel],
    ) -> TModel:
        """Ask the LLM for JSON and validate it against a Pydantic model.

        The output of this method is *trusted application data*: even if
        the LLM returns extra fields, malformed values, or a list instead
        of an object, response_model normalises or rejects it.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        raw = await self._chat(messages, json_mode=True)
        data = _parse_json_object(raw)
        if not isinstance(data, dict):
            raise LLMInvalidResponse("LLM returned a non-object JSON value.")
        try:
            return response_model.model_validate(data)
        except ValidationError as exc:
            # Include the first error so devs can fix the prompt/schema.
            first_error = exc.errors()[0] if exc.errors() else {}
            raise LLMInvalidResponse(
                f"LLM output failed Pydantic validation: {first_error}"
            ) from exc

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _chat(self, messages: list[dict], json_mode: bool = False) -> str:
        """POST to /chat/completions with automatic retry on transient errors.

        AsyncRetrying wraps the call and re-invokes it on transient
        failures with exponential backoff, until max_retries is reached.
        Permanent failures (LLMInvalidResponse) propagate immediately.
        """
        retrier = AsyncRetrying(
            reraise=True,
            retry=retry_if_exception_type(LLMTransientError),
            stop=stop_after_attempt(self.max_retries + 1),
            wait=wait_exponential(multiplier=1, min=1, max=8),
        )
        async for attempt in retrier:
            with attempt:
                return await self._do_chat(messages, json_mode)

    async def _do_chat(self, messages: list[dict], json_mode: bool) -> str:
        """A single, non-retried chat completion request."""
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }
        if json_mode:
            # Ask the provider to bias output toward valid JSON.
            payload["response_format"] = {"type": "json_object"}

        try:
            response = await self._client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
            )
        except httpx.ConnectError as exc:
            raise LLMConnectionError(f"Cannot reach LLM at {self.base_url}") from exc
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError("LLM request timed out") from exc

        if response.status_code >= 500:
            raise LLMHTTPError(f"LLM server error: HTTP {response.status_code}")
        if response.status_code >= 400:
            raise LLMInvalidResponse(
                f"LLM rejected the request: HTTP {response.status_code}: {response.text[:500]}"
            )

        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as exc:
            raise LLMInvalidResponse("Unexpected LLM response shape.") from exc

        if not isinstance(content, str) or len(content) > _MAX_RESPONSE_CHARS:
            raise LLMInvalidResponse("LLM response content is missing or too large.")

        # Trim surrounding whitespace so _parse_json_object sees clean input.
        return content.strip()


def _parse_json_object(raw: str) -> Any:
    """Best-effort parse of a JSON object from raw LLM text.

    Some local models wrap output in ```json fences or add preamble,
    so we first try plain parsing, then strip code fences, then fall
    back to extracting the largest {...} span.
    """
    candidates: list[str] = []

    if raw.startswith("{") and raw.endswith("}"):
        candidates.append(raw)

    # Markdown code fence: ```json\n{...}\n```
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, re.DOTALL)
    if fenced:
        candidates.append(fenced.group(1))

    # Anything between the first { and the last }.
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end > start:
        candidates.append(raw[start : end + 1])

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    raise LLMInvalidResponse(
        f"Could not parse JSON from LLM output (first 200 chars): {raw[:200]!r}"
    )