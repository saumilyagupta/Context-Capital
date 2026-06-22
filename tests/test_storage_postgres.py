"""Round-trip tests against a real Postgres container (gated)."""
from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("CC_RUN_PG_TESTS") != "1",
    reason="set CC_RUN_PG_TESTS=1 to run Postgres tests",
)


@pytest.fixture(scope="module")
def pg_dsn():
    from testcontainers.postgres import PostgresContainer
    container = PostgresContainer("pgvector/pgvector:pg16")
    container.start()
    try:
        dsn = container.get_connection_url().replace("postgresql+psycopg2://", "postgresql://")
        yield dsn
    finally:
        container.stop()


def _sample_memory(subject_id: str, suffix: str = "a") -> dict:
    return {
        "id": f"mem_{'0' * 31}{suffix}",
        "subject_id": subject_id,
        "kind": "preference",
        "predicate": "prefers_language",
        "object": {"value": "Python", "type": "string"},
        "confidence": 0.92,
        "sensitivity": "work",
        "provenance": {
            "source": "manual",
            "extracted_at": "2026-06-22T12:00:00+00:00",
            "raw_excerpt": "I love Python.",
            "imported": False,
            "import_source": None,
            "model": "test",
        },
    }


def test_connect_creates_schema(pg_dsn):
    from context_capital.storage.postgres import PostgresStore
    with PostgresStore(pg_dsn) as s:
        with s._conn.cursor() as cur:  # noqa: SLF001
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='public' ORDER BY table_name"
            )
            tables = {row["table_name"] for row in cur.fetchall()}
    for required in ("subjects", "memories", "provenance", "audit_log_entries",
                     "contexts", "raw_messages", "vector_embeddings"):
        assert required in tables, f"missing table: {required}"


def test_ensure_subject_idempotent(pg_dsn):
    from context_capital.storage.postgres import PostgresStore
    with PostgresStore(pg_dsn) as s:
        s.ensure_subject("did:test:1", "person", "Alice")
        s.ensure_subject("did:test:1", "person", "Alice")
        with s._conn.cursor() as cur:  # noqa: SLF001
            cur.execute("SELECT COUNT(*) AS c FROM subjects WHERE id=%s", ("did:test:1",))
            assert cur.fetchone()["c"] == 1


def test_add_memory_round_trip(pg_dsn):
    from context_capital.storage.postgres import PostgresStore
    with PostgresStore(pg_dsn) as s:
        s.ensure_subject("did:test:2")
        m = _sample_memory("did:test:2", "b")
        s.add_memory(m, actor="cli")
        got = s.get_memory(m["id"])
    assert got is not None
    assert got["id"] == m["id"]
    assert got["predicate"] == "prefers_language"
    assert got["object"]["value"] == "Python"
    assert got["sensitivity"] == "work"
    assert got["provenance"]["source"] == "manual"


def test_list_memories_filters(pg_dsn):
    from context_capital.storage.postgres import PostgresStore
    with PostgresStore(pg_dsn) as s:
        s.ensure_subject("did:test:3")
        s.add_memory(_sample_memory("did:test:3", "c"))
        s.add_memory({**_sample_memory("did:test:3", "d"), "kind": "fact"})
        prefs = s.list_memories(subject_id="did:test:3", kind="preference")
        facts = s.list_memories(subject_id="did:test:3", kind="fact")
        secret_only = s.list_memories(subject_id="did:test:3", sensitivity=["secret"])
    assert {m["kind"] for m in prefs} == {"preference"}
    assert {m["kind"] for m in facts} == {"fact"}
    assert secret_only == []


def test_audit_log_contains_memory_id_only(pg_dsn):
    """FR-9.6: audit MUST NOT contain raw memory text."""
    import json

    from context_capital.storage.postgres import PostgresStore
    with PostgresStore(pg_dsn) as s:
        s.ensure_subject("did:test:4")
        m = _sample_memory("did:test:4", "e")
        s.add_memory(m, actor="cli")
        entries = s.audit_log(limit=10)
    extract_done = [e for e in entries if e["action"] == "extract:done"]
    assert extract_done
    details = extract_done[0]["details"]
    if isinstance(details, str):
        details = json.loads(details)
    assert details == {"memory_id": m["id"]}
    assert "Python" not in str(details)


def test_persist_ingest_context_idempotent(pg_dsn):
    from context_capital.ingest.types import IngestContext, IngestMessage, IngestRole
    from context_capital.storage.postgres import PostgresStore
    ic = IngestContext(
        vendor="chatgpt",
        vendor_conversation_id="conv-xyz",
        captured_at=datetime(2026, 6, 22, 12, tzinfo=timezone.utc),
        source_file_hash="a" * 64,
        messages=[IngestMessage(seq=0, role=IngestRole.USER, content="Hi")],
        title="Test",
    )
    with PostgresStore(pg_dsn) as s:
        s.ensure_subject("did:test:5")
        cid1 = s.persist_ingest_context(ic, subject_id="did:test:5")
        cid2 = s.persist_ingest_context(ic, subject_id="did:test:5")
    assert cid1 == cid2
