from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from app.db.database import Base

class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id = Column(Integer, primary_key=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    token_hash = Column(String(64), unique=True, nullable=False)

    expires_at = Column(DateTime(timezone=True), nullable=False)