"""FastAPI dependency functions.

Dependencies let FastAPI provide shared objects (like the LLM client)
to route handlers. Routes just declare what they need; tests can
override the resolver with a fake.
"""

from fastapi import Request

from app.services.kas_client import KASClient
from app.services.llm_service import LLMService


def get_llm_service(request: Request) -> LLMService:
    """Return the process-wide LLMService stored on the app at startup."""
    return request.app.state.llm_service


def get_chat_llm_service(request: Request) -> LLMService:
    """Return the LLM used by /chat (may be a stronger model than extraction).

    Falls back to the main LLM service when no separate chat model is set.
    """
    return getattr(
        request.app.state, "chat_llm_service", request.app.state.llm_service
    )


def get_kas_client(request: Request) -> KASClient:
    """Return the process-wide KAS client stored on the app at startup."""
    return request.app.state.kas_client