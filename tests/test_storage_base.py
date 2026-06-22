"""Tests for the StoreBase ABC."""
from __future__ import annotations

import pytest

from context_capital.storage.base import StoreBase


def test_storebase_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        StoreBase()  # type: ignore[abstract]


class _StubStore(StoreBase):
    """Minimal concrete subclass — implements every abstract method as a no-op."""

    def connect(self) -> None: ...
    def close(self) -> None: ...
    def ensure_subject(self, subject_id, subject_type="person", display_name=None): ...
    def add_memory(self, memory, *, actor="system"): ...
    def list_memories(self, *, subject_id=None, kind=None, sensitivity=None):
        return []
    def get_memory(self, memory_id):
        return None
    def persist_ingest_context(self, ic, *, subject_id, actor="system"):
        return "ctx-stub"
    def get_context_by_unique(self, subject_id, source_file_hash, vendor_conversation_id):
        return None
    def audit_log(self, limit=100):
        return []


def test_stub_supports_embeddings_default_false():
    assert _StubStore().supports_embeddings() is False


def test_stub_add_embedding_is_noop():
    _StubStore().add_embedding("mem_x", [0.1, 0.2], model="dummy")


def test_stub_search_by_embedding_raises_not_implemented():
    with pytest.raises(NotImplementedError, match="semantic search requires the Postgres backend"):
        _StubStore().search_by_embedding([0.0] * 4)


def test_context_manager_calls_connect_and_close():
    calls = []

    class _Recorder(_StubStore):
        def connect(self) -> None:
            calls.append("connect")
        def close(self) -> None:
            calls.append("close")

    with _Recorder() as s:
        assert isinstance(s, StoreBase)
    assert calls == ["connect", "close"]
