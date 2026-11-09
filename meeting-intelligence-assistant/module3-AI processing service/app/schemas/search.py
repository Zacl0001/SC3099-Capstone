
"""Schemas for retrieval results from KAS."""

from pydantic import BaseModel, Field




class SectionRef(BaseModel):
    """A source section (speaker turn) a retrieved chunk overlaps."""

    section_id: str = Field(...)
    speaker: str = Field(...)
    timestamp: str = Field(...)
    text: str = Field(default="")


class RetrievedChunk(BaseModel):
    """One semantically retrieved transcript chunk."""

    text: str
    score: float = 0.0

    meeting_id: str | None = None
    title: str | None = None
    meeting_date: str | None = None
    meeting_start_time: str | None = None

    speakers: list[str] = Field(default_factory=list)
    section_metadata: list[SectionRef] = Field(
        default_factory=list
    )


class SearchResponse(BaseModel):
    """Top-level KAS search response."""

    query: str
    results: list[RetrievedChunk] = Field(default_factory=list)
