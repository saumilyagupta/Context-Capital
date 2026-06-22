"""Tests for Store.persist_ingest_context."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from context_capital.ingest.types import IngestContext, IngestMessage, IngestRole
from context_capital.storage import Store


def _now() -> datetime:
    return datetime(2026, 6, 22, 10, 0, 0, tzinfo=timezone.utc)


def _ic(messages_count: int = 2) -> IngestContext:
    return IngestContext(
        vendor="chatgpt",
        vendor_conversation_id="conv_abc",
        title="t",
        captured_at=_now(),
        source_file_hash="a" * 64,
        messages=[
            IngestMessage(
                seq=i,
                role=IngestRole.USER if i % 2 == 0 else IngestRole.ASSISTANT,
                content=f"m{i}",
            )
            for i in range(messages_count)
        ],
    )


def _subject() -> str:
    return "did:key:zABC"


def test_persists_context_and_messages(tmp_path: Path) -> None:
    db = tmp_path / "store.db"
    with Store(db) as store:
        store.ensure_subject(_subject())
        cid = store.persist_ingest_context(_ic(messages_count=3), subject_id=_subject())
        assert isinstance(cid, str) and len(cid) > 0
        row = store.get_context_by_unique(_subject(), "a" * 64, "conv_abc")
        assert row is not None
        assert row["source_vendor"] == "chatgpt"


def test_idempotent_on_same_file_and_conversation(tmp_path: Path) -> None:
    db = tmp_path / "store.db"
    with Store(db) as store:
        store.ensure_subject(_subject())
        cid1 = store.persist_ingest_context(_ic(), subject_id=_subject())
        cid2 = store.persist_ingest_context(_ic(), subject_id=_subject())
        assert cid1 == cid2


def test_different_file_hash_creates_new_context(tmp_path: Path) -> None:
    db = tmp_path / "store.db"
    with Store(db) as store:
        store.ensure_subject(_subject())
        ic1 = _ic()
        ic2 = _ic().model_copy(update={"source_file_hash": "b" * 64})
        cid1 = store.persist_ingest_context(ic1, subject_id=_subject())
        cid2 = store.persist_ingest_context(ic2, subject_id=_subject())
        assert cid1 != cid2


def test_writes_audit_entry_for_capture(tmp_path: Path) -> None:
    db = tmp_path / "store.db"
    with Store(db) as store:
        store.ensure_subject(_subject())
        store.persist_ingest_context(_ic(), subject_id=_subject(), actor="test")
        entries = store.audit_log(limit=10)
    assert any(e["action"] == "capture" for e in entries)
