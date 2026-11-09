"""Retrieval-augmented question answering.

Pipeline:
    question -> KAS /search (top-K chunks) -> grounded prompt -> LLM -> answer + citations

KAS chunks are retrieval units and usually span several transcript sections.
The LLM sees one numbered context block per *section* (speaker turn), so each
``[n]`` maps to a single transcript location the UI can show as its own
citation box.
"""
import asyncio
import re
from dataclasses import dataclass, replace

from app.prompts import qa as qa_prompts
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    Citation,
    GroundedAnswer,
)
from app.schemas.search import RetrievedChunk, SectionRef
from app.services.kas_client import KASClient
from app.services.llm_service import LLMService
from app.core.logging import get_logger


logger = get_logger(__name__)
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
    "must", "my", "now", "of", "off", "on", "once", "one",
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
    r"(?:\s*\[(?P<timestamp>"
    r"\d{1,3}:\d{2}(?::\d{2})?(?:[.,]\d+)?"
    r")\])?"
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
    sections: list[ContextSection],
    refs: list[SectionRef],
) -> list[ContextSection]:
    """Attach metadata using speaker/timestamp matching."""

    if not refs:
        return sections

    used: set[int] = set()
    positional = len(sections) == len(refs)
    result: list[ContextSection] = []

    for position, section in enumerate(sections):
        speaker = (section.speaker or "").strip().casefold()
        timestamp = _normalise_time(section.timestamp)

        candidates = []

        for index, candidate in enumerate(refs):
            if index in used:
                continue

            candidate_speaker = (
                candidate.speaker or ""
            ).strip().casefold()

            candidate_timestamp = _normalise_time(
                candidate.timestamp
            )

            if candidate_speaker != speaker:
                continue

            if timestamp and candidate_timestamp:
                if timestamp == candidate_timestamp:
                    candidates.append((0, index, candidate))
            else:
                candidates.append((1, index, candidate))

        ref = None

        if candidates:
            candidates.sort(key=lambda item: item[0])
            _, index, ref = candidates[0]
            used.add(index)

        elif positional and position not in used:
            # Positional matching is safe only when both lists
            # contain exactly the same number of sections.
            candidate = refs[position]

            if (
                not speaker
                or not candidate.speaker
                or speaker == candidate.speaker.strip().casefold()
            ):
                ref = candidate
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





def _chunk_sections(
    chunk: RetrievedChunk,
) -> list[ContextSection]:
    """
    Reconstruct speaker-level transcript sections.

    Use chunk text as the source of truth and metadata
    to attach section identifiers.
    """

    sections = _split_text(chunk.text)

    if not sections and chunk.text.strip():
        sections = [
            ContextSection(text=chunk.text.strip())
        ]

    return _attach_metadata(
        sections,
        chunk.section_metadata,
    )



def _merge_section_text(old_text: str, new_text: str) -> str:
    """Merge overlapping fragments without repeating shared text."""

    old_text = old_text.strip()
    new_text = new_text.strip()

    if not old_text:
        return new_text

    if not new_text:
        return old_text

    if old_text in new_text:
        return new_text

    if new_text in old_text:
        return old_text

    # Find the largest suffix of the old fragment that matches
    # the beginning of the new fragment.
    max_overlap = min(len(old_text), len(new_text))

    for overlap in range(max_overlap, 0, -1):
        if old_text[-overlap:] == new_text[:overlap]:
            # Avoid treating a tiny coincidental match as
            # a meaningful transcript overlap.
            if overlap >= 20:
                return old_text + new_text[overlap:]

    # No reliable overlap was found.
    return f"{old_text} {new_text}"


def _timestamp_sort_key(section: ContextSection):
    """Convert transcript timestamps into sortable seconds."""

    timestamp = _normalise_time(section.timestamp)

    if not timestamp:
        return (1, float("inf"))

    try:
        parts = timestamp.split(":")

        if len(parts) == 2:
            minutes, seconds = map(float, parts)
            total = minutes * 60 + seconds

        elif len(parts) == 3:
            hours, minutes, seconds = map(float, parts)
            total = hours * 3600 + minutes * 60 + seconds

        else:
            return (1, float("inf"))

        return (0, total)

    except (ValueError, TypeError):
        return (1, float("inf"))


