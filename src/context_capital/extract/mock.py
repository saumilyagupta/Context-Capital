"""Deterministic mock memory extractor — no LLM API calls.

The real `litellm`-fronted extractor is Phase-1.5. This mock keeps tests
fast and offline while still exercising the IDs / provenance / sensitivity
defaults the rest of the stack depends on.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from context_capital.schema.models import MemoryKind, Sensitivity, compute_memory_id

_RULES: list[tuple[str, dict[str, Any]]] = [
    ("pytorch", {
        "kind": MemoryKind.PREFERENCE,
        "predicate": "prefers",
        "object": {"value": "PyTorch", "type": "tool"},
        "sensitivity": Sensitivity.WORK,
    }),
    ("python", {
        "kind": MemoryKind.SKILL,
        "predicate": "uses",
        "object": {"value": "Python", "type": "language"},
        "sensitivity": Sensitivity.WORK,
    }),
    ("drone", {
        "kind": MemoryKind.PROJECT,
        "predicate": "works-on",
        "object": {"value": "Autonomous Drone", "type": "project"},
        "sensitivity": Sensitivity.WORK,
    }),
]


def extract_mock_memories(
    *,
    subject_id: str,
    raw_text: str,
    source: str = "manual:test",
    model: str = "mock/extractor-v0",
) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc).isoformat()
    lower = raw_text.lower()
    memories: list[dict[str, Any]] = []
    for needle, tmpl in _RULES:
        if needle not in lower:
            continue
        mem_id = compute_memory_id(
            kind=tmpl["kind"],
            predicate=tmpl["predicate"],
            subject_id=subject_id,
            object_value=tmpl["object"]["value"],
            object_type=tmpl["object"]["type"],
            sensitivity=tmpl["sensitivity"],
        )
        memories.append({
            "id": mem_id,
            "kind": str(tmpl["kind"]),
            "subject_id": subject_id,
            "predicate": tmpl["predicate"],
            "object": tmpl["object"],
            "confidence": 0.85,
            "sensitivity": str(tmpl["sensitivity"]),
            "provenance": {
                "source": source,
                "extracted_at": now,
                "raw_excerpt": raw_text[:200],
                "imported": False,
                "model": model,
            },
        })
    return memories
