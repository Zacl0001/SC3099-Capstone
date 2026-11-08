# Database cache for AI analysis output.
#
# One row per (meeting, analysis kind). The transcript hash records which
# transcript the payload was generated from, so a changed or re-processed
# transcript invalidates the entry instead of serving stale AI output.
#
# Kinds used by the routes: summary, action_items, decisions, topics.

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.db.database import Base


class AnalysisResult(Base):
    __tablename__ = "analysis_results"
    __table_args__ = (
        UniqueConstraint("meeting_id", "kind", name="uq_analysis_results_meeting_kind"),
    )

    id = Column(Integer, primary_key=True)

    meeting_id = Column(
        Integer,
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # "summary" | "action_items" | "decisions" | "topics"
    kind = Column(String(32), nullable=False)

    # SHA-256 of (cache version + transcript text).
    transcript_hash = Column(String(64), nullable=False)

    # Exactly the JSON body module3 returned, so routes can pass it through.
    payload = Column(JSONB, nullable=False)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
