"""Retrieval-augmented question answering.

Pipeline:
    question -> KAS /search (top-K chunks) -> grounded prompt -> LLM -> answer + citations

KAS chunks are retrieval units and usually span several transcript sections.
The LLM sees one numbered context block per *section* (speaker turn), so each
``[n]`` maps to a single transcript location the UI can show as its own
citation box.
"""

import re
from dataclasses import dataclass, replace

from app.prompts import qa as qa_prompts
from app.schemas.chat import ChatRequest, ChatResponse, Citation
from app.schemas.search import RetrievedChunk, SectionRef
from app.services.kas_client import KASClient
from app.services.llm_service import LLMService

NOT_FOUND_MESSAGE = "I could not find this information in the meeting transcript."

_SECTION_HEADER = re.compile(
    r"^(?P<speaker>[^:\n\[\]]{1,40}?)"
    r"(?:\s*\[(?P<timestamp>\d{1,3}:\d{2}(?::\d{2})?)\])?"
    r"\s*:\s*(?P<text>.*)$"
)


@dataclass
class ContextSection:
    """One speaker turn shown to the LLM as a numbered context block."""

    text: str
    speaker: str | None = None
    timestamp: str | None = None
    section_id: str | None = None

    def prompt_block(self) -> str:
        header = self.speaker or "Speaker"
        if self.timestamp:
            header += f" [{self.timestamp}]"
        return f"{header}: {self.text}".strip()


def _normalise_time(value: str | None) -> str:
    return re.sub(r"[.,]\d+$", "", value or "").strip()


def _split_text(text: str) -> list[ContextSection]:
    """Split chunk text into speaker turns (``Speaker [time]: text``)."""
    sections: list[ContextSection] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        match = _SECTION_HEADER.match(line)
        if match is not None:
            sections.append(
                ContextSection(
                    text=match.group("text").strip(),
                    speaker=match.group("speaker").strip() or None,
                    timestamp=match.group("timestamp"),
                )
            )
        elif sections:
            sections[-1].text = f"{sections[-1].text} {line}".strip()
        else:
            sections.append(ContextSection(text=line))

    return sections


def _attach_metadata(
    sections: list[ContextSection], refs: list[SectionRef]
) -> list[ContextSection]:
    """Attach ``section_id`` / speaker / timestamp from the chunk metadata."""
    if not refs:
        return sections

    used: set[int] = set()
    positional = len(sections) == len(refs)
    result: list[ContextSection] = []

    for position, section in enumerate(sections):
        ref: SectionRef | None = None

        for index, candidate in enumerate(refs):
            if index in used:
                continue

            speaker_matches = candidate.speaker == section.speaker
            time_matches = _normalise_time(candidate.timestamp) == _normalise_time(
                section.timestamp
            )
            # An empty timestamp in either place means "unknown", not a
            # mismatch; the speaker plus ordering still identifies the turn.
            if speaker_matches and (
                time_matches or not candidate.timestamp or not section.timestamp
            ):
                ref = candidate
                used.add(index)
                break

        if ref is None and positional and position not in used:
            ref = refs[position]
            used.add(position)

        if ref is not None:
            section = replace(
                section,
                speaker=section.speaker or ref.speaker,
                timestamp=section.timestamp or ref.timestamp,
                section_id=ref.section_id,
            )

        result.append(section)

    return result


def _chunk_sections(chunk: RetrievedChunk) -> list[ContextSection]:
    sections = _split_text(chunk.text)

    if not sections and chunk.text.strip():
        # No recognisable headers: keep the chunk as one fallback block.
        sections = [ContextSection(text=chunk.text.strip())]

    return _attach_metadata(sections, chunk.section_metadata)


def build_context_sections(chunks: list[RetrievedChunk]) -> list[ContextSection]:
    """Flatten retrieved chunks into ordered, de-duplicated sections.

    The same section can appear in two overlapping chunks; merging by
    ``section_id`` keeps it as one numbered block and avoids duplicate
    citation boxes. Sections without an id stay in retrieval order.
    """
    merged: dict[str, ContextSection] = {}
    order: list[str] = []
    anonymous: list[ContextSection] = []

    for chunk in chunks:
        for section in _chunk_sections(chunk):
            if section.section_id:
                existing = merged.get(section.section_id)
                if existing is None:
                    merged[section.section_id] = section
                    order.append(section.section_id)
                elif section.text and section.text not in existing.text:
                    merged[section.section_id] = replace(
                        existing,
                        text=f"{existing.text} {section.text}".strip(),
                    )
            else:
                anonymous.append(section)

    return [merged[section_id] for section_id in order] + anonymous


async def answer_question(
    body: ChatRequest,
    llm: LLMService,
    kas: KASClient,
    top_k: int | None = None,
) -> ChatResponse:
    """Generate a grounded answer (with citations) for a question."""
    chunks = await kas.search(body.meeting_id, body.question, top_k=top_k)

    if not chunks:
        return ChatResponse(answer=NOT_FOUND_MESSAGE, citations=[])

    sections = build_context_sections(chunks)
    if not sections:
        return ChatResponse(answer=NOT_FOUND_MESSAGE, citations=[])

    user_prompt = qa_prompts.build_user_prompt(
        body.question, [section.prompt_block() for section in sections]
    )
    answer = await llm.generate(qa_prompts.SYSTEM_PROMPT, user_prompt)

    return ChatResponse(
        answer=answer,
        citations=build_citations(answer, sections),
    )


def build_citations(
    answer: str, sections: list[ContextSection]
) -> list[Citation]:
    """Map ``[n]`` markers the model left in the answer to context sections.

    Any index the model references out of range is ignored; the citations
    only ever point at sections that were actually shown to the model.
    """
    referenced = {
        int(index)
        for index in re.findall(r"\[(\d+)\]", answer)
        if 1 <= int(index) <= len(sections)
    }

    citations = []
    for index in sorted(referenced):
        section = sections[index - 1]
        citations.append(
            Citation(
                index=index,
                text=section.text,
                speaker=section.speaker,
                timestamp=section.timestamp,
                section_id=section.section_id,
            )
        )
    return citations
