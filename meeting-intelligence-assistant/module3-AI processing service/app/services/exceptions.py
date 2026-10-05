"""Custom exceptions for the LLM service.

Separate exception types let the API layer decide the HTTP status code
(e.g. 502 for an unreachable LLM) without the routes needing to know
HTTP details, AND they let the retry logic target only *transient*
failures.
"""


class LLMError(Exception):
    """Base class for all LLM-related errors."""


class LLMTransientError(LLMError):
    """A temporary failure that is worth retrying.

    Examples: the LLM server is unreachable, the request timed out,
    or the server returned a 5xx. These may succeed on retry.
    """


class LLMConnectionError(LLMTransientError):
    """Could not reach the LLM server at all (DNS/connection refused)."""


class LLMTimeoutError(LLMTransientError):
    """The LLM did not respond within the configured timeout."""


class LLMHTTPError(LLMTransientError):
    """The LLM server returned an error HTTP status."""


class LLMInvalidResponse(LLMError):
    """The LLM answered but the response could not be parsed.

    This is a *permanent* failure: retrying will not fix a malformed
    JSON body (a different prompt or model might, though).
    """