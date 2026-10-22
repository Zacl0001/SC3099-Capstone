"""Schemas for the RAG question-answering endpoint (/chat)."""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Input for the Q&A endpoint."""

    meeting_id: str = Field(..., description="Which meeting to ask about.")
    question: str = Field(..., min_length=1, description="The user's question.")
    top_k: int | None = Field(
        default=None, ge=1, le=20, description="How many transcript chunks to retrieve."
    )


class Citation(BaseModel):
    """A source a generated answer relies on.

    `index` matches the [n] reference embedded in the answer text.
    """

    index: int = Field(..., description="Citation number referenced as [n] in the answer.")
    text: str = Field(..., description="The retrieved transcript chunk text.")
    speaker: str | None = Field(None, description="Speaker of the cited section, if known.")
    timestamp: str | None = Field(None, description="Timestamp of the cited section, if known.")
    section_id: str | None = Field(None, description="Source section id, if known.")


class ChatResponse(BaseModel):
    """Generated answer plus the sources it relies on."""

    answer: str = Field(...)
    citations: list[Citation] = Field(default_factory=list)