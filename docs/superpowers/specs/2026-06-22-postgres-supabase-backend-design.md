# Design Spec — Postgres / Supabase Backend + pgvector Embeddings

**Date:** 2026-06-22
**Status:** Approved by user (2026-06-22); plan-writing next
**Parent docs:** [`../../srs.md`](../../srs.md), [`../../sdd.md`](../../sdd.md), [`../../adr/003-storage.md`](../../adr/003-storage.md), [`../../adr/005-extraction-model.md`](../../adr/005-extraction-model.md)
**Builds on:** real capture pipeline (`2026-06-22-real-capture-pipeline-design.md`)
**Closes ADR-003 implementation gap; partially closes SRS NFR-PRF-3 (vector recall).**

---

## 0. Purpose

Implement ADR-003's primary backend (Postgres + pgvector) as a sibling to the existing SQLite store, with:

- A clean **`StoreBase` abstraction** so the rest of the code never branches on backend.
- A **`PostgresStore`** that mirrors `SQLiteStore`'s surface, with the addition of an embedding column populated automatically.
- A **`cc migrate`** CLI command to move an existing SQLite store into a fresh Postgres database.
- A **`cc memories search`** CLI command that does cosine-distance ANN over `vector_embeddings` (Postgres only).
- **Backend auto-selection** via `CC_DATABASE_URL` env var (Postgres URL → Postgres; else SQLite).

The Postgres backend is intentionally vanilla — it works against Supabase, self-hosted Postgres, RDS, anything with `pgvector` enabled. "Supabase" is a deployment target, not a code-level concept.

## 1. Goals and Non-Goals

### Goals
- Identical user-facing API across backends: `cc capture`, `cc list`, `cc export`, `cc import`, `cc serve`, `cc verify-audit` all work transparently on either.
- Automatic embedding generation in `PostgresStore.add_memory` using `litellm.embedding` (default model: `voyage/voyage-3`, dim 1024) — graceful degradation when the embedding API is unavailable.
- One-way `cc migrate --to postgres` that copies SQLite → Postgres idempotently.
- New `cc memories search "..."` semantic-search command available when Postgres is the backend.
- ≥80% coverage of new code; SQLite tests stay green by default; Postgres tests gated behind `CC_RUN_PG_TESTS=1` env var via `testcontainers`.

### Non-Goals (deferred)
- Postgres → SQLite reverse migration.
- Cross-machine sync (Supabase Realtime / replication).
- Supabase Auth multi-user (separate spec, Phase 3).
- Alembic migration tooling — first-connect DDL is sufficient.
- Sharding / partitioning of `memories` / `vector_embeddings`.
- Asynchronous DB access (`psycopg3` async); keep sync for parity with current SQLite code.
- Multiple embedding models simultaneously per store. One model per store; query embedding uses the model recorded with the row.

## 2. Scope (Locked)

Files added or modified. Nothing existing moves except `sqlite.py`'s exported class name (re-exported under the old name for backward compatibility).

```
src/context_capital/
├── config.py                        # NEW — resolve_database_url(), settings helpers
├── storage/
│   ├── __init__.py                  # MODIFIED — factory + re-export
│   ├── base.py                      # NEW — StoreBase (ABC)
│   ├── factory.py                   # NEW — Store(db_url=None) dispatcher
│   ├── sqlite.py                    # MODIFIED — rename Store→SQLiteStore, subclass StoreBase, leave alias
│   └── postgres.py                  # NEW — PostgresStore (psycopg3 + pgvector-python)
├── extract/
│   └── embed.py                     # NEW — litellm-fronted embedding helper
└── cli.py                           # MODIFIED — `cc migrate`, `cc memories search`

tests/
├── test_storage_factory.py          # NEW — URL dispatching tests
├── test_storage_postgres.py         # NEW — testcontainers, gated by CC_RUN_PG_TESTS
├── test_extract_embed.py            # NEW — mocked litellm.embedding
├── test_cli_migrate.py              # NEW — SQLite → testcontainers PG round-trip
└── test_cli_memories_search.py      # NEW — search via mocked embedding

docs/
└── data-model/schema.sql            # ALREADY CANONICAL — re-used verbatim for first-connect DDL
```

pyproject.toml dependency additions:

- `psycopg[binary]>=3.2` — sync Postgres driver
- `pgvector>=0.3` — pgvector Python adapter (registers `vector` type with psycopg3)
- (existing) `litellm` covers `litellm.embedding()` for the embedding pipeline