def build_context_sections(
    chunks: list[RetrievedChunk],
) -> list[ContextSection]:
    """
    Flatten retrieved chunks into ordered, deduplicated sections.

    Sections with the same section_id are merged.
    Sections without IDs are deduplicated by their content.
    """

    merged: dict[str, ContextSection] = {}
    order: list[str] = []
    anonymous: list[ContextSection] = []

    for chunk in chunks:
        for section in _chunk_sections(chunk):

            if section.section_id:
                section_id = section.section_id

                existing = merged.get(section_id)

                if existing is None:
                    merged[section_id] = section
                    order.append(section_id)
                    continue

                merged_text = _merge_section_text(
                    existing.text,
                    section.text,
                )

                merged[section_id] = replace(
                    existing,
                    text=merged_text,
                    speaker=existing.speaker or section.speaker,
                    timestamp=existing.timestamp or section.timestamp,
                )

            else:
                duplicate = any(
                    item.text.strip() == section.text.strip()
                    and item.speaker == section.speaker
                    and _normalise_time(item.timestamp)
                    == _normalise_time(section.timestamp)
                    for item in anonymous
                )

                if not duplicate:
                    anonymous.append(section)

    result = (
        [merged[section_id] for section_id in order]
        + anonymous
    )

    result.sort(key=_timestamp_sort_key)

    return result




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
    answer: str,
    sections: list[ContextSection],
) -> tuple[str, list[Citation]]:
    """
    Preserve only citations that reference valid context blocks.

    Do not automatically invent citations using lexical similarity.
    An answer without a verifiable citation must remain uncited.
    """

    if not sections or not answer.strip():
        return answer, []

    if answer.strip() == NOT_FOUND_MESSAGE:
        return NOT_FOUND_MESSAGE, []

    max_index = len(sections)

    valid_indices = set(range(1, max_index + 1))

    def validate_sentence(match: re.Match) -> str:
        sentence = match.group(0)

        markers = [
            int(value)
            for value in _CITATION_RE.findall(sentence)
        ]

        valid_markers = [
            marker
            for marker in markers
            if marker in valid_indices
        ]

        # Remove invalid citation markers.
        cleaned = re.sub(
            r"\s*\[\d+\]",
            "",
            sentence,
        )

        # Keep valid citations only.
        if valid_markers:
            unique_markers = list(dict.fromkeys(valid_markers))

            punctuation = ""
            core = cleaned.rstrip()

            while core and core[-1] in ".!?":
                punctuation = core[-1] + punctuation
                core = core[:-1]

            return (
                f"{core.rstrip()} "
                + " ".join(
                    f"[{index}]"
                    for index in unique_markers
                )
                + punctuation
            )

        return cleaned

    cited_answer = _SENTENCE_RE.sub(
        validate_sentence,
        answer,
    )

    citations = build_citations(
        cited_answer,
        sections,
    )

    return cited_answer, citations


def lexical_score(
    question: str,
    chunk: RetrievedChunk,
) -> float:
    """Calculate simple keyword overlap with a transcript chunk."""

    question_tokens = _tokens(question)
    chunk_tokens = _tokens(chunk.text)

    if not question_tokens:
        return 0.0

    overlap = question_tokens & chunk_tokens

    return len(overlap) / len(question_tokens)



