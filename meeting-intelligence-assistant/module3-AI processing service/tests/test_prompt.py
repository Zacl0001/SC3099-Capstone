"""Prompt-content tests.

These are cheap but important: they pin the behaviors evaluators care
about (evidence-only, no invented assignee, decision vs suggestion) so a
future edit to a prompt cannot silently remove them.
"""

import pytest

from app.prompts import action_items, decisions, summary, topics

TRANSCRIPT = "Alice: let's do X."


def test_summary_prompt_embeds_transcript():
    prompt = summary.build_user_prompt(TRANSCRIPT)
    assert TRANSCRIPT in prompt
    assert '"summary"' in prompt
    assert '"key_points"' in prompt


def test_summary_prompt_forbids_inventing_information():
    assert "never invent" in summary.SYSTEM_PROMPT.lower()


def test_action_prompt_embeds_transcript_and_schema():
    prompt = action_items.build_user_prompt(TRANSCRIPT)
    assert TRANSCRIPT in prompt
    for field in ("task", "assignee", "deadline", "evidence", "timestamp"):
        assert field in prompt


def test_action_prompt_does_not_infer_assignee():
    prompt = action_items.build_user_prompt(TRANSCRIPT)
    assert "Never guess or infer an assignee" in prompt
    assert "assignee\" MUST be null" in prompt
    assert "Do NOT include" in prompt


def test_action_prompt_empty_items_fallback():
    assert '{"action_items": []}' in action_items.USER_PROMPT_TEMPLATE


def test_decision_prompt_distinguishes_decision_from_suggestion():
    prompt = decisions.build_user_prompt(TRANSCRIPT)
    assert "Suggestion" in prompt
    assert "Opinion" in prompt
    assert "Discussion" in prompt
    assert "Action item" in prompt


def test_decision_prompt_agreement_phrases():
    assert "we decided" in decisions.USER_PROMPT_TEMPLATE.lower()


def test_topic_prompt_has_importance_enum():
    prompt = topics.build_user_prompt(TRANSCRIPT)
    assert TRANSCRIPT in prompt
    assert '"importance"' in prompt
    assert "HIGH" in prompt and "MEDIUM" in prompt and "LOW" in prompt