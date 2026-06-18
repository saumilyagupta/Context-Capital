"""End-to-end round-trip: extract → store → export → verify → import → list."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import nacl.signing

from context_capital.crypto import sign_document, verify_document
from context_capital.extract import extract_mock_memories
from context_capital.sanitize import SanitizationMode, sanitize_memory
from context_capital.storage import Store

SUBJECT = "did:key:z6MkpTHR8VNsBxYAAWHut2Geadd9jSwuBV8xRoAnwWsdvktH"


def test_full_roundtrip(tmp_path: Path, signing_key: nacl.signing.SigningKey) -> None:
    """Test complete round-trip: extract → store → export → verify → import → list."""
    text = "I prefer PyTorch for ML. My Drone uses Python."
    memories = extract_mock_memories(subject_id=SUBJECT, raw_text=text)
    assert len(memories) >= 2

    db = tmp_path / "store.db"
    with Store(db) as store:
        store.ensure_subject(SUBJECT)
        for m in memories:
            store.add_memory(m, actor="test")
        stored = store.list_memories(subject_id=SUBJECT)
    assert len(stored) == len(memories)

    doc = {
        "@context": "https://contextprotocol.org/ns/v0.1",
        "context_protocol_version": "0.1.0",
        "subject": {"id": SUBJECT, "type": "person"},
        "issuer": {
            "tool": "context-capital@0.1.0",
            "exported_at": datetime.now(timezone.utc).isoformat(),
        },
        "memories": stored,
    }
    signed = sign_document(doc, signing_key)
    assert verify_document(signed) is True

    raw = json.dumps(signed, default=str)
    reparsed = json.loads(raw)
    assert verify_document(reparsed) is True

    db2 = tmp_path / "store2.db"
    with Store(db2) as store2:
        store2.ensure_subject(SUBJECT)
        for m in reparsed["memories"]:
            clean = sanitize_memory(m, mode=SanitizationMode.WRAP)
            assert clean is not None
            clean["provenance"]["imported"] = True
            clean["provenance"]["import_source"] = reparsed["issuer"]["tool"]
            store2.add_memory(clean, actor="test:import")
        re_listed = store2.list_memories(subject_id=SUBJECT)
    assert len(re_listed) == len(stored)
    assert all(m["provenance"]["imported"] for m in re_listed)
