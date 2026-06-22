"""SQLite backend — single-user fallback per ADR-003."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from context_capital.ingest.types import IngestContext

SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS subjects (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK (type IN ('person','organization','agent')),
    display_name TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL REFERENCES subjects(id),
    kind TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object_value TEXT NOT NULL,
    object_type TEXT,
    confidence REAL NOT NULL,
    sensitivity TEXT NOT NULL CHECK (sensitivity IN ('public','work','personal','secret')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS memories_subject_kind_idx ON memories (subject_id, kind);
CREATE INDEX IF NOT EXISTS memories_subject_predicate_idx ON memories (subject_id, predicate);

CREATE TABLE IF NOT EXISTS provenance (
    memory_id TEXT PRIMARY KEY REFERENCES memories(id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    extracted_at TEXT NOT NULL,
    raw_excerpt TEXT,
    imported INTEGER NOT NULL DEFAULT 0,
    import_source TEXT,
    model TEXT,
    sanitization_trace TEXT
);

CREATE TABLE IF NOT EXISTS audit_log_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL DEFAULT (datetime('now')),
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    subject_id TEXT,
    details TEXT NOT NULL DEFAULT '{}',
    outcome TEXT NOT NULL CHECK (outcome IN ('success','denied','error'))
);

CREATE TABLE IF NOT EXISTS contexts (
    id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL REFERENCES subjects(id),
    source_vendor TEXT NOT NULL,
    source_file_hash TEXT NOT NULL,
    vendor_conversation_id TEXT NOT NULL,
    title TEXT,
    captured_at TEXT NOT NULL,
    UNIQUE (subject_id, source_file_hash, vendor_conversation_id)
);
CREATE INDEX IF NOT EXISTS contexts_subject_idx ON contexts (subject_id);

CREATE TABLE IF NOT EXISTS raw_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    context_id TEXT NOT NULL REFERENCES contexts(id) ON DELETE CASCADE,
    seq INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT,
    vendor_message_id TEXT,
    UNIQUE (context_id, seq)
);
CREATE INDEX IF NOT EXISTS raw_messages_context_idx ON raw_messages (context_id);
"""