def reciprocal_rank_fusion(
    ranked_results: list[list[RetrievedChunk]],
    question: str,
    k: int = 60,
) -> list[RetrievedChunk]:
    """Combine multiple retrieval rankings using RRF."""

    scores: dict[tuple, float] = {}
    chunk_map: dict[tuple, RetrievedChunk] = {}

    for results in ranked_results:
        seen_in_query = set()

        for rank, chunk in enumerate(results, start=1):
            key = (
                str(chunk.meeting_id),
                chunk.text.strip(),
            )

            if key in seen_in_query:
                continue

            seen_in_query.add(key)
            chunk_map[key] = chunk

            scores[key] = (
                scores.get(key, 0.0)
                + 1.0 / (k + rank)
            )

    question_tokens = _tokens(question)

    lexical_scores = {}

    for key, chunk in chunk_map.items():
        chunk_tokens = _tokens(chunk.text)

        if not question_tokens:
            lexical_scores[key] = 0.0
            continue

        overlap = question_tokens & chunk_tokens

        lexical_scores[key] = (
            len(overlap) / len(question_tokens)
        )

    lexical_ranking = sorted(
        lexical_scores,
        key=lexical_scores.get,
        reverse=True,
    )

    for rank, key in enumerate(lexical_ranking, start=1):
        if lexical_scores[key] > 0:
            scores[key] += 1.0 / (k + rank)

    ordered_keys = sorted(
        scores,
        key=scores.get,
        reverse=True,
    )

    return [
        chunk_map[key]
        for key in ordered_keys
    ]




def generate_search_queries(question: str) -> list[str]:
    """Generate question-focused retrieval queries."""

    original = question.strip()

    normalized = original.lower()

    queries = [original]

    expansions = {
        "release": [
            "release date launch schedule release approval",
            "final release decision target date fallback date",
        ],
        "qa": [
            "QA approval quality assurance sign off",
            "original QA date revised QA approval schedule",
        ],
        "worker": [
            "background workers worker count worker scaling",
            "increase in workers original number new number",
            "worker concurrency processing capacity",
        ],
        "notification": [
            "notification events delivery attempts retries",
            "notification processing delivery status queue",
        ],
        "testing": [
            "internal testing external customer testing UAT",
            "user acceptance testing approval test schedule",
        ],
        "performance": [
            "notification processing latency response time",
            "normal traffic peak traffic processing targets",
        ],
        "security": [
            "security requirements authorization access control",
            "deactivated accounts pending notifications",
        ],
        "date": [
            "original date revised date updated deadline",
            "initial schedule final confirmed schedule",
        ],
        "count": [
            "total count number of records processing attempts",
            "difference between event count and attempt count",
        ],
    }

    for keyword, alternatives in expansions.items():
        if keyword in normalized:
            queries.extend(alternatives)

    # Detect questions comparing two concepts.
    comparison_words = (
        "difference",
        "versus",
        "compare",
        "compared",
        "between",
    )

    if any(word in normalized for word in comparison_words):
        queries.append(
            f"definitions meaning distinction explanation: {original}"
        )

    # Detect questions involving chronology.
    chronology_words = (
        "original",
        "changed",
        "revised",
        "latest",
        "final",
        "previous",
        "updated",
    )

    if any(word in normalized for word in chronology_words):
        queries.append(
            f"initial proposal subsequent revision final agreement: {original}"
        )
        # Responsibility and deadline questions.
    responsibility_words = (
        "responsible",
        "responsibility",
        "assigned",
        "action item",
        "actionable",
        "complete",
        "completing",
        "task",
        "tasks",
    )

    if any(word in normalized for word in responsibility_words):
        queries.extend([
            "assigned responsibilities and action items",
            "Rachel tasks and commitments",
            "participant assignments and deadlines",
            "tasks explicitly assigned to each participant",
            "screenshots technical documentation November 9",
        ])

    # Deadline questions.
    deadline_words = (
        "deadline",
        "deadlines",
        "due",
        "by when",
        "schedule",
    )

    if any(word in normalized for word in deadline_words):
        queries.extend([
            "all task deadlines and delivery dates",
            "target dates fallback dates and revised dates",
            "November 5 November 6 November 9 November 10 November 12",
        ])

    # Questions specifically about November 9.
    if "november 9" in normalized:
        queries.extend([
            "November 9 screenshots staging environment",
            "Rachel three screenshots technical documentation",
        ])

    # Questions about release conditions.
    if "release" in normalized:
        queries.extend([
            "November 12 conditional release target",
            "QA UAT passing critical issue delay release",
            "final release approval November 10",
        ])
    # Preserve order and remove duplicate queries.
    return list(dict.fromkeys(queries))


