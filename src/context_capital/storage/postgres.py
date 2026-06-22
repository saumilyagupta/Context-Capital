"""Postgres backend — psycopg3 + pgvector. Mirrors SQLiteStore's surface."""
from __future__ import annotations

import json
import logging
import uuid
from typing import TYPE_CHECKING, Any

import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row

from context_capital.storage.base import StoreBase

if TYPE_CHECKING:
    from context_capital.ingest.types import IngestContext

logger = logging.getLogger(__name__)

# TODO(post-F-4): unify with docs/data-model/schema.sql once encryption (F-4)
# and audit hash chain (F-9) ship. The canonical schema uses bytea _enc columns
# and append-only audit triggers that this Phase-1 mirror does not yet need.
PHASE1_DDL: str = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS subjects (
    id            text PRIMARY KEY,
    type          text NOT NULL CHECK (type IN ('person','organization','agent')),
    display_name  text,
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS memories (
    id            text PRIMARY KEY,
    subject_id    text NOT NULL REFERENCES subjects(id),
    kind          text NOT NULL,
    predicate     text NOT NULL,
    object_value  text NOT NULL,
    object_type   text,
    confidence    double precision NOT NULL,
    sensitivity   text NOT NULL CHECK (sensitivity IN ('public','work','personal','secret')),
    created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS memories_subject_kind_idx       ON memories (subject_id, kind);
CREATE INDEX IF NOT EXISTS memories_subject_predicate_idx  ON memories (subject_id, predicate);

CREATE TABLE IF NOT EXISTS provenance (
    memory_id           text PRIMARY KEY REFERENCES memories(id) ON DELETE CASCADE,
    source              text NOT NULL,
    extracted_at        text NOT NULL,
    raw_excerpt         text,
    imported            boolean NOT NULL DEFAULT FALSE,
    import_source       text,
    model               text,
    sanitization_trace  text
);

CREATE TABLE IF NOT EXISTS audit_log_entries (
    id          bigserial PRIMARY KEY,
    at          timestamptz NOT NULL DEFAULT now(),
    actor       text NOT NULL,
    action      text NOT NULL,
    subject_id  text,
    details     jsonb NOT NULL DEFAULT '{}'::jsonb,
    outcome     text NOT NULL CHECK (outcome IN ('success','denied','error'))
);

CREATE TABLE IF NOT EXISTS contexts (
    id                       uuid PRIMARY KEY,
    subject_id               text NOT NULL REFERENCES subjects(id),
    source_vendor            text NOT NULL,
    source_file_hash         text NOT NULL,
    vendor_conversation_id   text NOT NULL,
    title                    text,
    captured_at              timestamptz NOT NULL,
    UNIQUE (subject_id, source_file_hash, vendor_conversation_id)
);
CREATE INDEX IF NOT EXISTS contexts_subject_idx ON contexts (subject_id);

CREATE TABLE IF NOT EXISTS raw_messages (
    id                  bigserial PRIMARY KEY,
    context_id          uuid NOT NULL REFERENCES contexts(id) ON DELETE CASCADE,
    seq                 int NOT NULL,
    role                text NOT NULL,
    content             text NOT NULL,
    created_at          text,
    vendor_message_id   text,
    UNIQUE (context_id, seq)
);
CREATE INDEX IF NOT EXISTS raw_messages_context_idx ON raw_messages (context_id);

CREATE TABLE IF NOT EXISTS vector_embeddings (
    memory_id   text NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    model       text NOT NULL,
    embedding   vector(1024) NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (memory_id, model)
);
CREATE INDEX IF NOT EXISTS vector_embeddings_hnsw_idx
    ON vector_embeddings USING hnsw (embedding vector_cosine_ops);
"""


class PostgresStore(StoreBase):
    """Postgres (+ pgvector) implementation of StoreBase."""

    def __init__(self, dsn: str, *, embed_dim: int = 1024) -> None:
        self.dsn = dsn
        self.embed_dim = embed_dim
        self._conn: psycopg.Connection[Any] | None = None

    # ---- Lifecycle --------------------------------------------------------
    def connect(self) -> None:
        self._conn = psycopg.connect(self.dsn, row_factory=dict_row, autocommit=False)
        with self._conn.cursor() as cur:
            cur.execute(PHASE1_DDL)
        self._conn.commit()
        register_vector(self._conn)

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _require_conn(self) -> psycopg.Connection[Any]:
        if self._conn is None:
            raise RuntimeError("PostgresStore is not connected — use as a context manager.")
        return self._conn

    # ---- Subjects ---------------------------------------------------------
    def ensure_subject(
        self,
        subject_id: str,
        subject_type: str = "person",
        display_name: str | None = None,
    ) -> None:
        c = self._require_conn()
        with c.cursor() as cur:
            cur.execute(
                "INSERT INTO subjects (id, type, display_name) VALUES (%s, %s, %s) "
                "ON CONFLICT (id) DO NOTHING",
                (subject_id, subject_type, display_name),
            )
        c.commit()

    # ---- Memories ---------------------------------------------------------
    def add_memory(self, memory: dict[str, Any], *, actor: str = "system") -> None:
        c = self._require_conn()
        try:
            with c.cursor() as cur:
                cur.execute(
                    "INSERT INTO memories"
                    " (id, subject_id, kind, predicate, object_value,"
                    "  object_type, confidence, sensitivity)"
                    " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
                    " ON CONFLICT (id) DO UPDATE SET"
                    "  subject_id=EXCLUDED.subject_id,"
                    "  kind=EXCLUDED.kind,"
                    "  predicate=EXCLUDED.predicate,"
                    "  object_value=EXCLUDED.object_value,"
                    "  object_type=EXCLUDED.object_type,"
                    "  confidence=EXCLUDED.confidence,"
                    "  sensitivity=EXCLUDED.sensitivity",
                    (
                        memory["id"],
                        memory["subject_id"],
                        str(memory["kind"]),
                        memory["predicate"],
                        json.dumps(memory["object"]["value"]),
                        memory["object"].get("type"),
                        float(memory["confidence"]),
                        str(memory["sensitivity"]),
                    ),
                )
                prov = memory.get("provenance", {})
                trace = prov.get("sanitization_trace")
                cur.execute(
                    "INSERT INTO provenance"
                    " (memory_id, source, extracted_at, raw_excerpt, imported,"
                    "  import_source, model, sanitization_trace)"
                    " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
                    " ON CONFLICT (memory_id) DO UPDATE SET"
                    "  source=EXCLUDED.source, extracted_at=EXCLUDED.extracted_at,"
                    "  raw_excerpt=EXCLUDED.raw_excerpt, imported=EXCLUDED.imported,"
                    "  import_source=EXCLUDED.import_source, model=EXCLUDED.model,"
                    "  sanitization_trace=EXCLUDED.sanitization_trace",
                    (
                        memory["id"],
                        prov.get("source", "manual"),
                        prov.get("extracted_at", ""),
                        prov.get("raw_excerpt"),
                        bool(prov.get("imported")),
                        prov.get("import_source"),
                        prov.get("model"),
                        json.dumps(trace) if trace else None,
                    ),
                )
                # FR-9.6 — audit references memory_id only, never raw text.
                cur.execute(
                    "INSERT INTO audit_log_entries"
                    " (actor, action, subject_id, details, outcome)"
                    " VALUES (%s, %s, %s, %s::jsonb, %s)",
                    (
                        actor,
                        "extract:done",
                        memory["subject_id"],
                        json.dumps({"memory_id": memory["id"]}),
                        "success",
                    ),
                )
            c.commit()
        except Exception:
            c.rollback()
            raise

    def list_memories(
        self,
        *,
        subject_id: str | None = None,
        kind: str | None = None,
        sensitivity: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        c = self._require_conn()
        q = (
            "SELECT m.*, p.source, p.extracted_at, p.raw_excerpt,"
            " p.imported, p.import_source, p.model"
            " FROM memories m LEFT JOIN provenance p ON p.memory_id = m.id"
            " WHERE TRUE"
        )
        params: list[Any] = []
        if subject_id is not None:
            q += " AND m.subject_id = %s"
            params.append(subject_id)
        if kind is not None:
            q += " AND m.kind = %s"
            params.append(kind)
        if sensitivity:
            q += " AND m.sensitivity = ANY(%s)"
            params.append(list(sensitivity))
        q += " ORDER BY m.created_at DESC"
        with c.cursor() as cur:
            cur.execute(q, params)
            rows = cur.fetchall()
        return [self._row_to_memory(r) for r in rows]

    def get_memory(self, memory_id: str) -> dict[str, Any] | None:
        c = self._require_conn()
        with c.cursor() as cur:
            cur.execute(
                "SELECT m.*, p.source, p.extracted_at, p.raw_excerpt,"
                " p.imported, p.import_source, p.model"
                " FROM memories m LEFT JOIN provenance p ON p.memory_id = m.id"
                " WHERE m.id = %s",
                (memory_id,),
            )
            row = cur.fetchone()
        return self._row_to_memory(row) if row else None

    @staticmethod
    def _row_to_memory(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "subject_id": row["subject_id"],
            "kind": row["kind"],
            "predicate": row["predicate"],
            "object": {"value": json.loads(row["object_value"]), "type": row["object_type"]},
            "confidence": float(row["confidence"]),
            "sensitivity": row["sensitivity"],
            "provenance": {
                "source": row.get("source") or "unknown",
                "extracted_at": row.get("extracted_at") or "",
                "raw_excerpt": row.get("raw_excerpt"),
                "imported": bool(row["imported"]) if row.get("imported") is not None else None,
                "import_source": row.get("import_source"),
                "model": row.get("model"),
            },
        }

    # ---- Contexts ---------------------------------------------------------
    def persist_ingest_context(
        self,
        ic: IngestContext,
        *,
        subject_id: str,
        actor: str = "system",
    ) -> str:
        c = self._require_conn()
        with c.cursor() as cur:
            cur.execute(
                "SELECT id FROM contexts WHERE subject_id = %s AND source_file_hash = %s "
                "AND vendor_conversation_id = %s",
                (subject_id, ic.source_file_hash, ic.vendor_conversation_id),
            )
            existing = cur.fetchone()
            if existing is not None:
                return str(existing["id"])

            cid = str(uuid.uuid4())
            try:
                cur.execute(
                    "INSERT INTO contexts (id, subject_id, source_vendor, source_file_hash,"
                    " vendor_conversation_id, title, captured_at)"
                    " VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (
                        cid,
                        subject_id,
                        ic.vendor,
                        ic.source_file_hash,
                        ic.vendor_conversation_id,
                        ic.title,
                        ic.captured_at,
                    ),
                )
                for m in ic.messages:
                    cur.execute(
                        "INSERT INTO raw_messages"
                        " (context_id, seq, role, content, created_at, vendor_message_id)"
                        " VALUES (%s, %s, %s, %s, %s, %s)",
                        (
                            cid,
                            m.seq,
                            str(m.role),
                            m.content,
                            m.created_at.isoformat() if m.created_at else None,
                            m.vendor_message_id,
                        ),
                    )
                cur.execute(
                    "INSERT INTO audit_log_entries"
                    " (actor, action, subject_id, details, outcome)"
                    " VALUES (%s, %s, %s, %s::jsonb, %s)",
                    (
                        actor,
                        "capture",
                        subject_id,
                        json.dumps(
                            {
                                "context_id": cid,
                                "vendor": ic.vendor,
                                "vendor_conversation_id": ic.vendor_conversation_id,
                                "messages": len(ic.messages),
                            }
                        ),
                        "success",
                    ),
                )
                c.commit()
            except Exception:
                c.rollback()
                raise
        return cid

    def get_context_by_unique(
        self,
        subject_id: str,
        source_file_hash: str,
        vendor_conversation_id: str,
    ) -> dict[str, Any] | None:
        c = self._require_conn()
        with c.cursor() as cur:
            cur.execute(
                "SELECT * FROM contexts WHERE subject_id = %s AND source_file_hash = %s "
                "AND vendor_conversation_id = %s",
                (subject_id, source_file_hash, vendor_conversation_id),
            )
            row = cur.fetchone()
        return dict(row) if row else None

    # ---- Audit ------------------------------------------------------------
    def audit_log(self, limit: int = 100) -> list[dict[str, Any]]:
        c = self._require_conn()
        with c.cursor() as cur:
            cur.execute(
                "SELECT * FROM audit_log_entries ORDER BY id DESC LIMIT %s",
                (limit,),
            )
            rows = cur.fetchall()
        return [dict(r) for r in rows]
