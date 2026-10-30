"""
SAIV Backend API - Module 2

FastAPI backend for authentication, meeting uploads, transcript processing,
and the AI/RAG-facing analysis endpoints.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.action_items import router as action_items_router
from app.api.routes.auth import router as auth_router
from app.api.routes.chat import router as chat_router
from app.api.routes.decisions import router as decisions_router
from app.api.routes.meetings import router as meeting_router
from app.api.routes.summaries import router as summaries_router
from app.api.routes.topics import router as topics_router
from app.api.routes.transcripts import router as transcript_router

logger = logging.getLogger(__name__)

app = FastAPI(title="Meeting intelligence Backend")

# The browser normally talks to Next.js, which proxies /api/* here. CORS is
# enabled so the backend can also be called directly during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(meeting_router)
app.include_router(transcript_router)
app.include_router(summaries_router)
app.include_router(action_items_router)
app.include_router(decisions_router)
app.include_router(topics_router)
app.include_router(chat_router)


@app.get("/health")
def health() -> dict:
    return {"status": "healthy"}
