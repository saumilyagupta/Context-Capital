from __future__ import annotations

from typing import Any

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from context_capital.schema import (
    CONTEXT_PROTOCOL_V0_1_SCHEMA,
    ContextDocument,
    Memory,
    MemoryKind,
    Sensitivity,
    compute_memory_id,
)


def test_minimal_doc_validates(minimal_doc: dict[str, Any]) -> None:
    minimal_doc["signature"] = {"alg": "ed25519", "value": "AA==", "public_key": "BB==", "canonicalization": "jcs"}
    doc = ContextDocument.model_validate(minimal_doc)
    assert doc.context_protocol_version == "0.1.0"
    assert len(doc.memories) == 1


def test_missing_sensitivity_is_rejected(minimal_doc: dict[str, Any]) -> None:
    minimal_doc["signature"] = {"alg": "ed25519", "value": "A", "public_key": "B", "canonicalization": "jcs"}
    del minimal_doc["memories"][0]["sensitivity"]
    with pytest.raises(ValidationError):
        ContextDocument.model_validate(minimal_doc)


def test_invalid_memory_id_pattern_rejected() -> None:
    with pytest.raises(ValidationError):
        Memory.model_validate({
            "id": "not_prefixed",
            "kind": "preference",
            "subject_id": "did:key:zABC",
            "predicate": "prefers",
            "object": {"value": "X"},
            "confidence": 0.5,
            "sensitivity": "work",
            "provenance": {"source": "manual", "extracted_at": "2026-06-18T10:00:00+00:00"},
        })


def test_confidence_out_of_range_rejected() -> None:
    with pytest.raises(ValidationError):
        Memory.model_validate({
            "id": "mem_" + "a" * 32,
            "kind": "preference",
            "subject_id": "did:key:zABC",
            "predicate": "prefers",
            "object": {"value": "X"},
            "confidence": 1.5,
            "sensitivity": "work",
            "provenance": {"source": "manual", "extracted_at": "2026-06-18T10:00:00+00:00"},
        })


def test_predicate_too_long_rejected() -> None:
    with pytest.raises(ValidationError):
        Memory.model_validate({
            "id": "mem_" + "a" * 32,
            "kind": "preference",
            "subject_id": "did:key:zABC",
            "predicate": "x" * 65,
            "object": {"value": "X"},
            "confidence": 0.5,
            "sensitivity": "work",
            "provenance": {"source": "manual", "extracted_at": "2026-06-18T10:00:00+00:00"},
        })


def test_compute_memory_id_is_deterministic() -> None:
    a = compute_memory_id(kind=MemoryKind.PREFERENCE, predicate="prefers", subject_id="did:key:zABC",
                          object_value="PyTorch", object_type="tool", sensitivity=Sensitivity.WORK)
    b = compute_memory_id(kind=MemoryKind.PREFERENCE, predicate="prefers", subject_id="did:key:zABC",
                          object_value="PyTorch", object_type="tool", sensitivity=Sensitivity.WORK)
    assert a == b
    assert a.startswith("mem_")
    assert len(a) == len("mem_") + 32


def test_compute_memory_id_differs_for_different_objects() -> None:
    a = compute_memory_id(kind="preference", predicate="prefers", subject_id="did:key:zABC",
                          object_value="PyTorch", object_type="tool", sensitivity="work")
    b = compute_memory_id(kind="preference", predicate="prefers", subject_id="did:key:zABC",
                          object_value="TensorFlow", object_type="tool", sensitivity="work")
    assert a != b


def test_json_schema_is_valid_metaschema() -> None:
    Draft202012Validator.check_schema(CONTEXT_PROTOCOL_V0_1_SCHEMA)
