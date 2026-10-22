# Define:
#
# TranscriptResponse
# TranscriptUploadResponse
# ProcessingStatus

from datetime import date, time

from pydantic import BaseModel

class TranscriptSection(BaseModel):
    section_id: str
    speaker_id: str
    speaker_name: str
    text: str
    timestamp: str | None = None

class TranscriptResponse(BaseModel):
    meeting_id: int
    title: str
    meeting_date: date | None = None
    meeting_start_time: time | None = None
    sections: list[TranscriptSection]