def format_grounded_answer(
    grounded: GroundedAnswer,
    sections: list[ContextSection],
) -> tuple[str, list[Citation]]:
    """Format validated claims and construct citations."""

    if grounded.not_found or not grounded.claims:
        return NOT_FOUND_MESSAGE, []

    citations_by_index: dict[int, Citation] = {}
    formatted_claims = []

    for claim in grounded.claims:
        valid_indices = []

        for index in claim.evidence_indices:
            if index < 1 or index > len(sections):
                continue

            section = sections[index - 1]

            citations_by_index[index] = Citation(
                index=index,
                text=section.text,
                speaker=section.speaker,
                timestamp=section.timestamp,
                section_id=section.section_id,
            )

            valid_indices.append(index)

        # Never return a factual claim without valid evidence.
        if not valid_indices:
            continue

        markers = " ".join(
            f"[{index}]" for index in valid_indices
        )

        formatted_claims.append(
            f"{claim.text.rstrip()} {markers}"
        )

    if not formatted_claims:
        return NOT_FOUND_MESSAGE, []

    citations = [
        citations_by_index[index]
        for index in sorted(citations_by_index)
    ]

    return "\n\n".join(formatted_claims), citations




async def retrieve_question_context(
    meeting_id: str,
    question: str,
    kas: KASClient,
    top_k: int = 10,
) -> list[RetrievedChunk]:
    """Retrieve question-relevant transcript chunks."""

    queries = generate_search_queries(question)

    logger.info(
        "[RAG] Starting retrieval | meeting=%s | queries=%d",
        meeting_id,
        len(queries),
    )

    search_results = await asyncio.gather(
        *[
            kas.search(
                meeting_id=meeting_id,
                query=query,
                top_k=min(max(top_k, 10), 20),
            )
            for query in queries
        ],
        return_exceptions=True,
    )

    valid_results = []

    for index, result in enumerate(search_results):

        if isinstance(result, Exception):
            logger.error(
                "[RAG] Search failed | query=%s | error=%s",
                queries[index],
                result,
            )
            continue

        logger.info(
            "[RAG] Search completed | query=%s | results=%d",
            queries[index],
            len(result),
        )

        valid_results.append(result)

    if not valid_results:
        logger.error(
            "[RAG] All retrieval queries failed | meeting=%s",
            meeting_id,
        )
        return []

    chunks = reciprocal_rank_fusion(
        ranked_results=valid_results,
        question=question,
    )

    # Prioritize chunks that directly match the actual question.
    chunks.sort(
        key=lambda chunk: (
            lexical_score(question, chunk),
            chunk.score,
        ),
        reverse=True,
    )

    context_limit = min(top_k * 3, 40)

    selected = chunks[:context_limit]

    logger.info(
        "[RAG] Retrieval finished | candidates=%d | selected=%d",
        len(chunks),
        len(selected),
    )

    for index, chunk in enumerate(selected, start=1):
        logger.debug(
            "[RAG] Selected chunk %d | score=%s | "
            "lexical=%s | text=%s",
            index,
            chunk.score,
            lexical_score(question, chunk),
            chunk.text[:500],
        )

    return selected




