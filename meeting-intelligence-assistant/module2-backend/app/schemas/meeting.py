# Define:
#
# MeetingCreate
# MeetingResponse
# MeetingUpdate

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

class CreateMeeting(BaseModel):
    model_config =  ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=255)

class MeetingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    created_at: datetime