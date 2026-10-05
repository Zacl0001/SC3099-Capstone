"""Response schema for action item extraction."""

from pydantic import BaseModel, Field


class ActionItem(BaseModel):
    """A single action item agreed in the meeting."""

    task: str = Field(..., description="The concrete task to be done.")
    assignee: str | None = Field(None, description="Who is responsible, if stated.")
    deadline: str | None = Field(None, description="Due date if stated in the transcript.")
    evidence: str = Field(..., description="Short quote from the transcript supporting this item.")
    timestamp: str | None = Field(None, description="When in the meeting this was said, if available.")


class ActionItemListResponse(BaseModel):
    """Wrapper so the top-level JSON object is extensible later
    (e.g. adding an 'error' or 'model' field without breaking clients)."""

    action_items: list[ActionItem]