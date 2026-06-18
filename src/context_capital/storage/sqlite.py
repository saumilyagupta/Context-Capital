"""SQLite backend — single-user fallback per ADR-003."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import TracebackType
from typing import Any

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
