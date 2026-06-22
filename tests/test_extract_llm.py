"""Tests for the litellm-fronted real extractor (no live API)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pytest

import context_capital.extract.llm as llm_mod
from context_capital.extract.llm import extract_memories
from context_capital.ingest.types import IngestContext, IngestMessage, IngestRole


def _ctx(messages: list[tuple[str, str]]) -> IngestContext:
    return IngestContext(
        vendor="chatgpt",
        vendor_conversation_id="conv_x",
        title="t",
        captured_at=datetime(2026, 6, 22, tzinfo=timezone.utc),
        source_file_hash="a" * 64,
        messages=[
            IngestMessage(seq=i, role=IngestRole(role), content=content)
            for i, (role, content) in enumerate(messages)
        ],
    )


def _mock_response(memories: list[dict[str, Any]]) -> dict[str, Any]:
    return {"choices": [{"message": {"content": json.dumps({"memories": memories})}}]}


def _patch_completion(monkeypatch: pytest.MonkeyPatch, response: dict[str, Any]) -> None:
    monkeypatch.setattr(llm_mod.litellm, "completion", lambda **_kw: response)
    monkeypatch.setattr(llm_mod.litellm, "token_counter", lambda **_kw: 100)


def test_extracts_valid_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_completion(monkeypatch, _mock_response([{
        "kind": "preference",
        "predicate": "prefers",
        "object": {"value": "PyTorch", "type": "tool"},
        "confidence": 0.9,
        "sensitivity": "work",
        "provenance_excerpt": "I prefer PyTorch.",
    }]))
    mems = extract_memories(subject_id="did:key:zABC", context=_ctx([("user", "I prefer PyTorch.")]))
    assert len(mems) == 1
    assert mems[0]["kind"] == "preference"
    assert mems[0]["object"]["value"] == "PyTorch"
    assert mems[0]["provenance"]["source"] == "chatgpt:conv_x"
    assert mems[0]["provenance"]["imported"] is False


def test_drops_invalid_kind(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_completion(monkeypatch, _mock_response([{
        "kind": "opinion",
        "predicate": "thinks",
        "object": {"value": "x"},
        "confidence": 0.5,
        "sensitivity": "work",
    }]))
    mems = extract_memories(subject_id="did:key:zABC", context=_ctx([("user", "I think.")]))
    assert mems == []


def test_drops_missing_required(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_completion(monkeypatch, _mock_response([{
        "kind": "preference",
        "predicate": "prefers",
        "confidence": 0.5,
        "sensitivity": "work",
    }]))
    mems = extract_memories(subject_id="did:key:zABC", context=_ctx([("user", "x")]))
    assert mems == []


def test_confidence_clamped_in_range(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_completion(monkeypatch, _mock_response([{
        "kind": "preference",
        "predicate": "prefers",
        "object": {"value": "x"},
        "confidence": 1.5,
        "sensitivity": "work",
    }]))
    mems = extract_memories(subject_id="did:key:zABC", context=_ctx([("user", "x")]))
    assert len(mems) == 1
    assert mems[0]["confidence"] == 1.0


def test_deduplicates_within_one_call(monkeypatch: pytest.MonkeyPatch) -> None:
    same = {
        "kind": "preference",
        "predicate": "prefers",
        "object": {"value": "PyTorch", "type": "tool"},
        "confidence": 0.9,
        "sensitivity": "work",
        "provenance_excerpt": "x",
    }
    _patch_completion(monkeypatch, _mock_response([same, same, same]))
    mems = extract_memories(subject_id="did:key:zABC", context=_ctx([("user", "x")]))
    assert len(mems) == 1


def test_empty_context_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_completion(monkeypatch, _mock_response([]))
    mems = extract_memories(subject_id="did:key:zABC", context=_ctx([]))
    assert mems == []


def test_invalid_json_from_model_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    bad = {"choices": [{"message": {"content": "not json"}}]}
    monkeypatch.setattr(llm_mod.litellm, "completion", lambda **_kw: bad)
    monkeypatch.setattr(llm_mod.litellm, "token_counter", lambda **_kw: 100)
    mems = extract_memories(subject_id="did:key:zABC", context=_ctx([("user", "x")]))
    assert mems == []


def test_llm_exception_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(**_kw: Any) -> Any:
        raise RuntimeError("api down")
    monkeypatch.setattr(llm_mod.litellm, "completion", boom)
    monkeypatch.setattr(llm_mod.litellm, "token_counter", lambda **_kw: 100)
    mems = extract_memories(subject_id="did:key:zABC", context=_ctx([("user", "x")]))
    assert mems == []
