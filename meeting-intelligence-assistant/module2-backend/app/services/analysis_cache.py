"""Database-backed cache for AI analysis results.

The GET endpoints for summary / action items / decisions / topics are not
idempotent: each one runs an LLM. Reusing the stored payload keeps a page
reload from paying that cost again.

Cache key: (meeting_id, kind). The transcript hash is stored with the row and
must match the current transcript for a hit, so editing or re-processing a
transcript invalidates it automatically. Bump ``CACHE_VERSION`` when the
module3 prompts or schemas change.
"""

import hashlib
import threading
from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.analysis_result import AnalysisResult

import logging

logger = logging.getLogger(__name__)

# Bump when module3's prompts or response schemas change so old payloads are
# not reused.
CACHE_VERSION = "1"

_locks_guard = threading.Lock()
_locks: dict[tuple[int, str], threading.Lock] = {}


def transcript_hash(transcript: str) -> str:
    """Hash the transcript together with the cache version."""
    data = f"{CACHE_VERSION}\n{transcript}".encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _lock_for(meeting_id: int, kind: str) -> threading.Lock:
    key = (meeting_id, kind)
    with _locks_guard:
        lock = _locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _locks[key] = lock
        return lock


def get_cached(
    db: Session, meeting_id: int, kind: str, digest: str
) -> dict[str, Any] | None:
    """Return the cached payload, or None when missing/stale."""
    row = db.scalar(
        select(AnalysisResult).where(
            AnalysisResult.meeting_id == meeting_id,
            AnalysisResult.kind == kind,
        )
    )
    if row is None or row.transcript_hash != digest:
        return None
    return row.payload


def store(
    db: Session,
    meeting_id: int,
    kind: str,
    digest: str,
    payload: dict[str, Any],
) -> None:
    """Insert or replace the cached payload.

    Cache writes must never turn a successful AI response into a failed
    request, so database errors are rolled back and ignored.
    """
    try:
        row = db.scalar(
            select(AnalysisResult).where(
                AnalysisResult.meeting_id == meeting_id,
                AnalysisResult.kind == kind,
            )
        )
        if row is None:
            db.add(
                AnalysisResult(
                    meeting_id=meeting_id,
                    kind=kind,
                    transcript_hash=digest,
                    payload=payload,
                )
            )
        else:
            row.transcript_hash = digest
            row.payload = payload

        db.commit()
    except IntegrityError:
        # Another request inserted the row first; keep its value.
        db.rollback()
    except Exception:
        logger.exception(
            "Analysis cache write failed | meeting_id=%s | kind=%s",
            meeting_id,
            kind,
        )
        db.rollback()

def get_or_generate(
    db: Session,
    meeting_id: int,
    kind: str,
    transcript: str,
    generate: Callable[[], dict[str, Any]],
    refresh: bool = False,
) -> dict[str, Any]:

    digest = transcript_hash(transcript)

    if not refresh:
        cached = get_cached(db, meeting_id, kind, digest)

        if cached is not None:
            logger.info(
                "Analysis cache hit | meeting_id=%s | kind=%s",
                meeting_id,
                kind,
            )
            return cached

    logger.info(
        "Analysis cache miss or refresh | meeting_id=%s | kind=%s | refresh=%s",
        meeting_id,
        kind,
        refresh,
    )

    with _lock_for(meeting_id, kind):

        if not refresh:
            cached = get_cached(db, meeting_id, kind, digest)

            if cached is not None:
                logger.info(
                    "Analysis cache hit after lock | meeting_id=%s | kind=%s",
                    meeting_id,
                    kind,
                )
                return cached

        logger.info(
            "AI analysis generation started | meeting_id=%s | kind=%s",
            meeting_id,
            kind,
        )

        try:
            payload = generate()

            logger.info(
                "AI analysis generation completed | meeting_id=%s | kind=%s",
                meeting_id,
                kind,
            )

        except Exception:
            logger.exception(
                "AI analysis generation failed | meeting_id=%s | kind=%s",
                meeting_id,
                kind,
            )
            raise

        store(db, meeting_id, kind, digest, payload)

        return payload
