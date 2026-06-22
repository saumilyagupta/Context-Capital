"""Tests for Claude export parser."""
from __future__ import annotations

from pathlib import Path

import pytest

from context_capital.ingest.claude import parse_claude_export
from context_capital.ingest.types import IngestRole


@pytest.fixture
def fixture_path() -> Path:
    return Path(__file__).parent / "fixtures" / "captures" / "claude-synthetic.json"


def test_parses_synthetic_fixture(fixture_path: Path) -> None:
    contexts = list(parse_claude_export(fixture_path))
    assert len(contexts) == 1
    assert contexts[0].vendor == "claude"
    assert contexts[0].vendor_conversation_id == "conv_xyz789"
    assert contexts[0].title == "Project planning"


def test_human_sender_maps_to_user(fixture_path: Path) -> None:
    ctx = next(parse_claude_export(fixture_path))
    assert ctx.messages[0].role == IngestRole.USER


def test_assistant_sender_preserved(fixture_path: Path) -> None:
    ctx = next(parse_claude_export(fixture_path))
    assert ctx.messages[1].role == IngestRole.ASSISTANT


def test_tool_use_block_emitted_as_marker(fixture_path: Path) -> None:
    ctx = next(parse_claude_export(fixture_path))
    assert "[tool_use: web_search]" in ctx.messages[1].content


def test_empty_text_and_content_skipped(fixture_path: Path) -> None:
    ctx = next(parse_claude_export(fixture_path))
    assert len(ctx.messages) == 2


def test_file_hash_is_deterministic(fixture_path: Path) -> None:
    a = list(parse_claude_export(fixture_path))
    b = list(parse_claude_export(fixture_path))
    assert a[0].source_file_hash == b[0].source_file_hash
    assert len(a[0].source_file_hash) == 64


def test_created_at_parsed_from_iso8601(fixture_path: Path) -> None:
    ctx = next(parse_claude_export(fixture_path))
    assert ctx.messages[0].created_at is not None
    assert ctx.messages[0].created_at.year == 2025
