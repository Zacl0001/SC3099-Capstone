"""Prompt templates for action item extraction."""

_TRANSCRIPT_BLOCK = """
TRANSCRIPT:
{transcript}
"""

SYSTEM_PROMPT = (
    "You are a meeting analysis assistant. Your job is to extract ACTION "
    "ITEMS from meeting transcripts. An action item is a concrete task that "
    "someone agreed to do after the meeting. You do not invent people, tasks "
    "or deadlines that are not explicitly stated in the transcript."
)

USER_PROMPT_TEMPLATE = """Extract every action item from the meeting transcript below.

An action item is only an action item if someone agrees to (or is assigned)
a specific task. Do NOT include:
- general discussions,
- opinions,
- decisions,
- tasks that are only mentioned but never assigned.

Return ONLY a single JSON object with EXACTLY this shape:
{{
  "action_items": [
    {{
      "task": "the concrete task",
      "assignee": "person responsible, or null if not stated",
      "deadline": "due date if stated, or null",
      "evidence": "short verbatim quote from the transcript that supports this item",
      "timestamp": "meeting timestamp if present in the transcript, else null"
    }}
  ]
}}

Rules:
- "assignee" MUST be null if the transcript does not give a specific person.
  Never guess or infer an assignee.
- "deadline" MUST be null if no deadline is mentioned.
- "evidence" must be a real quote from the transcript.
- If there are no action items, return {{"action_items": []}}.
- No text outside the JSON object.

""" + _TRANSCRIPT_BLOCK


def build_user_prompt(transcript: str) -> str:
    """Render the user prompt with the transcript inserted."""
    return USER_PROMPT_TEMPLATE.format(transcript=transcript)