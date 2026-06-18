"""Shared pytest fixtures."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import nacl.signing
import pytest


@pytest.fixture
def signing_key() -> nacl.signing.SigningKey:
    return nacl.signing.SigningKey(b"\x01" * 32)


@pytest.fixture
def now_iso() -> str:
    return datetime(2026, 6, 18, 10, 0, 0, tzinfo=timezone.utc).isoformat()


@pytest.fixture
def sample_subject_did() -> str:
    return "did:key:z6MkpTHR8VNsBxYAAWHut2Geadd9jSwuBV8xRoAnwWsdvktH"


@pytest.fixture
def minimal_doc(sample_subject_did: str, now_iso: str) -> dict[str, Any]:
    return {
        "@context": "https://contextprotocol.org/ns/v0.1",
        "context_protocol_version": "0.1.0",
        "subject": {"id": sample_subject_did, "type": "person"},
        "issuer": {"tool": "context-capital@0.1.0", "exported_at": now_iso},
        "memories": [
            {
                "id": "mem_3a7b4c5d6e7f8091a2b3c4d5e6f70819",
                "kind": "preference",
                "subject_id": sample_subject_did,
                "predicate": "prefers",
                "object": {"value": "PyTorch", "type": "tool"},
                "confidence": 0.92,
                "provenance": {
                    "source": "chatgpt:conv_a1b2c3",
                    "extracted_at": now_iso,
                    "raw_excerpt": "I prefer PyTorch.",
                    "model": "mock/test",
                },
                "sensitivity": "work",
            }
        ],
    }


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    return tmp_path / "store.db"


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"
