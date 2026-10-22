"""Prompt templates for topic identification."""

_TRANSCRIPT_BLOCK = """
TRANSCRIPT:
{transcript}
"""

SYSTEM_PROMPT = (
    "You are a meeting analysis assistant. Your job is to identify the major "
    "topics covered in a meeting transcript and rank their importance."
)

USER_PROMPT_TEMPLATE = """Identify the major topics covered in the meeting transcript below.

Return ONLY a single JSON object with EXACTLY this shape:
{{
  "topics": [
    {{
      "name": "short topic label (2-5 words)",
      "description": "1-2 sentence summary of what was discussed under this topic",
      "importance": "HIGH, MEDIUM or LOW"
    }}
  ]
}}

Rules:
- Cover all significant topics; avoid trivial off-topic remarks.
- Rank importance by how much meeting time / energy the topic received,
  and how consequential it is.
- Importance must be exactly one of HIGH, MEDIUM, LOW.
- If the meeting has only one topic, return exactly one entry.
- No text outside the JSON object.

""" + _TRANSCRIPT_BLOCK


def build_user_prompt(transcript: str) -> str:
    """Render the user prompt with the transcript inserted."""
    return USER_PROMPT_TEMPLATE.format(transcript=transcript)