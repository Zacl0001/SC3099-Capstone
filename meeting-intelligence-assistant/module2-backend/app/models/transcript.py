# Represents uploaded transcripts.
#
# Fields:
#
# id
# meeting_id
# file_name
# storage_path
# raw_text
# duration
# created_at

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from app.db.database import Base

class Transcript(Base):
    __tablename__ = "transcripts"

    id = Column(Integer, primary_key=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False, unique=True,)

    file_name = Column(String(255), nullable=False)
    storage_key = Column(String(1024), nullable=False) #helps to find the uploaded file
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)