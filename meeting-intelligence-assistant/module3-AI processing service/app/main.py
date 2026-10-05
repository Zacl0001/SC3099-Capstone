"""FastAPI entry point for the AI Processing Service.

Responsibilities:
  - create the FastAPI app
  - register routers (/summarize, /actions, /decisions, /topics)
  - create/release the shared LLMService via lifespan
  - expose /health and /
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import actions, decisions, summarize, topics
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.services.exceptions import LLMError
from app.services.llm_service import LLMService

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run once at startup (before yield) and shutdown (after yield)."""
    settings = get_settings()
    setup_logging(settings.log_level)

    app.state.llm_service = LLMService(
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
        temperature=settings.llm_temperature,
    )
    logger.info("AI Processing Service started (model=%s)", settings.llm_model)

    yield  # app is now serving requests

    await app.state.llm_service.close()
    logger.info("AI Processing Service shut down")


app = FastAPI(
    title="AI Processing Service",
    description="Analyzes meeting transcripts: summarization, action items, "
    "decisions, and topics, powered by a local LLM.",
    version="1.0.0",
    lifespan=lifespan,
)

# This service is called server-to-server by the backend; permissive CORS is fine.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(LLMError)
async def llm_error_handler(request: Request, exc: LLMError):
    """Any upstream LLM failure becomes a 502 Bad Gateway.

    The client (backend) sees a clear message instead of an opaque 500,
    and logged details remain available server-side.
    """
    logger.error("LLM error: %s", exc)
    return JSONResponse(status_code=502, content={"detail": str(exc)})


app.include_router(summarize.router)
app.include_router(actions.router)
app.include_router(decisions.router)
app.include_router(topics.router)


@app.get("/health")
async def health():
    """Liveness probe used by Docker/load balancers."""
    settings = get_settings()
    return {"status": "healthy", "model": settings.llm_model}


@app.get("/")
async def root():
    """Human-readable endpoint index."""
    return {
        "service": "AI Processing Service",
        "version": "1.0.0",
        "endpoints": [
            "POST /summarize",
            "POST /actions",
            "POST /decisions",
            "POST /topics",
            "GET /health",
        ],
    }