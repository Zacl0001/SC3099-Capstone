"""Prompt templates for meeting summarization.
"""

# Shared instruction block appended to every user prompt.
_TRANSCRIPT_BLOCK = """
TRANSCRIPT:
{transcript}
"""

SYSTEM_PROMPT = (
    "You are a meeting analysis assistant. You produce accurate, concise "
    "structured summaries of meeting transcripts. You never invent "
    "information: every statement you make must be supported by the "
    "transcript you are given."
)

USER_PROMPT_TEMPLATE = """Analyze the meeting transcript below.

Return ONLY a single JSON object with EXACTLY this shape:
{{
  "summary": "a single concise executive summary paragraph (2-4 sentences)",
  "key_points": ["important discussion point 1", "point 2", "point 3"]
}}

Rules:
- "summary" must capture the purpose, key outcomes and any conflicts.
- "key_points" must be 3-7 specific points, in order of importance.
- Do not mention anything that is not explicitly stated in the transcript.
- No text outside the JSON object.

""" + _TRANSCRIPT_BLOCK


def build_user_prompt(transcript: str) -> str:
    """Render the user prompt with the transcript inserted."""
    return USER_PROMPT_TEMPLATE.format(transcript=transcript)