## 3. Architecture

```
                ┌─────────────────────────────────────────────────┐
                │  cc CLI (init / capture / list / export / …)    │
                └────────────────────┬────────────────────────────┘
                                     │ calls
                                     ▼
                ┌─────────────────────────────────────────────────┐
                │  Store(db_url=None)  ── factory ─────────────── │
                │     reads CC_DATABASE_URL / config.toml         │
                │     dispatches on URL prefix                    │
                └──────────┬──────────────────────────┬───────────┘
                           │                          │
                ┌──────────▼─────────┐    ┌───────────▼──────────────┐
                │   SQLiteStore       │    │   PostgresStore           │
                │   (existing logic)  │    │   (psycopg3 + pgvector)   │
                │   inherits StoreBase│    │   inherits StoreBase      │
                │   no embeddings     │    │   embeddings on every     │
                │   no semantic search│    │   add_memory (best-effort)│
                └─────────────────────┘    └───────────────────────────┘
                           ▲                          ▲
                           └──────── StoreBase (ABC) ──┘
```

The CLI and every other consumer (`extract/llm.py`, `mcp_server.py`, etc.) only see `StoreBase`. Existing call sites that name `Store` keep working because `Store` becomes the factory function.

## 4. Component Design

### 4.1 `storage/base.py` — `StoreBase` ABC

```python
from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from context_capital.ingest.types import IngestContext


class StoreBase(ABC):
    """Abstract storage interface. SQLiteStore and PostgresStore implement it."""

    # Lifecycle
    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    def __enter__(self) -> "StoreBase":
        self.connect()
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    # Subjects
    @abstractmethod
    def ensure_subject(self, subject_id: str, subject_type: str = "person",
                       display_name: str | None = None) -> None: ...

    # Memories
    @abstractmethod
    def add_memory(self, memory: dict[str, Any], *, actor: str = "system") -> None: ...

    @abstractmethod
    def list_memories(self, *, subject_id: str | None = None, kind: str | None = None,
                      sensitivity: list[str] | None = None) -> list[dict[str, Any]]: ...

    @abstractmethod
    def get_memory(self, memory_id: str) -> dict[str, Any] | None: ...

    # Contexts
    @abstractmethod
    def persist_ingest_context(self, ic: "IngestContext", *, subject_id: str,
                                actor: str = "system") -> str: ...

    @abstractmethod
    def get_context_by_unique(self, subject_id: str, source_file_hash: str,
                              vendor_conversation_id: str) -> dict[str, Any] | None: ...

    # Audit
    @abstractmethod
    def audit_log(self, limit: int = 100) -> list[dict[str, Any]]: ...

    # Embeddings + search — no-op / refused on SQLite; real on Postgres
    def supports_embeddings(self) -> bool:
        return False

    def add_embedding(self, memory_id: str, vector: list[float], *, model: str) -> None:
        """Default no-op. Postgres overrides."""

    def search_by_embedding(
        self, vector: list[float], *, limit: int = 10,
        subject_id: str | None = None, kind: str | None = None,
        sensitivity: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError(
            "semantic search requires the Postgres backend; "
            "set CC_DATABASE_URL=postgresql://..."
        )
```

### 4.2 `storage/sqlite.py` — `SQLiteStore` (existing code refactored)

```python
# (Existing Store class, renamed to SQLiteStore, inheriting StoreBase.)
# Behavior unchanged. supports_embeddings() returns False (default).
# Re-export `Store = SQLiteStore` at module level for any direct legacy imports.
class SQLiteStore(StoreBase):
    # ... existing body verbatim, plus `class SQLiteStore(StoreBase):` header ...
    pass


# Backward-compat alias for any code that imported `Store` directly from this module.
Store = SQLiteStore
```

### 4.3 `storage/postgres.py` — `PostgresStore`

