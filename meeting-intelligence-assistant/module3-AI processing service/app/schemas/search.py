"""Schemas for retrieval results from the Knowledge Assistant Service.

"""

from pydantic import BaseModel, Field


class SectionRef(BaseModel):
    """A source section (speaker turn) a retrieved chunk overlaps."""

    section_id: str = Field(...)
    speaker: str = Field(...)
    timestamp: str = Field(...)


class RetrievedChunk(BaseModel):
    """One semantically retrieved transcript chunk."""

    text: str = Field(...)
    score: float = Field(default=0.0)
    meeting_id: str | None = None
    title: str | None = None
    meeting_date: str | None = None
    meeting_start_time: str | None = None
    speakers: list[str] = Field(default_factory=list)
    section_metadata: list[SectionRef] = Field(default_factory=list)


class SearchResponse(BaseModel):
    """Top-level /search response."""

    query: str = Field(...)
    results: list[RetrievedChunk] = Field(default_factory=list)