class Store:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def __enter__(self) -> Store:
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def connect(self) -> None:
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(SCHEMA_DDL)
        self._conn.commit()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _require_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("Store is not connected — use as a context manager.")
        return self._conn

    def ensure_subject(
        self,
        subject_id: str,
        subject_type: str = "person",
        display_name: str | None = None,
    ) -> None:
        c = self._require_conn()
        c.execute(
            "INSERT OR IGNORE INTO subjects (id, type, display_name) VALUES (?, ?, ?)",
            (subject_id, subject_type, display_name),
        )
        c.commit()

    def add_memory(
        self, memory: dict[str, Any], *, actor: str = "system"
    ) -> None:
        c = self._require_conn()
        with c:
            c.execute(
                "INSERT OR REPLACE INTO memories"
                " (id, subject_id, kind, predicate, object_value,"
                " object_type, confidence, sensitivity)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    memory["id"],
                    memory["subject_id"],
                    str(memory["kind"]),
                    memory["predicate"],
                    json.dumps(memory["object"]["value"]),
                    memory["object"].get("type"),
                    memory["confidence"],
                    str(memory["sensitivity"]),
                ),
            )
            prov = memory.get("provenance", {})
            trace = prov.get("sanitization_trace")
            c.execute(
                "INSERT OR REPLACE INTO provenance"
                " (memory_id, source, extracted_at, raw_excerpt, imported,"
                " import_source, model, sanitization_trace)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    memory["id"],
                    prov.get("source", "manual"),
                    prov.get("extracted_at", ""),
                    prov.get("raw_excerpt"),
                    1 if prov.get("imported") else 0,
                    prov.get("import_source"),
                    prov.get("model"),
                    json.dumps(trace) if trace else None,
                ),
            )
            # Audit: memory_id only — never raw text (FR-9.6).
            c.execute(
                "INSERT INTO audit_log_entries"
                " (actor, action, subject_id, details, outcome)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    actor,
                    "extract:done",
                    memory["subject_id"],
                    json.dumps({"memory_id": memory["id"]}),
                    "success",
                ),
            )

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
            " FROM memories m LEFT JOIN provenance p ON"
            " p.memory_id = m.id WHERE 1=1"
        )
        params: list[Any] = []
        if subject_id is not None:
            q += " AND m.subject_id = ?"
            params.append(subject_id)
        if kind is not None:
            q += " AND m.kind = ?"
            params.append(kind)
        if sensitivity:
            placeholders = ",".join("?" * len(sensitivity))
            q += f" AND m.sensitivity IN ({placeholders})"
            params.extend(sensitivity)
        q += " ORDER BY m.created_at DESC"
        rows = c.execute(q, params).fetchall()
        return [self._row_to_memory(r) for r in rows]

    def get_memory(self, memory_id: str) -> dict[str, Any] | None:
        c = self._require_conn()
        row = c.execute(
            "SELECT m.*, p.source, p.extracted_at, p.raw_excerpt,"
            " p.imported, p.import_source, p.model"
            " FROM memories m LEFT JOIN provenance p ON p.memory_id = m.id"
            " WHERE m.id = ?",
            (memory_id,),
        ).fetchone()
        return self._row_to_memory(row) if row else None

    @staticmethod
    def _row_to_memory(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "subject_id": row["subject_id"],
            "kind": row["kind"],
            "predicate": row["predicate"],
            "object": {"value": json.loads(row["object_value"]), "type": row["object_type"]},
            "confidence": row["confidence"],
            "sensitivity": row["sensitivity"],
            "provenance": {
                "source": row["source"] or "unknown",
                "extracted_at": row["extracted_at"] or "",
                "raw_excerpt": row["raw_excerpt"],
                "imported": bool(row["imported"]) if row["imported"] is not None else None,
                "import_source": row["import_source"],
                "model": row["model"],
            },
        }

    def audit_log(self, limit: int = 100) -> list[dict[str, Any]]:
        c = self._require_conn()
        rows = c.execute(
            "SELECT * FROM audit_log_entries ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def persist_ingest_context(
        self,
        ic: IngestContext,
        *,
        subject_id: str,
        actor: str = "system",
    ) -> str:
        """Persist an IngestContext + its messages. Idempotent on
        (subject_id, source_file_hash, vendor_conversation_id). Returns the
        context UUID (existing one if duplicate).
        """
        import uuid as _uuid

        c = self._require_conn()
        existing = c.execute(
            "SELECT id FROM contexts WHERE subject_id = ? AND source_file_hash = ? "
            "AND vendor_conversation_id = ?",
            (subject_id, ic.source_file_hash, ic.vendor_conversation_id),
        ).fetchone()
        if existing is not None:
            return str(existing["id"])
        cid = str(_uuid.uuid4())
        with c:
            c.execute(
                """INSERT INTO contexts (id, subject_id, source_vendor, source_file_hash,
                                          vendor_conversation_id, title, captured_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    cid,
                    subject_id,
                    ic.vendor,
                    ic.source_file_hash,
                    ic.vendor_conversation_id,
                    ic.title,
                    ic.captured_at.isoformat(),
                ),
            )
            for m in ic.messages:
                c.execute(
                    """INSERT INTO raw_messages
                           (context_id, seq, role, content, created_at, vendor_message_id)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        cid,
                        m.seq,
                        str(m.role),
                        m.content,
                        m.created_at.isoformat() if m.created_at else None,
                        m.vendor_message_id,
                    ),
                )
            c.execute(
                "INSERT INTO audit_log_entries (actor, action, subject_id, details, outcome) "
                "VALUES (?, ?, ?, ?, ?)",
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
        return cid

    def get_context_by_unique(
        self,
        subject_id: str,
        source_file_hash: str,
        vendor_conversation_id: str,
    ) -> dict[str, Any] | None:
        c = self._require_conn()
        row = c.execute(
            "SELECT * FROM contexts WHERE subject_id = ? AND source_file_hash = ? "
            "AND vendor_conversation_id = ?",
            (subject_id, source_file_hash, vendor_conversation_id),
        ).fetchone()
        return dict(row) if row else None
