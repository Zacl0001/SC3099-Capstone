"""Response schema for decision extraction."""

from pydantic import BaseModel, Field


class Decision(BaseModel):
    """A decision reached during the meeting."""

    decision: str = Field(..., description="What was decided.")
    evidence: str = Field(..., description="Short quote from the transcript supporting this.")
    timestamp: str | None = Field(None, description="When in the meeting this decision was made, if available.")


class DecisionListResponse(BaseModel):
    """Wrapper object containing all extracted decisions."""

    decisions: list[Decision]