```python
from __future__ import annotations
import json
import logging
import uuid
from typing import Any, TYPE_CHECKING

import psycopg
from psycopg.rows import dict_row
from pgvector.psycopg import register_vector

from context_capital.storage.base import StoreBase

if TYPE_CHECKING:
    from context_capital.ingest.types import IngestContext

logger = logging.getLogger(__name__)

# Canonical DDL — read from docs/data-model/schema.sql at import time and
# rendered into a Python string. (See note in §6 on how this is loaded.)
SCHEMA_DDL: str  # populated from packaged schema.sql


class PostgresStore(StoreBase):
    def __init__(self, dsn: str, *, embed_dim: int = 1024) -> None:
        self.dsn = dsn
        self.embed_dim = embed_dim
        self._conn: psycopg.Connection | None = None
        # Embedding service is injected so tests can substitute a mock.
        from context_capital.extract.embed import embed_text, DEFAULT_EMBED_MODEL
        self._embed = embed_text
        self._embed_model = DEFAULT_EMBED_MODEL

    def connect(self) -> None:
        self._conn = psycopg.connect(self.dsn, row_factory=dict_row)
        # Register pgvector adapter on this connection.
        register_vector(self._conn)
        # Idempotent DDL.
        with self._conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute(SCHEMA_DDL)
        self._conn.commit()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def supports_embeddings(self) -> bool:
        return True

    # ensure_subject / add_memory / list_memories / get_memory /
    # persist_ingest_context / get_context_by_unique / audit_log all mirror
    # SQLite logic but use psycopg parameter style (%s) and Postgres
    # types (jsonb, timestamptz, uuid, vector).

    def add_memory(self, memory: dict[str, Any], *, actor: str = "system") -> None:
        # 1. INSERT INTO memories ON CONFLICT DO NOTHING (same as SQLite REPLACE)
        # 2. INSERT INTO provenance
        # 3. Compute embedding (best-effort) and insert into vector_embeddings
        # 4. Audit-log entry (FR-9.6: memory_id only)
        ...  # full impl in writing-plans plan

    def add_embedding(self, memory_id: str, vector: list[float], *, model: str) -> None:
        # INSERT OR REPLACE into vector_embeddings (memory_id, model)
        ...

    def search_by_embedding(
        self, vector: list[float], *, limit: int = 10,
        subject_id: str | None = None, kind: str | None = None,
        sensitivity: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        # SELECT m.*, p.* FROM memories m
        # JOIN vector_embeddings v ON v.memory_id = m.id
        # JOIN provenance p ON p.memory_id = m.id
        # WHERE [filters]
        # ORDER BY v.embedding <=> %s::vector
        # LIMIT %s
        ...
```

### 4.4 `storage/factory.py` — `Store(db_url=None)` dispatcher

```python
from __future__ import annotations
from pathlib import Path

from context_capital.storage.base import StoreBase
from context_capital.config import resolve_database_url


def Store(db_url: str | Path | None = None) -> StoreBase:
    """Factory: returns SQLiteStore or PostgresStore based on URL.

    If `db_url` is None, reads CC_DATABASE_URL / config.toml / default.
    """
    resolved = db_url if db_url is not None else resolve_database_url()
    if isinstance(resolved, str) and resolved.startswith(("postgresql://", "postgres://")):
        from context_capital.storage.postgres import PostgresStore
        return PostgresStore(resolved)
    # Otherwise SQLite — accept Path or str path.
    from context_capital.storage.sqlite import SQLiteStore
    return SQLiteStore(Path(resolved))
```

### 4.5 `storage/__init__.py` (modified)

```python
from context_capital.storage.base import StoreBase
from context_capital.storage.factory import Store

__all__ = ["Store", "StoreBase"]
```

`Store` is now a function, not a class. Existing call sites like `with Store(path) as store:` still work because the function returns a context-manager-compatible object.

### 4.6 `config.py` — settings resolver

```python
from __future__ import annotations
import os
import tomllib
from pathlib import Path

DEFAULT_DATA_DIR = Path("~/.context-capital").expanduser()
DEFAULT_SQLITE_PATH = DEFAULT_DATA_DIR / "store.db"


def resolve_database_url() -> str | Path:
    """Returns either a Postgres URL string or a SQLite Path."""
    if url := os.environ.get("CC_DATABASE_URL"):
        return url
    cfg_path = DEFAULT_DATA_DIR / "config.toml"
    if cfg_path.exists():
        cfg = tomllib.loads(cfg_path.read_text())
        url = cfg.get("storage", {}).get("database_url")
        if url:
            return url
    return DEFAULT_SQLITE_PATH


def resolve_embed_model() -> str:
    return os.environ.get("CC_EMBED_MODEL", "voyage/voyage-3")
```

### 4.7 `extract/embed.py` — embedding helper

