# Schemas for meeting Q&A.

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=20)


class CitationResponse(BaseModel):
    chunk_id: str
    start_time: str | None = None
    end_time: str | None = None
    speaker: str | None = None
    text: str


class ChatResponse(BaseModel):
    answer: str
    citations: list[CitationResponse] = Field(default_factory=list)
