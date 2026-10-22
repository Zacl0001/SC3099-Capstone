"""Prompt templates for grounded question answering (/chat).

The anti-hallucination contract: the model may ONLY use the context blocks
it is given, must say "not found" otherwise, and must tag facts with the
block number [n] so answers can be turned into citations.
"""

SYSTEM_PROMPT = (
    "You are a meeting knowledge assistant. Answer the user's question using "
    "ONLY the provided meeting transcript excerpts. Do not invent facts. "
    "Every factual sentence you write must end with an inline reference like "
    "[1] or [2] pointing to the context block it came from. The context almost "
    "always contains the answer; only report it could not be found if you have "
    "carefully checked every block and the information is truly absent."
)

USER_PROMPT_TEMPLATE = """Answer the question based ONLY on the context below.

{context}

QUESTION:
{question}

Rules:
- The context blocks are labelled [1], [2], ... and are your only source.
- Quote or paraphrase what the speakers actually said, and end every factual
  sentence with the number of the block that supports it, like this:
  "The deployment was postponed to Friday [1]."
- Use the block numbers that actually support each sentence (they can differ
  within one answer).
- Only if you have carefully read every block and the answer is truly not
  there, reply with exactly:
  "I could not find this information in the meeting transcript."
- Do not mention context blocks you did not use.

"""


def build_user_prompt(question: str, context_blocks: list[str]) -> str:
    """Render the user prompt with numbered context blocks."""
    context = "\n\n".join(
        f"[{i}] {block}" for i, block in enumerate(context_blocks, 1)
    )
    return USER_PROMPT_TEMPLATE.format(context=context, question=question)