```python
from __future__ import annotations
import logging

import litellm

logger = logging.getLogger(__name__)

DEFAULT_EMBED_MODEL = "voyage/voyage-3"  # 1024 dim — matches schema.sql vector(1024)
EMBED_DIM = 1024


def embed_text(text: str, *, model: str = DEFAULT_EMBED_MODEL) -> list[float] | None:
    """Return the embedding vector for `text`, or None on failure (best-effort).

    Failure causes (network, no API key, rate limit, etc.) are logged at WARN
    and the function returns None. Caller decides whether to drop or fallback.
    """
    if not text or not text.strip():
        return None
    try:
        resp = litellm.embedding(model=model, input=[text])
        data = resp["data"]
        if not data:
            return None
        vec = data[0].get("embedding")
        if not isinstance(vec, list) or len(vec) != EMBED_DIM:
            logger.warning("embedding has unexpected shape (model=%s, len=%s)", model,
                           None if not isinstance(vec, list) else len(vec))
            return None
        return [float(x) for x in vec]
    except Exception as e:  # noqa: BLE001
        logger.warning("embed_text failed (model=%s): %s", model, e)
        return None


def memory_to_text(memory: dict) -> str:
    """Canonical string used to embed a memory.

    Concatenates predicate + object.value + a short excerpt of provenance.raw_excerpt.
    """
    obj = memory.get("object") or {}
    val = obj.get("value", "")
    excerpt = (memory.get("provenance") or {}).get("raw_excerpt", "") or ""
    return f"{memory.get('predicate', '')}: {val}\n{excerpt[:512]}"
```

### 4.8 `cc migrate` CLI command

```
cc migrate --to postgres [--source <sqlite-path>] [--target <postgres-url>] [--with-embeddings]
```

Flow:
1. If `--source` omitted, default to `~/.context-capital/store.db`.
2. If `--target` omitted, read `CC_DATABASE_URL`; if not set, fail with `BadParameter`.
3. Open `SQLiteStore(source)` and `PostgresStore(target)`. Refuse if `target` already has subjects from a different subject DID (safety check; can be bypassed with `--force`).
4. Stream rows table-by-table in FK-safe order: `subjects` → `contexts` → `raw_messages` → `memories` → `provenance` → `validity_periods` (skip if empty) → `audit_log_entries`.
5. Idempotent: every INSERT uses `ON CONFLICT DO NOTHING` keyed on PK. Re-running `cc migrate` resumes.
6. If `--with-embeddings`, compute embeddings for each migrated memory before insert. Best-effort per-row; failures logged, memory still migrated.
7. Final audit-log entry in the *target* recording the migration: `actor='cli:migrate'`, `action='migrate:done'`, `details={"source_subject_count": N, "memories_migrated": M, "embeddings_created": K}`.
8. Print summary to stdout.

```python
@app.command()
def migrate(
    to: str = typer.Option(..., "--to"),
    source: Path | None = typer.Option(None, "--source"),
    target: str | None = typer.Option(None, "--target"),
    with_embeddings: bool = typer.Option(False, "--with-embeddings/--no-embeddings"),
    force: bool = typer.Option(False, "--force"),
) -> None:
    if to != "postgres":
        raise typer.BadParameter("Only --to postgres is supported.")
    ...
```

### 4.9 `cc memories search` CLI command

```
cc memories search "query string" [--limit 10] [--kind preference,project] [--sensitivity work,public]
```

Implementation uses a nested typer app for `cc memories <subcommand>`:

```python
memories_app = typer.Typer(help="Memory-level operations.")
app.add_typer(memories_app, name="memories")


@memories_app.command("search")
def memories_search(
    query: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(10, "--limit", "-l"),
    kind: str | None = typer.Option(None, "--kind"),
    sensitivity: list[str] | None = typer.Option(None, "--sensitivity"),
) -> None:
    ...
```

Flow:
1. Open the store via the factory.
2. If `not store.supports_embeddings()`: print clear error, exit 2.
3. Embed the query string with the same model as `extract/embed.py` default.
4. Call `store.search_by_embedding(vec, limit=L, kind=kind, sensitivity=sensitivity)`.
5. Print results in the same format as `cc list`, ordered by similarity (closest first).

## 5. Data Flow

```mermaid
flowchart TD
    A[cc command] -->|Store factory| B{URL prefix?}
    B -- "postgresql://" --> C[PostgresStore]
    B -- "path or sqlite" --> D[SQLiteStore]
    C -->|add_memory| E[INSERT memories + provenance]
    C -->|embed via litellm| F[INSERT vector_embeddings]
    C -->|audit| G[INSERT audit_log_entries]
    D -->|add_memory| H[INSERT memories + provenance]
    D -->|audit| I[INSERT audit_log_entries]
    A2[cc memories search] -->|embed query| J[litellm.embedding]
    J -->|vector| K[PostgresStore.search_by_embedding]
    K -->|"ORDER BY embedding <=> %s"| L[Top-K memories]
```

