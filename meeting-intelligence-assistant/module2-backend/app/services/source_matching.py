"""Deterministic source enrichment for AI-extracted items.

The extraction LLM does not reliably copy the transcript's section id, and it
sometimes leaves ``assignee`` null even when its own evidence quote names the
person (``"Jamie: I'll fix the PDF parser"`` or ``"Priya, can you own the
user guide?"``). These helpers anchor every item to a stored transcript
section and fill only facts the evidence states explicitly.

Enrichment runs when a result is read, not when it is generated, so payloads
already stored in ``analysis_results`` are repaired without a cache bump.
"""

import re
from typing import Any

_WORD_RE = re.compile(r"[a-z0-9]+")
_SPEAKER_PREFIX_RE = re.compile(r"^\s*([A-Z][\w .'-]{0,39}?)\s*:\s*(.*)$")
_FIRST_PERSON_RE = re.compile(
    r"\bi\s*(?:'ll|’ll| will| can| am|'m|’m|'d|’d)\b", re.IGNORECASE
)
_ASSIGNMENT_PATTERNS = (
    # "Priya, can you own the user guide?"
    re.compile(
        r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*,?\s*"
        r"(?:can|could|would|will)\s+you\b"
    ),
    # "assign the guide to Priya" / "assigned it to Priya"
    re.compile(
        r"\bassign(?:ed|ing)?\s+(?:it|this|that|the\s+[\w ]{1,40}?)?\s*to\s+"
        r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b",
        re.IGNORECASE,
    ),
    # "Priya will own the user guide" / "Taylor is going to raise the timeout"
    re.compile(
        r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+"
        r"(?:will|is going to|shall|agreed to)\s+"
        r"(?:own|write|prepare|fix|handle|take|send|review|raise|update|"
        r"draft|create|build|follow|check|share|schedule|book|run)\b"
    ),
    # "Priya can own the guide" / "Taylor can update the timeout"
    re.compile(
        r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+"
        r"(?:can|could|should)\s+"
        r"(?:own|write|prepare|fix|handle|take|send|review|raise|update|"
        r"draft|create|build|follow|check|share|schedule|book|run)\b"
    ),
)

_NON_NAMES = {
    "i",
    "we",
    "the",
    "this",
    "that",
    "they",
    "he",
    "she",
    "it",
    "please",
    "everyone",
    "someone",
    "nobody",
}
_EMPTY_ASSIGNEES = {
    "",
    "unassigned",
    "unknown",
    "none",
    "null",
    "n/a",
    "na",
    "tbd",
    "not stated",
    "not assigned",
}


def _normalise_time(value: str | None) -> str:
    """Drop milliseconds so 00:01:23.500 and 00:01:23 compare equal."""
    return re.sub(r"[.,]\d+$", "", value or "").strip()


def _tokens(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def _strip_speaker(evidence: str) -> tuple[str | None, str]:
    """Split ``"Jamie: I'll fix it"`` into ``("Jamie", "I'll fix it")``."""
    match = _SPEAKER_PREFIX_RE.match(evidence or "")
    if match is None:
        return None, evidence or ""
    return match.group(1).strip(), match.group(2).strip()


def _speaker_key(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def match_section(
    evidence: str,
    timestamp: str | None,
    sections: list[dict],
) -> dict | None:
    """Return the stored transcript section an item's evidence came from.

    Evidence overlap is the primary signal; a matching timestamp is only used
    when the evidence is too weak to score. A weak match returns ``None`` so
    the UI can say it could not pinpoint the passage instead of jumping to an
    unrelated part of the transcript.
    """
    if not sections:
        return None

    speaker, body = _strip_speaker(evidence or "")
    evidence_tokens = set(_tokens(body))
    evidence_time = _normalise_time(timestamp)

    best: dict | None = None
    best_score = 0.0

    for section in sections:
        section_tokens = set(_tokens(section.get("text") or ""))
        if not evidence_tokens or not section_tokens:
            continue

        overlap = len(evidence_tokens & section_tokens)
        if overlap < 2:
            continue

        coverage = overlap / len(evidence_tokens)
        if coverage < 0.5:
            continue

        precision = overlap / len(section_tokens)
        score = coverage + (0.05 * precision)

        section_speaker = _speaker_key(section.get("speaker_name"))
        if speaker and section_speaker and speaker.lower() == section_speaker:
            score += 0.2
        if evidence_time and _normalise_time(section.get("timestamp")) == evidence_time:
            score += 0.1

        if score > best_score:
            best = section
            best_score = score

    if best is not None:
        return best

    if evidence_time:
        for section in sections:
            if _normalise_time(section.get("timestamp")) == evidence_time:
                return section

    return None


def _clean_name(value: str | None) -> str | None:
    if not value:
        return None
    name = re.sub(r"\s+", " ", value).strip(" .,:;!?\"'")
    if not name or name.lower() in _NON_NAMES:
        return None
    return name


def derive_assignee(evidence: str, section: dict | None) -> str | None:
    """Extract an assignee that the evidence states explicitly.

    This is not inference: first-person wording is attributed to the person
    who said the quote, and named assignments are taken verbatim. Anything
    ambiguous leaves the item unassigned.
    """
    speaker, body = _strip_speaker(evidence or "")
    text = body or evidence or ""

    for pattern in _ASSIGNMENT_PATTERNS:
        match = pattern.search(text)
        if match:
            name = _clean_name(match.group(1))
            if name:
                return name

    if _FIRST_PERSON_RE.search(text):
        if speaker:
            return _clean_name(speaker)
        if section is not None:
            return _clean_name(section.get("speaker_name"))

    return None


def _has_assignee(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    return value.strip().lower() not in _EMPTY_ASSIGNEES


def enrich_analysis(
    payload: dict[str, Any],
    sections: list[dict],
    kind: str,
) -> dict[str, Any]:
    """Return a copy of ``payload`` with section ids and assignees filled in.

    ``kind`` is ``"action_items"`` or ``"decisions"``. An extracted assignee
    is kept, but a confidently matched section replaces the section id and
    timestamp so the link and the displayed time cannot disagree.
    """
    items_key = "action_items" if kind == "action_items" else "decisions"
    items = payload.get(items_key)
    if not isinstance(items, list):
        return payload

    enriched: list[Any] = []
    for item in items:
        if not isinstance(item, dict):
            enriched.append(item)
            continue

        copy = dict(item)
        evidence = copy.get("evidence") or ""
        matched = match_section(evidence, copy.get("timestamp"), sections)

        if matched is not None:
            # The matched section is the source of truth: the id and the time
            # shown next to "View in transcript" must point at the same turn.
            if matched.get("section_id"):
                copy["section_id"] = matched["section_id"]
            if matched.get("timestamp"):
                copy["timestamp"] = matched["timestamp"]

        if kind == "action_items" and not _has_assignee(copy.get("assignee")):
            assignee = derive_assignee(evidence, matched)
            if assignee:
                copy["assignee"] = assignee

        enriched.append(copy)

    result = dict(payload)
    result[items_key] = enriched
    return result
