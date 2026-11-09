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
import time
import uuid
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

TModel = TypeVar("TModel", bound=BaseModel)

_MAX_RESPONSE_CHARS = 100_000

# A 60s default was too low for local CPU inference; local models (esp.
# qwen2.5:7b-instruct on a laptop) can need >1min per generation.  120s gives
# a single attempt a reasonable chance before retries kick in.


class LLMService:
    """Thin async client for chat-completion LLM calls."""

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: float = 120.0,
        max_retries: int = 2,
        temperature: float = 0.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.max_retries = max_retries
        self.temperature = temperature

        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds),
            trust_env=False,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
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
        """Generate JSON and validate it against a Pydantic model."""

        request_id = uuid.uuid4().hex[:8]
        started_at = time.perf_counter()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        schema = response_model.model_json_schema()

        # Include the schema explicitly in the prompt.
        messages[1]["content"] += (
            "\n\nREQUIRED JSON SCHEMA:\n"
            + json.dumps(schema, indent=2)
            + "\nReturn only a JSON object matching this schema."
        )

        logger.info(
            "[LLM:%s] STRUCTURED START | Model=%s | Schema=%s",
            request_id,
            self.model,
            response_model.__name__,
        )

        retrier = AsyncRetrying(
            reraise=True,
            retry=retry_if_exception_type(LLMInvalidResponse),
            stop=stop_after_attempt(2),
            wait=wait_exponential(
                multiplier=1,
                min=1,
                max=4,
            ),
            before_sleep=lambda retry_state: logger.warning(
                "[LLM:%s] RETRY | Attempt=%d | Error=%s",
                request_id,
                retry_state.attempt_number,
                retry_state.outcome.exception(),
            ),
        )

        try:
            async for attempt in retrier:
                with attempt:
                    raw = await self._chat(
                        messages,
                        response_schema={"type": "json_object"},
                    )

                    logger.info(
                        "[LLM:%s] RAW STRUCTURED OUTPUT | %s",
                        request_id,
                        raw[:3000],
                    )

                    data = _parse_json_object(raw)

                    if not isinstance(data, dict):
                        raise LLMInvalidResponse(
                            "LLM returned a non-object JSON value."
                        )

                    try:
                        result = response_model.model_validate(data)

                    except ValidationError as exc:
                        logger.error(
                            "[LLM:%s] VALIDATION FAILED | Errors=%s",
                            request_id,
                            exc.errors(),
                        )

                        raise LLMInvalidResponse(
                            f"LLM output failed validation: {exc.errors()}"
                        ) from exc

                    elapsed = time.perf_counter() - started_at

                    logger.info(
                        "[LLM:%s] STRUCTURED SUCCESS | Duration=%.2fs",
                        request_id,
                        elapsed,
                    )

                    return result

        except Exception as exc:
            logger.exception(
                "[LLM:%s] STRUCTURED FAILED | Error=%s",
                request_id,
                exc,
            )
            raise

        raise LLMInvalidResponse(
            "LLM failed to produce a valid structured response."
        )



    async def _chat(
        self,
        messages: list[dict],
        response_schema: dict | None = None,
    ) -> str:
        retrier = AsyncRetrying(
            reraise=True,
            retry=retry_if_exception_type(LLMTransientError),
            stop=stop_after_attempt(self.max_retries + 1),
            wait=wait_exponential(
                multiplier=1,
                min=1,
                max=8,
            ),
        )

        async for attempt in retrier:
            with attempt:
                return await self._do_chat(
                    messages,
                    response_schema,
                )

        raise LLMInvalidResponse("LLM request failed.")

    async def _do_chat(
        self,
        messages: list[dict],
        response_schema: dict | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }

        if response_schema is not None:
            payload["response_format"] = response_schema

        try:
            response = await self._client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
            )

        except httpx.ConnectError as exc:
            raise LLMConnectionError(
                f"Cannot reach LLM at {self.base_url}"
            ) from exc

        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(
                "LLM request timed out"
            ) from exc

        if response.status_code >= 500:
            raise LLMHTTPError(
                f"LLM server error: HTTP {response.status_code}"
            )

        if response.status_code >= 400:
            raise LLMInvalidResponse(
                f"LLM rejected request: HTTP "
                f"{response.status_code}: {response.text[:500]}"
            )

        try:
            content = response.json()["choices"][0]["message"]["content"]

        except (KeyError, IndexError, ValueError) as exc:
            raise LLMInvalidResponse(
                "Unexpected LLM response shape."
            ) from exc

        if (
            not isinstance(content, str)
            or len(content) > _MAX_RESPONSE_CHARS
        ):
            raise LLMInvalidResponse(
                "LLM response content is missing or too large."
            )

        logger.debug(
            "LLM response received. Model=%s Length=%d",
            self.model,
            len(content),
        )

        return content.strip()


def _parse_json_object(raw: str) -> Any:
    """Parse a JSON object from raw LLM output."""

    candidates: list[str] = []

    if raw.startswith("{") and raw.endswith("}"):
        candidates.append(raw)

    fenced = re.search(
        r"```(?:json)?\s*(\{.*\})\s*```",
        raw,
        re.DOTALL,
    )

    if fenced:
        candidates.append(fenced.group(1))

    start, end = raw.find("{"), raw.rfind("}")

    if start != -1 and end > start:
        candidates.append(raw[start:end + 1])

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    logger.warning(
        "Unable to parse LLM JSON. Response preview: %r",
        raw[:1000],
    )

    raise LLMInvalidResponse(
        f"Could not parse JSON from LLM output: {raw[:200]!r}"
    )