## 6. Schema Reuse

The Postgres schema is already at `docs/data-model/schema.sql`. The `PostgresStore.connect()` method reads that file (packaged via `importlib.resources`) and executes it. The file is the single source of truth.

```python
# storage/postgres.py
from pathlib import Path

def _load_schema() -> str:
    # Search up from this file to find docs/data-model/schema.sql.
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "docs" / "data-model" / "schema.sql"
        if candidate.exists():
            return candidate.read_text()
    raise FileNotFoundError("could not locate docs/data-model/schema.sql")


SCHEMA_DDL = _load_schema()
```

(If the package is later installed without the `docs/` tree, this falls back to a packaged copy — handled in the implementation plan, not the spec.)

**Important:** SQLite has its own DDL string inside `sqlite.py`. The two are not auto-synchronized. If you change schema, you change *both*. A future conformance test ("SQLite ≡ Postgres column set") is on the carry-forward list.

## 7. Backend Selection Examples

```bash
# Default — SQLite (no env var)
cc capture --vendor chatgpt --file conv.json   # writes to ~/.context-capital/store.db

# Postgres / Supabase via env var
export CC_DATABASE_URL=postgresql://user:pass@db.xyz.supabase.co:5432/postgres
cc capture --vendor chatgpt --file conv.json   # writes to Supabase

# Config file (~/.context-capital/config.toml)
# [storage]
# database_url = "postgresql://..."
```

The CLI never asks "which backend?" — it just uses whatever resolves.

## 8. Failure Modes

