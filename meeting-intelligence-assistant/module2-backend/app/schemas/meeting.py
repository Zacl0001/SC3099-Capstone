# Define:
#
# MeetingCreate
# MeetingResponse
# MeetingUpdate

from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field

class CreateMeeting(BaseModel):
    model_config =  ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=255)
    meeting_date: date | None = None
    meeting_start_time: time | None = None

class MeetingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    meeting_date: date | None = None
    meeting_start_time: time | None = None
    created_at: datetime
