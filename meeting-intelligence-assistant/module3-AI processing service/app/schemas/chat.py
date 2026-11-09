"""Schemas for the RAG question-answering endpoint (/chat)."""

from pydantic import BaseModel, Field, model_validator


class GroundedClaim(BaseModel):
    """One factual claim and its supporting transcript sections."""

    text: str = Field(
        ...,
        min_length=1,
        description="One factual claim supported by the transcript.",
    )

    evidence_indices: list[int] = Field(
        ...,
        min_length=1,
        description=(
            "Positive context block numbers that directly support "
            "the claim."
        ),
    )

    @model_validator(mode="after")
    def validate_evidence_indices(self):
        if any(index < 1 for index in self.evidence_indices):
            raise ValueError(
                "Evidence indices must be positive integers."
            )

        if len(self.evidence_indices) != len(
            set(self.evidence_indices)
        ):
            raise ValueError(
                "Evidence indices must not contain duplicates."
            )

        if not self.text.strip():
            raise ValueError("Claim text cannot be empty.")

        return self



class GroundedAnswer(BaseModel):
    """Structured answer containing claims and supporting evidence."""

    claims: list[GroundedClaim] = Field(
        default_factory=list,
        description="Factual claims supported by transcript evidence.",
    )

    not_found: bool = Field(
        default=False,
        description=(
            "True only when no relevant answer can be established "
            "from the supplied transcript sections."
        ),
    )

    @model_validator(mode="after")
    def validate_answer(self):
        if self.not_found and self.claims:
            raise ValueError(
                "A not-found answer cannot contain factual claims."
            )

        if not self.not_found and not self.claims:
            raise ValueError(
                "An answer must contain claims or be marked not_found."
            )

        return self



class ChatRequest(BaseModel):
    """Input for the Q&A endpoint."""

    meeting_id: str = Field(..., description="Which meeting to ask about.")
    question: str = Field(..., min_length=1, description="The user's question.")
    top_k: int | None = Field(
        default=None, ge=1, le=20, description="How many transcript chunks to retrieve."
    )


class Citation(BaseModel):
    """A source a generated answer relies on.

    `index` matches the [n] reference embedded in the answer text.
    """

    index: int = Field(..., description="Citation number referenced as [n] in the answer.")
    text: str = Field(..., description="The retrieved transcript chunk text.")
    speaker: str | None = Field(None, description="Speaker of the cited section, if known.")
    timestamp: str | None = Field(None, description="Timestamp of the cited section, if known.")
    section_id: str | None = Field(None, description="Source section id, if known.")


class ChatResponse(BaseModel):
    """Generated answer plus the sources it relies on."""

    answer: str = Field(...)
    citations: list[Citation] = Field(default_factory=list)