| Failure | Behavior | Recovery |
|---|---|---|
| `psycopg.OperationalError` (can't connect) | Wrap with structured error; print masked DSN + suggest checking creds | User fixes URL / network |
| `pgvector` extension missing | SQL error caught; rewrap with "Run `CREATE EXTENSION vector;` (Supabase has it by default)" | User enables extension |
| Embedding API down | `embed_text` returns `None`; memory persisted without embedding; warn logged | Re-embed via `cc migrate --with-embeddings` later |
| Embedding dim mismatch (e.g., user switched to `text-embedding-3-small` mid-store) | Hard error on insert with explicit message naming both dims | User picks one model and either stays or wipes |
| Migration partial failure | Idempotent — re-run resumes from `ON CONFLICT DO NOTHING` | User re-runs `cc migrate` |
| Search on SQLite backend | `NotImplementedError` from `search_by_embedding`; CLI catches and prints clean message + exit 2 | User sets `CC_DATABASE_URL` to Postgres |
| Long-running embedding API call | `litellm`'s default timeout applies; per-call failure is per-memory; bulk migration continues | none |
| Postgres `ON CONFLICT` constraint violation other than PK (shouldn't happen) | Re-raise — explicit failure better than silent corruption | none |

## 9. Tests

| File | What it tests | When it runs |
|---|---|---|
| `test_storage_factory.py` | URL dispatching: `postgresql://` → PostgresStore mock, `Path` → SQLiteStore, env var fallback, config.toml fallback | Always |
| `test_storage_postgres.py` | Round-trip CRUD on real Postgres via testcontainers (`pgvector/pgvector:pg16`) | Only when `CC_RUN_PG_TESTS=1` is set |
| `test_extract_embed.py` | Mocked `litellm.embedding`; default model name; failure returns None; dim mismatch returns None; `memory_to_text` shape | Always |
| `test_cli_migrate.py` | SQLite seeded → migrated → both stores compared row counts; idempotency on re-run; `--with-embeddings` mocked | Postgres parts gated; CLI-wiring parts always |
| `test_cli_memories_search.py` | Mocked store with `supports_embeddings=True` and stubbed `search_by_embedding`; assert filter passthrough; SQLite path prints error and exits 2 | Always |
| Existing `test_storage*.py` | Unchanged — still pass against `SQLiteStore` (the rename is transparent due to the `Store = SQLiteStore` alias) | Always |

CI runs the always-on tests. A nightly job (or manual `CC_RUN_PG_TESTS=1 pytest`) runs the Postgres-gated tests.

## 10. Definition of Done

- [ ] `cc capture --vendor chatgpt --file …` writes to Postgres when `CC_DATABASE_URL=postgresql://…` is set.
- [ ] Every memory written via Postgres has a row in `vector_embeddings` (or an explicit log line if the embedding API failed).
- [ ] `cc memories search "ML preferences"` returns top-K memories sorted by cosine similarity, with `--kind` and `--sensitivity` filters honored.
- [ ] `cc migrate --to postgres` copies a SQLite store into a fresh Postgres database with row-count parity (verified by a test).
- [ ] `cc migrate --to postgres` is idempotent on re-run (no duplicate rows).
- [ ] SQLite path still works identically when `CC_DATABASE_URL` is unset.
- [ ] `pytest -q` (without `CC_RUN_PG_TESTS`) stays green at the existing 96 + new always-on tests.
- [ ] `CC_RUN_PG_TESTS=1 pytest` passes the gated tests against testcontainers.
- [ ] `ruff check` and `mypy --strict` clean for `src/context_capital/storage`, `src/context_capital/config.py`, `src/context_capital/extract/embed.py`.
- [ ] README quickstart shows both the SQLite default and the Postgres/Supabase env-var form.

## 11. Out of Scope

| Item | Why deferred |
|---|---|
| Postgres → SQLite reverse migration | Single-direction migration covers the "upgrade local to managed" path; reverse is rare |
| Supabase Auth / multi-user | Phase 3; would change the entire identity model |
| Supabase Realtime push for memory changes | Out of local-first scope; future sync spec |
| Multi-model embedding columns (multiple rows per memory, different models) | Schema supports it (PK is `(memory_id, model)`); the *write* path picks one model per store and stops. Querying with a different model is a future feature. |
| Alembic / formal migrations | First-connect IF-NOT-EXISTS DDL is sufficient through v0.x |
| Async / asyncpg | Sync code matches existing patterns; async is a separate refactor |
| Sharding, partitioning, read replicas | Way past Phase 2 |

## 12. Open Questions

1. **Embedding model dimension.** Default is `voyage/voyage-3` (1024) to match `schema.sql`. If a user sets `CC_EMBED_MODEL=text-embedding-3-small` (1536), the existing schema's `vector(1024)` column rejects it. **Resolution shipped in this plan:** hard-fail with an explicit message on first insert; document `CC_EMBED_DIM` env override + matching ALTER TABLE in `ops/runbook.md`. Multi-dim support is a future spec.
2. **Supabase connection pooler vs direct.** Supabase exposes both `db.xyz.supabase.co:5432` (direct) and `*.pooler.supabase.com:6543` (PgBouncer). Either works; PgBouncer in *transaction mode* is not compatible with prepared statements that `psycopg3` uses by default — we'll document this and recommend session mode or direct.
3. **Audit log volume on Postgres.** With cross-machine usage potential, `audit_log_entries` grows fast. Phase 2.5 may need partitioning by `at` (timestamp) — not addressed here.
4. **Connection lifetime.** Currently we open a new connection per `with Store() as s:` block. For high-volume MCP servers, a connection pool would be desirable. Adding `psycopg.ConnectionPool` is deferred until profiling shows it matters.

## 13. References

- `docs/adr/003-storage.md` — locks Postgres+pgvector as primary, SQLite as fallback
- `docs/adr/005-extraction-model.md` — extraction model + embedding model decisions
- `docs/data-model.md` + `docs/data-model/schema.sql` — canonical schema
- `docs/sdd.md` §2.5 — storage layer design
- `docs/srs.md` §F-4, §NFR-PRF-3 — storage requirements
- Existing `src/context_capital/storage/sqlite.py` — the surface that `StoreBase` abstracts over
- Supabase docs on pgvector: https://supabase.com/docs/guides/database/extensions/pgvector
- pgvector-python: https://github.com/pgvector/pgvector-python
- psycopg 3 docs: https://www.psycopg.org/psycopg3/

## 14. Estimated Cost

| Phase | Cost |
|---|---|
| Spec self-review (inline) | small |
| Plan writing (writing-plans skill) | $8–12 |
| Implementation execution (subagent-driven, ~10–12 tasks) | $80–130 |
| Per-task reviews | $20–35 |
| Buffer for fixes (Postgres surfaces; testcontainers can be finicky) | $20–30 |
| **Total** | **~$130–210** |

If embedding-pipeline tests need iteration on `litellm` `voyage/voyage-3` request shape, expect the upper end. Plan accounts for that with mocked tests as the default and a single gated live-API smoke test in the optional nightly job.
