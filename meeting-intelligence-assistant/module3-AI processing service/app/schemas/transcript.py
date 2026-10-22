"""Shared request schema for all analysis endpoints.

Every endpoint in this service takes the same input: a meeting
identifier plus the raw transcript text.
"""

from pydantic import BaseModel, Field


class TranscriptRequest(BaseModel):
    """Input for summarization / extraction endpoints."""

    meeting_id: str = Field(..., description="Identifier of the meeting.")
    transcript: str = Field(..., min_length=1, description="Full meeting transcript text.")