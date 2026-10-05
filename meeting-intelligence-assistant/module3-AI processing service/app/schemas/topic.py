"""Response schema for topic identification."""

from typing import Literal

from pydantic import BaseModel, Field

Importance = Literal["HIGH", "MEDIUM", "LOW"]


class Topic(BaseModel):
    """A major topic discussed in the meeting."""

    name: str = Field(..., description="Short name for the topic.")
    description: str = Field(..., description="What was discussed under this topic.")
    importance: Importance = Field(..., description="HIGH, MEDIUM or LOW.")


class TopicListResponse(BaseModel):
    """Wrapper object containing all identified topics."""

    topics: list[Topic]