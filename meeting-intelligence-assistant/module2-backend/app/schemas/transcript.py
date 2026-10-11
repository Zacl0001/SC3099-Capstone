# Define:
#
# TranscriptResponse
# TranscriptUploadResponse
# ProcessingStatus

from pydantic import BaseModel

class TranscriptSection(BaseModel):
    section_id: str
    speaker_id: str
    speaker_name: str
    text: str

class TranscriptResponse(BaseModel):
    meeting_id: int
    title: str
    sections: list[TranscriptSection]