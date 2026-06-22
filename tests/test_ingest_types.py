"""Tests for ingest canonical types."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from context_capital.ingest.types import IngestContext, IngestMessage, IngestRole


def _now() -> datetime:
    return datetime(2026, 6, 22, 10, 0, 0, tzinfo=timezone.utc)


def test_ingest_message_minimal() -> None:
    m = IngestMessage(seq=0, role=IngestRole.USER, content="hello")
    assert m.seq == 0
    assert m.role == "user"
    assert m.created_at is None


def test_ingest_message_negative_seq_rejected() -> None:
    with pytest.raises(ValidationError):
        IngestMessage(seq=-1, role=IngestRole.USER, content="x")


def test_ingest_message_extra_field_forbidden() -> None:
    with pytest.raises(ValidationError):
        IngestMessage.model_validate(
            {"seq": 0, "role": "user", "content": "x", "extra": "nope"}
        )


def test_ingest_message_unknown_role_rejected() -> None:
    with pytest.raises(ValidationError):
        IngestMessage.model_validate({"seq": 0, "role": "bot", "content": "x"})


def test_ingest_context_minimal() -> None:
    ctx = IngestContext(
        vendor="chatgpt",
        vendor_conversation_id="conv_abc",
        captured_at=_now(),
        source_file_hash="a" * 64,
        messages=[],
    )
    assert ctx.vendor == "chatgpt"
    assert ctx.messages == []
    assert ctx.title is None


def test_ingest_context_with_messages() -> None:
    ctx = IngestContext(
        vendor="claude",
        vendor_conversation_id="conv_xyz",
        title="Project planning",
        captured_at=_now(),
        source_file_hash="b" * 64,
        messages=[
            IngestMessage(seq=0, role=IngestRole.USER, content="hi"),
            IngestMessage(seq=1, role=IngestRole.ASSISTANT, content="hello"),
        ],
    )
    assert len(ctx.messages) == 2
    assert ctx.messages[1].role == IngestRole.ASSISTANT


def test_ingest_context_extra_field_forbidden() -> None:
    with pytest.raises(ValidationError):
        IngestContext.model_validate({
            "vendor": "chatgpt",
            "vendor_conversation_id": "x",
            "captured_at": _now().isoformat(),
            "source_file_hash": "c" * 64,
            "messages": [],
            "extra": "nope",
        })
