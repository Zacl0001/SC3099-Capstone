"""Retrieval-augmented question answering.

Pipeline:
    question -> KAS /search (top-K chunks) -> grounded prompt -> LLM -> answer + citations

The KAS chunk is the retrieval step; the LLM here only turns those chunks into
an answer. If retrieval finds nothing, we skip the LLM entirely.
"""

import re

from app.prompts import qa as qa_prompts
from app.schemas.chat import ChatRequest, ChatResponse, Citation
from app.schemas.search import RetrievedChunk
from app.services.kas_client import KASClient
from app.services.llm_service import LLMService

NOT_FOUND_MESSAGE = "I could not find this information in the meeting transcript."


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

    user_prompt = qa_prompts.build_user_prompt(
        body.question, [chunk.text for chunk in chunks]
    )
    answer = await llm.generate(qa_prompts.SYSTEM_PROMPT, user_prompt)

    return ChatResponse(
        answer=answer,
        citations=build_citations(answer, chunks),
    )


def build_citations(answer: str, chunks: list[RetrievedChunk]) -> list[Citation]:
    """Map [n] markers the model left in the answer to retrieved chunks.

    Any index the model references out of range is ignored; the citations
    only ever point at chunks the retriever actually returned.
    """
    referenced = {
        int(index)
        for index in re.findall(r"\[(\d+)\]", answer)
        if 1 <= int(index) <= len(chunks)
    }

    citations = []
    for index in sorted(referenced):
        chunk = chunks[index - 1]
        source = chunk.section_metadata[0] if chunk.section_metadata else None
        citations.append(
            Citation(
                index=index,
                text=chunk.text,
                speaker=source.speaker if source else None,
                timestamp=source.timestamp if source else None,
                section_id=source.section_id if source else None,
            )
        )
    return citations