from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from context_capital.storage import Store


def _make_memory(
    subject_id: str,
    predicate: str = "prefers",
    value: str = "PyTorch",
    sensitivity: str = "work",
) -> dict[str, Any]:
    return {
        "id": f"mem_{predicate[:8].ljust(8, 'a')}" + "0" * 24,
        "subject_id": subject_id,
        "kind": "preference",
        "predicate": predicate,
        "object": {"value": value, "type": "tool"},
        "confidence": 0.9,
        "sensitivity": sensitivity,
        "provenance": {
            "source": "manual:test",
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "raw_excerpt": "test",
            "imported": False,
            "model": "mock",
        },
    }


def test_store_creates_schema(temp_db_path: Path) -> None:
    with Store(temp_db_path):
        pass
    assert temp_db_path.exists()


def test_add_and_list_memory(
    temp_db_path: Path, sample_subject_did: str
) -> None:
    with Store(temp_db_path) as store:
        store.ensure_subject(sample_subject_did)
        store.add_memory(
            _make_memory(sample_subject_did, predicate="prefers", value="PyTorch")
        )
        mems = store.list_memories(subject_id=sample_subject_did)
    assert len(mems) == 1
    assert mems[0]["object"]["value"] == "PyTorch"


def test_list_filter_by_kind(
    temp_db_path: Path, sample_subject_did: str
) -> None:
    with Store(temp_db_path) as store:
        store.ensure_subject(sample_subject_did)
        m1 = _make_memory(
            sample_subject_did, predicate="prefers", value="PyTorch"
        )
        m2 = _make_memory(sample_subject_did, predicate="uses", value="Python")
        m2["kind"] = "skill"
        store.add_memory(m1)
        store.add_memory(m2)
        skill_mems = store.list_memories(
            subject_id=sample_subject_did, kind="skill"
        )
    assert len(skill_mems) == 1
    assert skill_mems[0]["object"]["value"] == "Python"


def test_list_filter_by_sensitivity_excludes_secret(
    temp_db_path: Path, sample_subject_did: str
) -> None:
    with Store(temp_db_path) as store:
        store.ensure_subject(sample_subject_did)
        secret = _make_memory(
            sample_subject_did,
            predicate="knows",
            value="bank-PIN",
            sensitivity="secret",
        )
        work = _make_memory(sample_subject_did, predicate="uses", value="Python")
        store.add_memory(secret)
        store.add_memory(work)
        non_secret = store.list_memories(
            subject_id=sample_subject_did,
            sensitivity=["public", "work", "personal"],
        )
    assert all(m["sensitivity"] != "secret" for m in non_secret)
    assert len(non_secret) == 1


def test_add_memory_writes_audit_entry_no_raw_text(
    temp_db_path: Path, sample_subject_did: str
) -> None:
    with Store(temp_db_path) as store:
        store.ensure_subject(sample_subject_did)
        store.add_memory(_make_memory(sample_subject_did), actor="test")
        audit = store.audit_log(limit=10)
    assert any(e["action"] == "extract:done" for e in audit)
    # FR-9.6: details MUST NOT include raw memory text.
    assert all("PyTorch" not in str(e["details"]) for e in audit)


def test_get_memory_returns_none_for_missing(temp_db_path: Path) -> None:
    with Store(temp_db_path) as store:
        assert store.get_memory("mem_" + "0" * 32) is None  # noqa: S105
