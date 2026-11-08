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

_WORD_RE = re.compile(r"[a-z0-9]+")
_ORDINAL_RE = re.compile(r"(\d+)(?:st|nd|rd|th)$")
_SENTENCE_RE = re.compile(r"[^.!?\n]+(?:[.!?]+|$)")
_CITATION_RE = re.compile(r"\[(\d+)\]")

# Words that carry no retrieval signal. Kept deliberately small: names,
# numbers and dates are exactly what identifies the supporting speaker turn.
_STOPWORDS = {
    "a", "about", "after", "again", "all", "also", "am", "an", "and", "any",
    "are", "as", "at", "be", "because", "been", "before", "being", "between",
    "both", "but", "by", "can", "could", "did", "do", "does", "doing", "done",
    "each", "few", "for", "from", "further", "get", "go", "had", "has", "have",
    "having", "he", "her", "here", "hers", "him", "his", "how", "i", "if", "in",
    "into", "is", "it", "its", "itself", "just", "me", "might", "more", "most",
    "must", "my", "no", "nor", "not", "now", "of", "off", "on", "once", "one",
    "only", "or", "other", "our", "ours", "out", "over", "own", "same", "she",
    "should", "so", "some", "such", "than", "that", "the", "their", "theirs",
    "them", "then", "there", "these", "they", "this", "those", "through", "to",
    "too", "under", "until", "up", "very", "was", "we", "were", "what", "when",
    "where", "which", "while", "who", "whom", "why", "will", "with", "would",
    "you", "your", "yours",
}

# A sentence needs this much evidence before it is attributed to a section.
# Below it, an answer stays uncited rather than pointing at a guess.
_MIN_OVERLAP = 2
_MIN_COVERAGE = 0.34

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


def _stem(token: str) -> str:
    """Crude suffix stripping so "delayed" matches "delay"."""
    if token.isdigit() or len(token) <= 4:
        return token
    for suffix in ("ing", "ed", "es", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            return token[: -len(suffix)]
    return token


def _tokens(text: str) -> set[str]:
    """Meaningful words in a quote or transcript section."""
    tokens = set()
    for raw in _WORD_RE.findall((text or "").lower()):
        token = _stem(_ORDINAL_RE.sub(r"\1", raw))
        if token not in _STOPWORDS:
            tokens.add(token)
    return tokens


def _best_section_index(
    sentence: str, sections: list[ContextSection]
) -> int | None:
    """Return the 1-based context block that best supports one sentence.

    Tokens are weighted by rarity across the retrieved sections: "QA" and
    "sign-off" identify one turn, while "launch" appears nearly everywhere.
    Without that weighting a long summary turn wins on volume alone.
    """
    sentence_tokens = _tokens(sentence)
    if len(sentence_tokens) < _MIN_OVERLAP:
        return None

    section_tokens = [_tokens(section.prompt_block()) for section in sections]

    document_frequency: dict[str, int] = {}
    for tokens in section_tokens:
        for token in tokens:
            document_frequency[token] = document_frequency.get(token, 0) + 1

    def weight(token: str) -> float:
        return 1.0 / document_frequency.get(token, 1)

    sentence_weight = sum(weight(token) for token in sentence_tokens)
    if sentence_weight == 0:
        return None

    best_index: int | None = None
    best_score = 0.0

    for index, tokens in enumerate(section_tokens, start=1):
        if not tokens:
            continue

        overlap = sentence_tokens & tokens
        if len(overlap) < _MIN_OVERLAP:
            continue

        coverage = len(overlap) / len(sentence_tokens)
        if coverage < _MIN_COVERAGE:
            continue

        weighted_overlap = sum(weight(token) for token in overlap)
        jaccard = len(overlap) / (
            len(sentence_tokens) + len(tokens) - len(overlap)
        )
        score = (weighted_overlap / sentence_weight) + (0.05 * jaccard)
        if score > best_score:
            best_index = index
            best_score = score

    return best_index


def _add_marker(sentence: str, index: int) -> str:
    """Insert ``[index]`` before the sentence's final punctuation."""
    trailing = sentence[len(sentence.rstrip()):]
    core = sentence.rstrip()

    punctuation = ""
    while core and core[-1] in ".!?;:":
        punctuation = core[-1] + punctuation
        core = core[:-1]

    return f"{core.rstrip()} [{index}]{punctuation}{trailing}"


def ensure_citations(
    answer: str, sections: list[ContextSection]
) -> tuple[str, list[Citation]]:
    """Fill in ``[n]`` markers the model forgot, then build the citations.

    Local models follow the citation rule most of the time but occasionally
    return a correct, grounded answer with no markers at all. Rather than
    showing that answer without sources, each unmarked sentence is matched
    against the same context blocks the model saw. The thresholds are strict:
    a sentence that only shares one generic word stays uncited.
    """
    if not sections or not answer.strip() or answer.strip() == NOT_FOUND_MESSAGE:
        return answer, []

    max_index = len(sections)
    rewritten: list[str] = []
    cursor = 0

    for match in _SENTENCE_RE.finditer(answer):
        rewritten.append(answer[cursor:match.start()])
        sentence = match.group(0)
        cursor = match.end()

        body = sentence.strip()
        if not body or body == NOT_FOUND_MESSAGE:
            rewritten.append(sentence)
            continue

        markers = [int(value) for value in _CITATION_RE.findall(body)]
        valid = [marker for marker in markers if 1 <= marker <= max_index]
        cleaned = re.sub(r"\s*\[\d+\]", "", sentence)
        sentence_tokens = _tokens(cleaned)

        # Trust a model marker when the section it names shares at least one
        # meaningful word with the sentence. If none of the markers line up,
        # try to attribute the sentence from its own words - but only replace
        # them when a clear alternative exists, because a paraphrase can be
        # correct without sharing vocabulary with the transcript.
        if any(
            sentence_tokens & _tokens(sections[marker - 1].prompt_block())
            for marker in valid
        ):
            rewritten.append(sentence)
            continue

        index = _best_section_index(cleaned, sections)
        if index is None:
            rewritten.append(sentence if valid else cleaned)
        else:
            rewritten.append(_add_marker(cleaned, index))

    rewritten.append(answer[cursor:])
    cited_answer = "".join(rewritten)

    return cited_answer, build_citations(cited_answer, sections)


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
    cited_answer, citations = ensure_citations(answer, sections)

    return ChatResponse(answer=cited_answer, citations=citations)


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
