# Represents:
#
# meetings
# Fields:
#
# id
# user_id
# title
# description
# status
# created_at
# updated_at
# Relationships:
#
# User → Meetings
# Meeting → Transcript
# Meeting → Summary
# Meeting → Actions
# Meeting → Decisions

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func

from app.db.database import Base

class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    title = Column(String(255), nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
