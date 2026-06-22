"""Embedding + semantic search round-trip tests (gated)."""
from __future__ import annotations

import os
from unittest.mock import patch

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
        yield container.get_connection_url().replace("postgresql+psycopg2://", "postgresql://")
    finally:
        container.stop()


def _mem(subject_id: str, suffix: str, value: str, kind: str = "preference") -> dict:
    return {
        "id": f"mem_{'0' * 31}{suffix}",
        "subject_id": subject_id,
        "kind": kind,
        "predicate": "prefers",
        "object": {"value": value, "type": "string"},
        "confidence": 0.9,
        "sensitivity": "work",
        "provenance": {
            "source": "manual",
            "extracted_at": "2026-06-22T12:00:00+00:00",
            "raw_excerpt": value,
            "imported": False,
            "import_source": None,
            "model": "test",
        },
    }


def test_supports_embeddings_true(pg_dsn):
    from context_capital.storage.postgres import PostgresStore
    with PostgresStore(pg_dsn) as s:
        assert s.supports_embeddings() is True


def test_add_memory_writes_embedding_row(pg_dsn):
    from context_capital.extract import embed as embed_mod
    from context_capital.storage.postgres import PostgresStore

    fixed_vec = [0.1] * 1024
    with patch.object(embed_mod, "embed_text", return_value=fixed_vec):
        with PostgresStore(pg_dsn) as s:
            s.ensure_subject("did:test:emb:1")
            m = _mem("did:test:emb:1", "1", "Python")
            s.add_memory(m, actor="cli")
            with s._conn.cursor() as cur:  # noqa: SLF001
                cur.execute(
                    "SELECT model FROM vector_embeddings WHERE memory_id=%s", (m["id"],)
                )
                row = cur.fetchone()
    assert row is not None
    assert row["model"] == "voyage/voyage-3"


def test_add_memory_with_failing_embedding_still_persists(pg_dsn):
    from context_capital.extract import embed as embed_mod
    from context_capital.storage.postgres import PostgresStore

    with patch.object(embed_mod, "embed_text", return_value=None):
        with PostgresStore(pg_dsn) as s:
            s.ensure_subject("did:test:emb:2")
            m = _mem("did:test:emb:2", "2", "Rust")
            s.add_memory(m, actor="cli")
            got = s.get_memory(m["id"])
            with s._conn.cursor() as cur:  # noqa: SLF001
                cur.execute(
                    "SELECT COUNT(*) AS c FROM vector_embeddings WHERE memory_id=%s",
                    (m["id"],),
                )
                count = cur.fetchone()["c"]
    assert got is not None
    assert count == 0


def test_search_by_embedding_returns_nearest_first(pg_dsn):
    from context_capital.extract import embed as embed_mod
    from context_capital.storage.postgres import PostgresStore

    vec_a = [1.0] + [0.0] * 1023
    vec_b = [0.0, 1.0] + [0.0] * 1022

    def fake_embed(text, *, model="voyage/voyage-3"):
        return vec_a if "Python" in text else vec_b

    with patch.object(embed_mod, "embed_text", side_effect=fake_embed):
        with PostgresStore(pg_dsn) as s:
            s.ensure_subject("did:test:emb:3")
            s.add_memory(_mem("did:test:emb:3", "3", "Python"))
            s.add_memory(_mem("did:test:emb:3", "4", "Rust"))
            results = s.search_by_embedding(vec_a, limit=2, subject_id="did:test:emb:3")
    assert len(results) == 2
    assert results[0]["object"]["value"] == "Python"
    assert results[1]["object"]["value"] == "Rust"


def test_search_by_embedding_honors_kind_and_sensitivity_filters(pg_dsn):
    from context_capital.extract import embed as embed_mod
    from context_capital.storage.postgres import PostgresStore

    vec = [0.5] * 1024
    with patch.object(embed_mod, "embed_text", return_value=vec):
        with PostgresStore(pg_dsn) as s:
            s.ensure_subject("did:test:emb:4")
            s.add_memory(_mem("did:test:emb:4", "5", "X", kind="preference"))
            s.add_memory({**_mem("did:test:emb:4", "6", "Y", kind="fact"), "sensitivity": "personal"})
            kinds = s.search_by_embedding(vec, kind="fact", subject_id="did:test:emb:4")
            sens = s.search_by_embedding(vec, sensitivity=["personal"], subject_id="did:test:emb:4")
    assert all(r["kind"] == "fact" for r in kinds)
    assert all(r["sensitivity"] == "personal" for r in sens)


def test_add_embedding_upserts(pg_dsn):
    from context_capital.extract import embed as embed_mod
    from context_capital.storage.postgres import PostgresStore

    with patch.object(embed_mod, "embed_text", return_value=None):
        with PostgresStore(pg_dsn) as s:
            s.ensure_subject("did:test:emb:5")
            m = _mem("did:test:emb:5", "7", "Go")
            s.add_memory(m)
            s.add_embedding(m["id"], [0.2] * 1024, model="voyage/voyage-3")
            s.add_embedding(m["id"], [0.3] * 1024, model="voyage/voyage-3")
            with s._conn.cursor() as cur:  # noqa: SLF001
                cur.execute(
                    "SELECT COUNT(*) AS c FROM vector_embeddings "
                    "WHERE memory_id=%s AND model=%s",
                    (m["id"], "voyage/voyage-3"),
                )
                assert cur.fetchone()["c"] == 1
