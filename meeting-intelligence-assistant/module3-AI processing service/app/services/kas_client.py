"""HTTP client for the Knowledge Assistant Service (module4).

"""

from typing import Any

import httpx
from pydantic import ValidationError
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.logging import get_logger
from app.schemas.search import RetrievedChunk, SearchResponse
from app.services.exceptions import (
    KASConnectionError,
    KASHTTPError,
    KASInvalidResponse,
    KASTimeoutError,
    KASTransientError,
)

logger = get_logger(__name__)

_MAX_CHUNKS = 500


class KASClient:
    """Thin async client for the Knowledge Assistant Service endpoints."""

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
        top_k: int = 5,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self.default_top_k = top_k
        # transport is injectable so tests can use httpx.MockTransport.
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds), transport=transport
        )

    async def close(self) -> None:
        """Release the underlying HTTP connection pool."""
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def search(
        self, meeting_id: str, query: str, top_k: int | None = None
    ) -> list[RetrievedChunk]:
        """Retrieve the top-K chunks for a question within one meeting."""
        payload = {
            "meeting_id": meeting_id,
            "query": query,
            "top_k": top_k or self.default_top_k,
        }
        data = await self._request("POST", "/search", payload)
        try:
            parsed = SearchResponse.model_validate(data)
        except ValidationError as exc:
            raise KASInvalidResponse(
                f"KAS /search response failed validation: {exc.errors()[0] if exc.errors() else exc}"
            ) from exc
        # Guard against a pathological response consuming all context.
        return parsed.results[:_MAX_CHUNKS]

    async def chunk(self, meeting_id: str | None, transcript: str) -> list[str]:
        """Split a transcript into semantic chunks WITHOUT indexing them.

        Returns just the chunk texts; the analysis endpoints only need text.
        """
        payload: dict[str, Any] = {"transcript": transcript}
        if meeting_id:
            payload["meeting_id"] = meeting_id

        data = await self._request("POST", "/chunk", payload)
        try:
            chunks = data["chunks"]
            if not isinstance(chunks, list):
                raise TypeError("chunks must be a list")
            texts = [item["text"] for item in chunks if isinstance(item, dict)]
        except (KeyError, TypeError) as exc:
            raise KASInvalidResponse("KAS /chunk response was malformed.") from exc

        return [t for t in texts if isinstance(t, str) and t.strip()]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _request(self, method: str, path: str, json_body: dict) -> dict:
        """POST with automatic retry on transient failures."""
        retrier = AsyncRetrying(
            reraise=True,
            retry=retry_if_exception_type(KASTransientError),
            stop=stop_after_attempt(self.max_retries + 1),
            wait=wait_exponential(multiplier=1, min=1, max=8),
        )
        async for attempt in retrier:
            with attempt:
                return await self._do_request(method, path, json_body)

    async def _do_request(self, method: str, path: str, json_body: dict) -> dict:
        """A single, non-retried KAS request."""
        try:
            response = await self._client.request(
                method, f"{self.base_url}{path}", json=json_body
            )
        except httpx.ConnectError as exc:
            raise KASConnectionError(f"Cannot reach KAS at {self.base_url}") from exc
        except httpx.TimeoutException as exc:
            raise KASTimeoutError("KAS request timed out") from exc

        if response.status_code >= 500:
            raise KASHTTPError(f"KAS server error: HTTP {response.status_code}")
        if response.status_code >= 400:
            raise KASInvalidResponse(
                f"KAS rejected the request: HTTP {response.status_code}: {response.text[:500]}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise KASInvalidResponse("KAS returned non-JSON content.") from exc

        if not isinstance(data, dict):
            raise KASInvalidResponse("KAS response was not a JSON object.")

        return data