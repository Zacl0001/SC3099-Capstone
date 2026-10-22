"""Prompt templates for the map-reduce summarization path.

Used when a transcript is long enough that it must be chunked first:
map = summarize each chunk (via the normal summary prompt), reduce = merge
the per-chunk summaries into one final summary.
"""

REDUCE_SYSTEM_PROMPT = (
    "You are a meeting analysis assistant. You combine partial summaries of a "
    "long meeting transcript into one accurate, concise final summary. You never "
    "invent information: every statement must be supported by the partial "
    "summaries you are given."
)

REDUCE_USER_PROMPT_TEMPLATE = """Below are partial summaries of one long meeting transcript. Combine them into ONE final summary.

PARTIAL SUMMARIES:
{partials}

Return ONLY a single JSON object with EXACTLY this shape (example):
{{"summary": "The team reviewed the deployment plan and agreed to stage the rollout.", "key_points": ["Staged rollout agreed", "Connection pool to be shared", "Frontend search UI owned by Morgan"]}}

The object must contain both keys: "summary" (string) and "key_points" (array of strings).

Rules:
- Merge overlapping content; remove duplicates.
- Keep 3-7 key points, in order of importance.
- Do not add anything that is not present in the partial summaries.
- No text outside the JSON object, and no extra keys.

"""


def build_reduce_user_prompt(partials: list) -> str:
    """Render the reduce prompt from a list of SummaryResponse-like objects."""
    blocks = "\n\n".join(
        f"## Partial {i}\nSummary: {p.summary}\nKey points: {', '.join(p.key_points)}"
        for i, p in enumerate(partials, 1)
    )
    return REDUCE_USER_PROMPT_TEMPLATE.format(partials=blocks)