"""Response schema for meeting summarization."""

from pydantic import BaseModel, Field


class SummaryResponse(BaseModel):
    """Structured summary produced from a transcript."""

    summary: str = Field(
        ...,
        description="Concise executive summary of the meeting.",
    )

    key_points: list[str] = Field(
        default_factory=list,
        description="The most important discussion points.",
    )