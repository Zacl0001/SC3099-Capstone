"""Tests for the LLM JSON parsing helper.

These target the robustness path that protects us against messy local
model output (code fences, preamble text, plain garbage).
"""

import pytest

from app.services.exceptions import LLMInvalidResponse
from app.services.llm_service import _parse_json_object

VALID = {"summary": "hello", "key_points": ["a", "b"]}


def test_parses_plain_json():
    assert _parse_json_object('{"summary": "hello", "key_points": ["a", "b"]}') == VALID


def test_parses_markdown_fenced_json():
    raw = '```json\n{"summary": "hello", "key_points": ["a", "b"]}\n```'
    assert _parse_json_object(raw) == VALID


def test_parses_json_with_preamble_text():
    raw = 'Here is your answer:\n{"summary": "hello", "key_points": ["a", "b"]}\nHope that helps!'
    assert _parse_json_object(raw) == VALID


def test_parses_json_with_trailing_comments():
    raw = '{"summary": "hello", "key_points": ["a", "b"]}\nLet me know if you need more.'
    assert _parse_json_object(raw) == VALID


def test_raises_on_garbage():
    with pytest.raises(LLMInvalidResponse):
        _parse_json_object("the meeting went very well, no structure at all")


def test_raises_on_nested_but_unparseable():
    with pytest.raises(LLMInvalidResponse):
        _parse_json_object('{"summary": unclosed')