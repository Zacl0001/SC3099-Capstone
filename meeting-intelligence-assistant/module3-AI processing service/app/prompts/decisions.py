"""Prompt templates for decision extraction.

Evaluators care a lot about the distinction between a DECISION and
a suggestion / opinion / discussion / action item, so the prompt is
explicit about those boundaries.
"""

_TRANSCRIPT_BLOCK = """
TRANSCRIPT:
{transcript}
"""

SYSTEM_PROMPT = (
    "You are a meeting analysis assistant. Your job is to extract DECISIONS "
    "from meeting transcripts. A decision is a conclusion the group reached "
    "and settled on, often with explicit agreement (\"we will\", \"let's go "
    "with\", \"agreed\"). You do not invent decisions from context."
)

USER_PROMPT_TEMPLATE = """Extract every decision from the meeting transcript below.

A DECISION is a conclusion the meeting settled on. It is DIFFERENT from:
- Suggestion: a proposal that was NOT agreed upon -> exclude.
- Opinion: a person's preference, no group agreement -> exclude.
- Discussion: exploration of an idea, no conclusion -> exclude.
- Action item: a task for someone; report the underlying decision, not the task.

A decision often follows agreement phrases such as "we decided", "agreed",
"let's go with", "we will", "final answer is". If multiple people express
support, it is likely a decision.

Return ONLY a single JSON object with EXACTLY this shape:
{{
  "decisions": [
    {{
      "decision": "what was decided, as a clear statement",
      "evidence": "short verbatim quote from the transcript supporting this",
      "timestamp": "meeting timestamp if present in the transcript, else null"
    }}
  ]
}}

Rules:
- Only include real decisions. When in doubt, exclude.
- "evidence" must be a real quote from the transcript.
- If there are no decisions, return {{"decisions": []}}.
- No text outside the JSON object.

""" + _TRANSCRIPT_BLOCK


def build_user_prompt(transcript: str) -> str:
    """Render the user prompt with the transcript inserted."""
    return USER_PROMPT_TEMPLATE.format(transcript=transcript)