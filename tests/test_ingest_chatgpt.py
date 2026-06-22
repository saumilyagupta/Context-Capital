"""Tests for ChatGPT export parser."""
from __future__ import annotations

from pathlib import Path

import pytest

from context_capital.ingest.chatgpt import parse_chatgpt_export
from context_capital.ingest.types import IngestRole


@pytest.fixture
def fixture_path() -> Path:
    return Path(__file__).parent / "fixtures" / "captures" / "chatgpt-synthetic.json"


def test_parses_synthetic_fixture(fixture_path: Path) -> None:
    contexts = list(parse_chatgpt_export(fixture_path))
    assert len(contexts) == 2
    assert contexts[0].vendor == "chatgpt"
    assert contexts[0].vendor_conversation_id == "conv_a1b2c3"
    assert contexts[0].title == "Project planning"


def test_walks_mapping_in_node_order(fixture_path: Path) -> None:
    ctx = next(parse_chatgpt_export(fixture_path))
    assert [m.seq for m in ctx.messages] == [0, 1, 2]
    assert ctx.messages[0].role == IngestRole.USER
    assert ctx.messages[1].role == IngestRole.ASSISTANT
    assert ctx.messages[2].role == IngestRole.TOOL


def test_concatenates_content_parts(fixture_path: Path) -> None:
    ctx = next(parse_chatgpt_export(fixture_path))
    assert ctx.messages[0].content == "I prefer PyTorch for ML."


def test_skips_conversations_with_no_messages(fixture_path: Path) -> None:
    contexts = list(parse_chatgpt_export(fixture_path))
    assert contexts[1].vendor_conversation_id == "conv_d4e5f6"
    assert contexts[1].messages == []


def test_file_hash_is_deterministic(fixture_path: Path) -> None:
    a = list(parse_chatgpt_export(fixture_path))
    b = list(parse_chatgpt_export(fixture_path))
    assert a[0].source_file_hash == b[0].source_file_hash
    assert len(a[0].source_file_hash) == 64


def test_created_at_decoded_from_unix_epoch(fixture_path: Path) -> None:
    ctx = next(parse_chatgpt_export(fixture_path))
    assert ctx.messages[0].created_at is not None
    assert ctx.messages[0].created_at.year == 2024


def test_vendor_message_id_preserved(fixture_path: Path) -> None:
    ctx = next(parse_chatgpt_export(fixture_path))
    assert ctx.messages[0].vendor_message_id == "msg-1"