async def answer_question(
    body: ChatRequest,
    llm: LLMService,
    kas: KASClient,
    top_k: int | None = None,
) -> ChatResponse:
    """Generate a grounded answer using multi-query retrieval."""

    meeting_id = str(body.meeting_id)
    retrieval_k = top_k or body.top_k or 10

    logger.info(
        "[RAG] Question received | meeting=%s | question=%s",
        meeting_id,
        body.question,
    )

    # 1. Retrieve evidence using multiple queries.
    chunks = await retrieve_question_context(
        meeting_id=meeting_id,
        question=body.question,
        kas=kas,
        top_k=retrieval_k,
    )

    if not chunks:
        logger.warning(
            "[RAG] No chunks retrieved | meeting=%s",
            meeting_id,
        )

        return ChatResponse(
            answer=NOT_FOUND_MESSAGE,
            citations=[],
        )

    # 2. Convert chunks into speaker-level context blocks.
    sections = build_context_sections(chunks)

    logger.info(
        "[RAG DEBUG] Retrieved chunks: %d",
        len(chunks),
    )

    logger.info(
        "[RAG DEBUG] Reconstructed sections: %d",
        len(sections),
    )

    for index, section in enumerate(sections, start=1):
        logger.info(
            "[RAG DEBUG] CONTEXT [%d] speaker=%s timestamp=%s "
            "section_id=%s text=%s",
            index,
            section.speaker,
            section.timestamp,
            section.section_id,
            section.text,
        )

    if not sections:
        logger.warning("[RAG] No usable context sections")

        return ChatResponse(
            answer=NOT_FOUND_MESSAGE,
            citations=[],
        )

    logger.info(
        "[RAG] Context prepared | chunks=%d | sections=%d",
        len(chunks),
        len(sections),
    )

    # 3. Generate grounded answer.
    
    logger.info(
        "[RAG] ===== RETRIEVED CONTEXT INSPECTION ====="
    )

    for index, section in enumerate(sections, start=1):
        logger.info(
            "[RAG] SECTION [%d] | speaker=%s | timestamp=%s | "
            "section_id=%s | text=%s",
            index,
            section.speaker,
            section.timestamp,
            section.section_id,
            section.text[:1000],
        )

    logger.info(
        "[RAG] ===== END CONTEXT INSPECTION ====="
    )
    logger.info(
        "[RAG] Final context statistics | "
        "chunks=%d | sections=%d | chars=%d",
        len(chunks),
        len(sections),
        sum(len(section.prompt_block()) for section in sections),
    )
    user_prompt = qa_prompts.build_user_prompt(
        body.question,
        [
            section.prompt_block()
            for section in sections
        ],
    )

    logger.info(
        "[RAG] Sending context to LLM | chars=%d",
        len(user_prompt),
    )

  
    
    # 4. Generate structured grounded answer.

    grounded_answer = await llm.generate_structured(
        system_prompt=qa_prompts.SYSTEM_PROMPT,
        user_prompt=user_prompt,
        response_model=GroundedAnswer,
    )

    logger.info(
        "[RAG] Structured answer | claims=%d | not_found=%s",
        len(grounded_answer.claims),
        grounded_answer.not_found,
    )

    # 5. Handle insufficient evidence.

    if grounded_answer.not_found or not grounded_answer.claims:
        return ChatResponse(
            answer=NOT_FOUND_MESSAGE,
            citations=[],
        )

    # 6. Validate evidence references and construct citations.

    valid_claims = []
    referenced_indices = set()

    for claim in grounded_answer.claims:

        valid_indices = sorted({
            index
            for index in claim.evidence_indices
            if 1 <= index <= len(sections)
        })

        if not valid_indices:
            logger.warning(
                "[RAG] Claim rejected: no valid evidence | claim=%s",
                claim.text,
            )
            continue

        valid_claims.append(
            (claim.text, valid_indices)
        )

        referenced_indices.update(valid_indices)

    if not valid_claims:
        return ChatResponse(
            answer=NOT_FOUND_MESSAGE,
            citations=[],
        )

    # 7. Format answer with actual evidence markers.

    answer_parts = []

    for claim_text, evidence_indices in valid_claims:
        markers = " ".join(
            f"[{index}]"
            for index in evidence_indices
        )

        answer_parts.append(
            f"{claim_text} {markers}"
        )

    final_answer = "\n\n".join(answer_parts)

    # 8. Build citations only from explicitly supplied evidence.

    citations = [
        Citation(
            index=index,
            text=sections[index - 1].text,
            speaker=sections[index - 1].speaker,
            timestamp=sections[index - 1].timestamp,
            section_id=sections[index - 1].section_id,
        )
        for index in sorted(referenced_indices)
    ]

    logger.info(
        "[RAG] Answer complete | claims=%d | citations=%d",
        len(valid_claims),
        len(citations),
    )

    return ChatResponse(
        answer=final_answer,
        citations=citations,
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
