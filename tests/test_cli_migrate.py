"""Tests for cc migrate --to postgres."""
from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from typer.testing import CliRunner

runner = CliRunner()


def _init_cc(tmp_path, monkeypatch):
    from context_capital import cli as cli_mod
    monkeypatch.setattr(cli_mod, "DATA_DIR", tmp_path)
    (tmp_path / "signing.key").write_bytes(b"\x00" * 32)
    (tmp_path / "subject_did").write_text("did:test:mig:1")


def _seed_sqlite(path):
    from context_capital.ingest.types import IngestContext, IngestMessage, IngestRole
    from context_capital.storage.sqlite import SQLiteStore
    with SQLiteStore(path) as s:
        s.ensure_subject("did:test:mig:1")
        ic = IngestContext(
            vendor="chatgpt",
            vendor_conversation_id="conv-mig",
            captured_at=datetime(2026, 6, 22, tzinfo=timezone.utc),
            source_file_hash="b" * 64,
            messages=[IngestMessage(seq=0, role=IngestRole.USER, content="hi")],
            title="seed",
        )
        s.persist_ingest_context(ic, subject_id="did:test:mig:1")
        s.add_memory({
            "id": "mem_" + "0" * 31 + "a",
            "subject_id": "did:test:mig:1",
            "kind": "preference",
            "predicate": "prefers_language",
            "object": {"value": "Python", "type": "string"},
            "confidence": 0.9,
            "sensitivity": "work",
            "provenance": {
                "source": "manual",
                "extracted_at": "2026-06-22T12:00:00+00:00",
                "raw_excerpt": "I like Python.",
                "imported": False,
            },
        })


def test_migrate_rejects_unknown_to_target(tmp_path, monkeypatch):
    from context_capital.cli import app
    _init_cc(tmp_path, monkeypatch)
    db = tmp_path / "store.db"
    _seed_sqlite(db)
    res = runner.invoke(app, ["migrate", "--to", "mysql", "--source", str(db)])
    assert res.exit_code != 0
    assert "postgres" in res.output.lower()


def test_migrate_requires_target_when_env_unset(tmp_path, monkeypatch):
    from context_capital.cli import app
    _init_cc(tmp_path, monkeypatch)
    monkeypatch.delenv("CC_DATABASE_URL", raising=False)
    db = tmp_path / "store.db"
    _seed_sqlite(db)
    res = runner.invoke(app, ["migrate", "--to", "postgres", "--source", str(db)])
    assert res.exit_code != 0


@pytest.mark.skipif(
    os.environ.get("CC_RUN_PG_TESTS") != "1",
    reason="set CC_RUN_PG_TESTS=1",
)
def test_migrate_sqlite_to_postgres_row_count_parity(tmp_path, monkeypatch):
    from testcontainers.postgres import PostgresContainer

    from context_capital.cli import app
    from context_capital.storage.postgres import PostgresStore
    from context_capital.storage.sqlite import SQLiteStore

    _init_cc(tmp_path, monkeypatch)
    src = tmp_path / "store.db"
    _seed_sqlite(src)

    with PostgresContainer("pgvector/pgvector:pg16") as pg:
        dsn = pg.get_connection_url().replace("postgresql+psycopg2://", "postgresql://")

        res = runner.invoke(app, [
            "migrate", "--to", "postgres",
            "--source", str(src),
            "--target", dsn,
            "--no-embeddings",
        ])
        assert res.exit_code == 0, res.output

        with SQLiteStore(src) as s_src, PostgresStore(dsn) as s_dst:
            src_mems = s_src.list_memories()
            dst_mems = s_dst.list_memories()
        assert len(src_mems) == len(dst_mems) == 1
        assert {m["id"] for m in src_mems} == {m["id"] for m in dst_mems}

        # Idempotency: second run must not duplicate memories.
        res2 = runner.invoke(app, [
            "migrate", "--to", "postgres",
            "--source", str(src),
            "--target", dsn,
            "--no-embeddings",
        ])
        assert res2.exit_code == 0, res2.output
        with PostgresStore(dsn) as s_dst:
            assert len(s_dst.list_memories()) == 1
