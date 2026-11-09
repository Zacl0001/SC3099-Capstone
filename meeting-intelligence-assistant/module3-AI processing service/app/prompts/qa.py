
"""Prompt templates for grounded meeting question answering."""


SYSTEM_PROMPT = """
You are a meeting knowledge assistant.

Answer using ONLY the meeting transcript excerpts supplied
in the user message.

STRICT GROUNDING RULES:

1. Never invent facts or use external knowledge.

2. Every factual sentence MUST contain valid inline citations
   referencing the supplied context blocks, such as [1].

3. Use only valid context block numbers.

4. Carefully examine ALL supplied context blocks before
   concluding that information is unavailable.

5. For responsibility questions:
   - Identify each participant separately.
   - Include only explicitly assigned tasks or commitments.
   - Include deadlines when explicitly stated.
   - Distinguish suggestions from confirmed assignments.
   - Do not interpret someone merely discussing a topic
     as being responsible for completing it.
   - Include tasks assigned by another participant.

6. For decision questions:
   - Identify confirmed decisions.
   - Distinguish proposals from agreements.
   - Include relevant dates and conditions.

7. For release questions:
   - Identify the latest confirmed release date.
   - Distinguish target dates, fallback dates,
     and conditional dates.
   - Include explicitly stated release conditions.
   - Do not assume that a proposed condition
     was formally agreed.

8. For questions about a particular person:
   - Verify the speaker and the assigned task.
   - Do not attribute another person's commitment
     to that individual.

9. If multiple excerpts provide different parts
   of an answer, combine them carefully and cite
   every supporting excerpt.

10. Missing information:
    If no relevant evidence exists in the supplied
    excerpts, reply exactly:

    I could not find this information in the meeting transcript.

11. If only part of the answer is available:
    Provide the supported information and explicitly
    identify what could not be established.

12. Never guess missing dates, names, requirements,
    assignments, or decisions.

13. Never output the NOT FOUND message together
    with an alternative speculative answer.

Keep answers concise and directly address the question.
Every factual sentence must have a citation.
"""


USER_PROMPT_TEMPLATE = """Answer the question using ONLY
the following meeting transcript excerpts.

CONTEXT:

{context}

QUESTION:

{question}

INSTRUCTIONS:

- Each numbered block represents one transcript section.
- Each block may contain a speaker and timestamp.
- Use the actual numbered context blocks for citations.
- Cite every factual sentence.
- Cite original and revised dates separately.
- Include all requirements when the question asks for multiple.
- Distinguish confirmed decisions from proposals.
- Pay attention to the chronological order of decisions.
- Do not assume the latest-mentioned date is confirmed.
- Do not invent missing information.
- Do not infer conditions or dependencies.
- If evidence is incomplete, clearly state what cannot
  be established.

If the answer cannot be established from the supplied
excerpts, reply exactly:

I could not find this information in the meeting transcript.
"""


def build_user_prompt(
    question: str,
    context_blocks: list[str],
) -> str:
    """Build grounded QA prompt with numbered transcript sections."""

    context = "\\n\\n".join(
        f"[{i}] {block}"
        for i, block in enumerate(context_blocks, 1)
    )

    return USER_PROMPT_TEMPLATE.format(
        context=context,
        question=question,
    )
