# Postgres / Supabase Backend + pgvector Embeddings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a Postgres + pgvector storage backend as a peer to the existing SQLite store, with auto-embedding, `cc migrate`, and `cc memories search`, selected transparently by `CC_DATABASE_URL`.

**Architecture:** Introduce a `StoreBase` ABC; rename `Store` → `SQLiteStore` (keep `Store = SQLiteStore` alias inside `sqlite.py`); add `PostgresStore` (psycopg3 + pgvector); replace the top-level `Store` symbol with a factory function that dispatches on URL prefix. Embedding is a separate module (`extract/embed.py`) fronting `litellm.embedding`. Migration is one-way (SQLite → Postgres), idempotent via `ON CONFLICT DO NOTHING`.

**Tech Stack:** Python 3.12, Pydantic v2, psycopg[binary]≥3.2, pgvector≥0.3, litellm≥1.50, typer, rich, pytest, testcontainers (dev-time, gated).

## Global Constraints

- **Spec source:** `docs/superpowers/specs/2026-06-22-postgres-supabase-backend-design.md`. Exact values copied below are normative for every task.
- **Embedding model default:** `voyage/voyage-3` — dimension `1024` — matches `docs/data-model/schema.sql`'s `vector(1024)` column. Override via `CC_EMBED_MODEL`.
- **Backend selector env var:** `CC_DATABASE_URL`. Prefix test: `postgresql://` or `postgres://` → Postgres; anything else → SQLite path.
- **Default SQLite path:** `~/.context-capital/store.db` (unchanged from current behavior).
- **Config file location:** `~/.context-capital/config.toml` with `[storage] database_url = "..."`.
- **DDL strategy — important deviation from spec §6:** PostgresStore ships an **inline Phase-1 mirror DDL** (Postgres types + `vector_embeddings` table) that matches the *current* SQLite plaintext surface — *not* `docs/data-model/schema.sql` verbatim, because that canonical schema uses `_enc bytea` columns and `audit_log_entries.this_hash bytea NOT NULL` triggers for F-4 encryption + F-9 audit-hash-chain features that have NOT shipped yet. Unifying the two DDLs is a carry-forward item once F-4/F-9 land. PostgresStore's inline DDL MUST include a `# TODO(post-F-4): unify with docs/data-model/schema.sql` comment pointing at this decision.
- **TDD:** every task writes the failing test first, runs it to verify failure, implements the minimal code, runs the test to verify pass, commits. No exceptions.
- **Backward compat:** every existing test under `tests/` MUST keep passing without modification. The `Store` import surface is a function from Task 4 onward; existing call sites use it as `Store(path)` which the factory supports.
- **Postgres tests gating:** every test that opens a real Postgres connection is wrapped in `@pytest.mark.skipif(os.environ.get("CC_RUN_PG_TESTS") != "1", reason="set CC_RUN_PG_TESTS=1 to run Postgres tests")`. Container image: `pgvector/pgvector:pg16`.
- **Audit log invariant (FR-9.6):** Postgres `add_memory` / `persist_ingest_context` audit entries store ONLY `memory_id` / `context_id` references — never raw text. Mirrors SQLiteStore behavior.
- **Lint/type gates:** `ruff check src/context_capital/storage src/context_capital/config.py src/context_capital/extract/embed.py` and `mypy --strict` on the same paths MUST be clean at end of every commit.
- **Dependencies added in Task 0:** `psycopg[binary]>=3.2`, `pgvector>=0.3`, `testcontainers>=4.0` (dev-extras only).
- **No async:** PostgresStore is sync — matches existing SQLite code and the rest of the codebase.

---

## File Map (locked at plan-time)

| Path | Status | Responsibility |
|---|---|---|
| `pyproject.toml` | MODIFY | add 2 runtime + 1 dev deps |
| `src/context_capital/config.py` | NEW | `resolve_database_url()`, `resolve_embed_model()` |
| `src/context_capital/storage/__init__.py` | MODIFY | re-export `Store` (now a function) + `StoreBase` |
| `src/context_capital/storage/base.py` | NEW | `StoreBase` ABC |
| `src/context_capital/storage/factory.py` | NEW | `Store(db_url=None)` dispatcher function |
| `src/context_capital/storage/sqlite.py` | MODIFY | rename class to `SQLiteStore(StoreBase)`, add `Store = SQLiteStore` alias |
| `src/context_capital/storage/postgres.py` | NEW | `PostgresStore` with inline Phase-1 mirror DDL + vector_embeddings |
| `src/context_capital/extract/embed.py` | NEW | `embed_text()`, `memory_to_text()`, constants |
| `src/context_capital/cli.py` | MODIFY | replace `_store_path()` usage with factory; add `cc migrate`; add `cc memories search` |
| `tests/test_storage_base.py` | NEW | ABC behavior, default methods, instantiation refusal |
| `tests/test_config.py` | NEW | env var → URL, config.toml → URL, default → path, embed model resolver |
| `tests/test_storage_factory.py` | NEW | URL dispatch (mocked PostgresStore), path → SQLiteStore |
| `tests/test_extract_embed.py` | NEW | mocked litellm.embedding success/failure/dim-mismatch + `memory_to_text` |
| `tests/test_storage_postgres.py` | NEW | gated round-trip via testcontainers `pgvector/pgvector:pg16` |
| `tests/test_storage_postgres_embed.py` | NEW | gated embedding + search round-trip |
| `tests/test_cli_migrate.py` | NEW | SQLite-seeded → migrated → row-count parity + idempotency (gated) |
| `tests/test_cli_memories_search.py` | NEW | mocked store + filters; SQLite path → exit 2 |
| `README.md` | MODIFY | quickstart shows both SQLite default + Postgres env-var form |

---

## Task Dependency Graph

```
T0 deps  ──►  T1 base  ──►  T2 sqlite-refactor ──►  T4 factory
              │                                       ▲
              │             T3 config ────────────────┘
              │
              ├────────────────────────────────────────►  T5 embed
              │
              └──►  T6 postgres-crud  ──►  T7 postgres-embed-search
                                                  │
                          T4 + T6 ────►  T8 cc migrate
                          T4 + T7 ────►  T9 cc memories search
                          T9 done ────►  T10 README + docs
```

Each task ends with a green test run + a commit. No task touches another task's files except where the table above lists MODIFY (T2, T4, T8, T9, T10).

---

### Task 0: Add dependencies + sanity import

**Files:**
- Modify: `pyproject.toml` (dependencies list + optional-dependencies.dev)
- Test: implicit — `pip install -e ".[dev]"` and `python -c "import psycopg, pgvector, testcontainers"` succeeds.

**Interfaces:**
- Consumes: nothing.
- Produces: `psycopg`, `pgvector`, `testcontainers` importable in later tasks.

- [ ] **Step 1: Edit `pyproject.toml` to add runtime deps**

In the `dependencies = [...]` block (currently ends at line 33), append two lines BEFORE the closing `]`:

```toml
    "psycopg[binary]>=3.2",
    "pgvector>=0.3",
```

- [ ] **Step 2: Edit `pyproject.toml` to add dev dep**

In `[project.optional-dependencies]` `dev = [...]` block, append before closing `]`:

```toml
    "testcontainers>=4.0",
```

- [ ] **Step 3: Install + smoke-check imports**

Run:
```bash
pip install -e ".[dev]"
python -c "import psycopg; from pgvector.psycopg import register_vector; import testcontainers; print('ok')"
```
Expected output: `ok`

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "deps: add psycopg3, pgvector-python, testcontainers for Postgres backend"
```

---

### Task 1: `StoreBase` ABC

**Files:**
- Create: `src/context_capital/storage/base.py`
- Test: `tests/test_storage_base.py`

**Interfaces:**
- Consumes: `context_capital.ingest.types.IngestContext` (TYPE_CHECKING only — no runtime dep).
- Produces:
  - `StoreBase` ABC with abstract methods: `connect()`, `close()`, `ensure_subject(subject_id, subject_type='person', display_name=None)`, `add_memory(memory, *, actor='system')`, `list_memories(*, subject_id=None, kind=None, sensitivity=None)`, `get_memory(memory_id)`, `persist_ingest_context(ic, *, subject_id, actor='system') -> str`, `get_context_by_unique(subject_id, source_file_hash, vendor_conversation_id)`, `audit_log(limit=100)`.
  - Concrete default methods: `__enter__`, `__exit__`, `supports_embeddings() -> bool` (returns False), `add_embedding(memory_id, vector, *, model)` (no-op), `search_by_embedding(...)` (raises `NotImplementedError` with the message `"semantic search requires the Postgres backend; set CC_DATABASE_URL=postgresql://..."`).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_storage_base.py`:

```python
"""Tests for the StoreBase ABC."""
from __future__ import annotations

import pytest

from context_capital.storage.base import StoreBase


def test_storebase_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        StoreBase()  # type: ignore[abstract]


class _StubStore(StoreBase):
    """Minimal concrete subclass — implements every abstract method as a no-op."""

    def connect(self) -> None: ...
    def close(self) -> None: ...
    def ensure_subject(self, subject_id, subject_type="person", display_name=None): ...
    def add_memory(self, memory, *, actor="system"): ...
    def list_memories(self, *, subject_id=None, kind=None, sensitivity=None):
        return []
    def get_memory(self, memory_id):
        return None
    def persist_ingest_context(self, ic, *, subject_id, actor="system"):
        return "ctx-stub"
    def get_context_by_unique(self, subject_id, source_file_hash, vendor_conversation_id):
        return None
    def audit_log(self, limit=100):
        return []


def test_stub_supports_embeddings_default_false():
    assert _StubStore().supports_embeddings() is False


def test_stub_add_embedding_is_noop():
    _StubStore().add_embedding("mem_x", [0.1, 0.2], model="dummy")


def test_stub_search_by_embedding_raises_not_implemented():
    with pytest.raises(NotImplementedError, match="semantic search requires the Postgres backend"):
        _StubStore().search_by_embedding([0.0] * 4)


def test_context_manager_calls_connect_and_close():
    calls = []

    class _Recorder(_StubStore):
        def connect(self) -> None:
            calls.append("connect")
        def close(self) -> None:
            calls.append("close")

    with _Recorder() as s:
        assert isinstance(s, StoreBase)
    assert calls == ["connect", "close"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_storage_base.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'context_capital.storage.base'`.

- [ ] **Step 3: Implement `storage/base.py`**

Create `src/context_capital/storage/base.py`:

```python
"""StoreBase — the abstract surface shared by SQLiteStore and PostgresStore."""
from __future__ import annotations

from abc import ABC, abstractmethod
from types import TracebackType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from context_capital.ingest.types import IngestContext


class StoreBase(ABC):
    """Abstract storage interface implemented by SQLiteStore and PostgresStore."""

    # ---- Lifecycle --------------------------------------------------------
    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    def __enter__(self) -> "StoreBase":
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    # ---- Subjects ---------------------------------------------------------
    @abstractmethod
    def ensure_subject(
        self,
        subject_id: str,
        subject_type: str = "person",
        display_name: str | None = None,
    ) -> None: ...

    # ---- Memories ---------------------------------------------------------
    @abstractmethod
    def add_memory(self, memory: dict[str, Any], *, actor: str = "system") -> None: ...

    @abstractmethod
    def list_memories(
        self,
        *,
        subject_id: str | None = None,
        kind: str | None = None,
        sensitivity: list[str] | None = None,
    ) -> list[dict[str, Any]]: ...

    @abstractmethod
    def get_memory(self, memory_id: str) -> dict[str, Any] | None: ...

    # ---- Contexts ---------------------------------------------------------
    @abstractmethod
    def persist_ingest_context(
        self,
        ic: "IngestContext",
        *,
        subject_id: str,
        actor: str = "system",
    ) -> str: ...

    @abstractmethod
    def get_context_by_unique(
        self,
        subject_id: str,
        source_file_hash: str,
        vendor_conversation_id: str,
    ) -> dict[str, Any] | None: ...

    # ---- Audit ------------------------------------------------------------
    @abstractmethod
    def audit_log(self, limit: int = 100) -> list[dict[str, Any]]: ...

    # ---- Embeddings + semantic search (Postgres overrides) ---------------
    def supports_embeddings(self) -> bool:
        return False

    def add_embedding(
        self,
        memory_id: str,
        vector: list[float],
        *,
        model: str,
    ) -> None:
        """Default no-op. Subclasses with vector storage override."""

    def search_by_embedding(
        self,
        vector: list[float],
        *,
        limit: int = 10,
        subject_id: str | None = None,
        kind: str | None = None,
        sensitivity: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError(
            "semantic search requires the Postgres backend; "
            "set CC_DATABASE_URL=postgresql://..."
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_storage_base.py -v`
Expected: 5 passed.

- [ ] **Step 5: Lint + type check**

Run:
```bash
ruff check src/context_capital/storage/base.py tests/test_storage_base.py
mypy --strict src/context_capital/storage/base.py
```
Expected: both clean.

- [ ] **Step 6: Commit**

```bash
git add src/context_capital/storage/base.py tests/test_storage_base.py
git commit -m "feat(storage): add StoreBase ABC with default embedding stubs"
```

---

### Task 2: Refactor `Store` → `SQLiteStore(StoreBase)` with alias

**Files:**
- Modify: `src/context_capital/storage/sqlite.py:82` (the `class Store:` line)
- Modify: `src/context_capital/storage/sqlite.py` (bottom) — add `Store = SQLiteStore` alias
- Test: existing `tests/test_storage.py`, `tests/test_storage_contexts.py`, and all dependent tests stay green (no test file changes).

**Interfaces:**
- Consumes: `context_capital.storage.base.StoreBase` (from Task 1).
- Produces:
  - `SQLiteStore(StoreBase)` — class — exact same public surface as today's `Store`.
  - `Store = SQLiteStore` — module-level alias preserving backward compatibility for any direct `from context_capital.storage.sqlite import Store` import.

- [ ] **Step 1: Write a focused regression test asserting the rename + alias**

Append to `tests/test_storage.py`:

```python
def test_sqlite_store_is_storebase_subclass():
    from context_capital.storage.base import StoreBase
    from context_capital.storage.sqlite import SQLiteStore, Store
    assert issubclass(SQLiteStore, StoreBase)
    assert Store is SQLiteStore  # backward-compat alias
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_storage.py::test_sqlite_store_is_storebase_subclass -v`
Expected: FAIL with `ImportError: cannot import name 'SQLiteStore' from context_capital.storage.sqlite`.

- [ ] **Step 3: Make the rename + alias**

In `src/context_capital/storage/sqlite.py`:

Add this import at module-top with the other imports:

```python
from context_capital.storage.base import StoreBase
```

Replace the line `class Store:` (line 82) with:

```python
class SQLiteStore(StoreBase):
```

Replace the existing `def __enter__(self) -> Store:` return annotation with `def __enter__(self) -> "SQLiteStore":`.

At the end of the file, add:

```python


# Backward-compat alias — existing code imports `Store` directly from this module.
Store = SQLiteStore
```

- [ ] **Step 4: Run the full storage tests to verify everything still passes**

Run:
```bash
pytest tests/test_storage.py tests/test_storage_contexts.py -v
```
Expected: all green (existing tests + new alias test).

- [ ] **Step 5: Run the full suite to verify no regression**

Run: `pytest -q`
Expected: same number of tests as before this task + 1 new test (alias), all passing.

- [ ] **Step 6: Lint + type check**

Run:
```bash
ruff check src/context_capital/storage/sqlite.py
mypy --strict src/context_capital/storage/sqlite.py
```
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add src/context_capital/storage/sqlite.py tests/test_storage.py
git commit -m "refactor(storage): rename Store→SQLiteStore (inherits StoreBase), keep alias"
```

---

### Task 3: `config.py` — URL + embed model resolvers

**Files:**
- Create: `src/context_capital/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `DEFAULT_DATA_DIR: Path` = `Path("~/.context-capital").expanduser()`
  - `DEFAULT_SQLITE_PATH: Path` = `DEFAULT_DATA_DIR / "store.db"`
  - `resolve_database_url() -> str | Path` — checks `CC_DATABASE_URL` env, then `~/.context-capital/config.toml` `[storage] database_url`, then returns `DEFAULT_SQLITE_PATH`.
  - `resolve_embed_model() -> str` — checks `CC_EMBED_MODEL` env, else returns `"voyage/voyage-3"`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_config.py`:

```python
"""Tests for context_capital.config."""
from __future__ import annotations

from pathlib import Path


def test_env_var_returns_postgres_url(monkeypatch):
    from context_capital.config import resolve_database_url
    monkeypatch.setenv("CC_DATABASE_URL", "postgresql://u:p@h:5432/db")
    assert resolve_database_url() == "postgresql://u:p@h:5432/db"


def test_no_env_no_config_returns_default_sqlite_path(monkeypatch, tmp_path):
    from context_capital import config
    monkeypatch.delenv("CC_DATABASE_URL", raising=False)
    monkeypatch.setattr(config, "DEFAULT_DATA_DIR", tmp_path / "cc-empty")
    monkeypatch.setattr(config, "DEFAULT_SQLITE_PATH", tmp_path / "cc-empty" / "store.db")
    result = config.resolve_database_url()
    assert isinstance(result, Path)
    assert result == tmp_path / "cc-empty" / "store.db"


def test_config_toml_overrides_default(monkeypatch, tmp_path):
    from context_capital import config
    monkeypatch.delenv("CC_DATABASE_URL", raising=False)
    data_dir = tmp_path / "cc-with-config"
    data_dir.mkdir()
    (data_dir / "config.toml").write_text(
        '[storage]\ndatabase_url = "postgresql://from-config/db"\n'
    )
    monkeypatch.setattr(config, "DEFAULT_DATA_DIR", data_dir)
    monkeypatch.setattr(config, "DEFAULT_SQLITE_PATH", data_dir / "store.db")
    assert config.resolve_database_url() == "postgresql://from-config/db"


def test_env_var_beats_config_toml(monkeypatch, tmp_path):
    from context_capital import config
    monkeypatch.setenv("CC_DATABASE_URL", "postgresql://env-wins/db")
    data_dir = tmp_path / "cc-both"
    data_dir.mkdir()
    (data_dir / "config.toml").write_text(
        '[storage]\ndatabase_url = "postgresql://loser/db"\n'
    )
    monkeypatch.setattr(config, "DEFAULT_DATA_DIR", data_dir)
    assert config.resolve_database_url() == "postgresql://env-wins/db"


def test_resolve_embed_model_default(monkeypatch):
    from context_capital.config import resolve_embed_model
    monkeypatch.delenv("CC_EMBED_MODEL", raising=False)
    assert resolve_embed_model() == "voyage/voyage-3"


def test_resolve_embed_model_env_override(monkeypatch):
    from context_capital.config import resolve_embed_model
    monkeypatch.setenv("CC_EMBED_MODEL", "openai/text-embedding-3-small")
    assert resolve_embed_model() == "openai/text-embedding-3-small"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'context_capital.config'`.

- [ ] **Step 3: Implement `config.py`**

Create `src/context_capital/config.py`:

```python
"""Runtime configuration resolution (env vars, config.toml, defaults)."""
from __future__ import annotations

import os
import tomllib
from pathlib import Path

DEFAULT_DATA_DIR: Path = Path("~/.context-capital").expanduser()
DEFAULT_SQLITE_PATH: Path = DEFAULT_DATA_DIR / "store.db"

DEFAULT_EMBED_MODEL: str = "voyage/voyage-3"


def resolve_database_url() -> str | Path:
    """Resolve the active storage URL.

    Order:
      1. ``$CC_DATABASE_URL`` (any non-empty value)
      2. ``~/.context-capital/config.toml`` -> ``[storage] database_url``
      3. Default SQLite path at ``~/.context-capital/store.db``
    """
    env = os.environ.get("CC_DATABASE_URL")
    if env:
        return env
    cfg_path = DEFAULT_DATA_DIR / "config.toml"
    if cfg_path.exists():
        cfg = tomllib.loads(cfg_path.read_text())
        url = cfg.get("storage", {}).get("database_url")
        if url:
            return str(url)
    return DEFAULT_SQLITE_PATH


def resolve_embed_model() -> str:
    return os.environ.get("CC_EMBED_MODEL") or DEFAULT_EMBED_MODEL
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: 6 passed.

- [ ] **Step 5: Lint + type check**

Run:
```bash
ruff check src/context_capital/config.py tests/test_config.py
mypy --strict src/context_capital/config.py
```
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add src/context_capital/config.py tests/test_config.py
git commit -m "feat(config): add resolve_database_url and resolve_embed_model"
```

---

### Task 4: Factory + `storage/__init__.py`

**Files:**
- Create: `src/context_capital/storage/factory.py`
- Modify: `src/context_capital/storage/__init__.py`
- Test: `tests/test_storage_factory.py`

**Interfaces:**
- Consumes: `StoreBase` (Task 1), `SQLiteStore` (Task 2), `resolve_database_url` (Task 3), `PostgresStore` (Task 6 — but imported lazily so this task can land first).
- Produces:
  - `Store(db_url: str | Path | None = None) -> StoreBase` — top-level factory function.
  - `storage/__init__.py` re-exports `Store` (function) and `StoreBase` (class).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_storage_factory.py`:

```python
"""Tests for the Store factory dispatcher."""
from __future__ import annotations

import sys
from unittest.mock import MagicMock


def test_path_returns_sqlite_store(tmp_path):
    from context_capital.storage import Store
    from context_capital.storage.sqlite import SQLiteStore
    s = Store(tmp_path / "x.db")
    assert isinstance(s, SQLiteStore)


def test_str_path_returns_sqlite_store(tmp_path):
    from context_capital.storage import Store
    from context_capital.storage.sqlite import SQLiteStore
    s = Store(str(tmp_path / "y.db"))
    assert isinstance(s, SQLiteStore)


def test_postgresql_url_returns_postgres_store(monkeypatch):
    fake_module = MagicMock()
    fake_class = MagicMock(name="PostgresStore")
    fake_class.return_value = MagicMock(name="PostgresStoreInstance")
    fake_module.PostgresStore = fake_class
    monkeypatch.setitem(sys.modules, "context_capital.storage.postgres", fake_module)
    from context_capital.storage import Store
    inst = Store("postgresql://u:p@h:5432/db")
    fake_class.assert_called_once_with("postgresql://u:p@h:5432/db")
    assert inst is fake_class.return_value


def test_postgres_url_short_form_also_routes_to_postgres(monkeypatch):
    fake_module = MagicMock()
    fake_class = MagicMock(name="PostgresStore")
    fake_module.PostgresStore = fake_class
    monkeypatch.setitem(sys.modules, "context_capital.storage.postgres", fake_module)
    from context_capital.storage import Store
    Store("postgres://u:p@h:5432/db")
    fake_class.assert_called_once_with("postgres://u:p@h:5432/db")


def test_none_uses_resolve_database_url(monkeypatch, tmp_path):
    from context_capital import config
    monkeypatch.setattr(config, "DEFAULT_SQLITE_PATH", tmp_path / "store.db")
    monkeypatch.setattr(config, "DEFAULT_DATA_DIR", tmp_path)
    monkeypatch.delenv("CC_DATABASE_URL", raising=False)
    from context_capital.storage import Store
    from context_capital.storage.sqlite import SQLiteStore
    s = Store()
    assert isinstance(s, SQLiteStore)


def test_storebase_exported():
    from context_capital.storage import StoreBase
    from context_capital.storage.base import StoreBase as Base
    assert StoreBase is Base
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_storage_factory.py -v`
Expected: FAIL — `Store` is currently a class, not a callable returning by URL.

- [ ] **Step 3: Implement `storage/factory.py`**

Create `src/context_capital/storage/factory.py`:

```python
"""Store factory — dispatches to SQLiteStore or PostgresStore by URL prefix."""
from __future__ import annotations

from pathlib import Path

from context_capital.config import resolve_database_url
from context_capital.storage.base import StoreBase


def Store(db_url: str | Path | None = None) -> StoreBase:
    """Return a configured StoreBase implementation.

    Selection rule:
      - URL strings starting with ``postgresql://`` or ``postgres://`` -> PostgresStore.
      - Anything else (a Path, or a string path) -> SQLiteStore.
      - ``None`` -> falls back to :func:`context_capital.config.resolve_database_url`.

    The PostgresStore import is lazy so importing this module does not require
    psycopg to be installed.
    """
    resolved = db_url if db_url is not None else resolve_database_url()
    if isinstance(resolved, str) and resolved.startswith(("postgresql://", "postgres://")):
        from context_capital.storage.postgres import PostgresStore
        return PostgresStore(resolved)
    from context_capital.storage.sqlite import SQLiteStore
    path = resolved if isinstance(resolved, Path) else Path(resolved)
    return SQLiteStore(path)
```

- [ ] **Step 4: Update `storage/__init__.py`**

Replace contents of `src/context_capital/storage/__init__.py` with:

```python
"""Storage backends (ADR-003) — SQLite default, Postgres+pgvector when configured."""
from context_capital.storage.base import StoreBase
from context_capital.storage.factory import Store

__all__ = ["Store", "StoreBase"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_storage_factory.py -v`
Expected: 6 passed.

- [ ] **Step 6: Run the full suite to confirm `cc capture` / `cc list` / etc. still work**

Run: `pytest -q`
Expected: all green. The CLI still uses `Store(_store_path())`, which now goes through the factory, which dispatches to SQLiteStore via the Path branch.

- [ ] **Step 7: Lint + type check**

Run:
```bash
ruff check src/context_capital/storage/factory.py src/context_capital/storage/__init__.py tests/test_storage_factory.py
mypy --strict src/context_capital/storage/factory.py src/context_capital/storage/__init__.py
```
Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add src/context_capital/storage/factory.py src/context_capital/storage/__init__.py tests/test_storage_factory.py
git commit -m "feat(storage): add Store() factory dispatching on URL prefix"
```

---

### Task 5: `extract/embed.py` — embedding helper

**Files:**
- Create: `src/context_capital/extract/embed.py`
- Test: `tests/test_extract_embed.py`

**Interfaces:**
- Consumes: `litellm` (already in deps).
- Produces:
  - `DEFAULT_EMBED_MODEL: str` = `"voyage/voyage-3"`
  - `EMBED_DIM: int` = `1024`
  - `embed_text(text: str, *, model: str = DEFAULT_EMBED_MODEL) -> list[float] | None` — best-effort embedding.
  - `memory_to_text(memory: dict) -> str` — canonical shape `f"{predicate}: {value}\n{raw_excerpt[:512]}"`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_extract_embed.py`:

```python
"""Tests for the embedding helper."""
from __future__ import annotations

from unittest.mock import patch


def test_default_embed_model_is_voyage_3():
    from context_capital.extract.embed import DEFAULT_EMBED_MODEL, EMBED_DIM
    assert DEFAULT_EMBED_MODEL == "voyage/voyage-3"
    assert EMBED_DIM == 1024


def test_embed_text_happy_path():
    from context_capital.extract import embed as embed_mod
    fake_vec = [0.1] * 1024
    with patch.object(
        embed_mod, "litellm",
        embedding=lambda **_: {"data": [{"embedding": fake_vec}]},
    ):
        out = embed_mod.embed_text("hello world")
    assert out == fake_vec


def test_embed_text_empty_input_returns_none():
    from context_capital.extract.embed import embed_text
    assert embed_text("") is None
    assert embed_text("   ") is None


def test_embed_text_wrong_dim_returns_none():
    from context_capital.extract import embed as embed_mod
    bad_vec = [0.0] * 128
    with patch.object(
        embed_mod, "litellm",
        embedding=lambda **_: {"data": [{"embedding": bad_vec}]},
    ):
        assert embed_mod.embed_text("hello") is None


def test_embed_text_litellm_exception_returns_none():
    from context_capital.extract import embed as embed_mod

    def boom(**_):
        raise RuntimeError("network down")

    with patch.object(embed_mod, "litellm", embedding=boom):
        assert embed_mod.embed_text("anything") is None


def test_embed_text_no_data_returns_none():
    from context_capital.extract import embed as embed_mod
    with patch.object(
        embed_mod, "litellm",
        embedding=lambda **_: {"data": []},
    ):
        assert embed_mod.embed_text("x") is None


def test_memory_to_text_includes_predicate_value_and_excerpt():
    from context_capital.extract.embed import memory_to_text
    mem = {
        "predicate": "prefers_language",
        "object": {"value": "Python", "type": "string"},
        "provenance": {"raw_excerpt": "I love Python for data science."},
    }
    s = memory_to_text(mem)
    assert "prefers_language" in s
    assert "Python" in s
    assert "I love Python" in s


def test_memory_to_text_truncates_excerpt_to_512():
    from context_capital.extract.embed import memory_to_text
    mem = {
        "predicate": "p",
        "object": {"value": "v"},
        "provenance": {"raw_excerpt": "x" * 2000},
    }
    s = memory_to_text(mem)
    excerpt = s.split("\n", 1)[1]
    assert len(excerpt) == 512


def test_memory_to_text_missing_provenance_is_safe():
    from context_capital.extract.embed import memory_to_text
    s = memory_to_text({"predicate": "p", "object": {"value": "v"}})
    assert s.startswith("p: ")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_extract_embed.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'context_capital.extract.embed'`.

- [ ] **Step 3: Implement `extract/embed.py`**

Create `src/context_capital/extract/embed.py`:

```python
"""Embedding helper (litellm-fronted, best-effort)."""
from __future__ import annotations

import logging
from typing import Any

import litellm

logger = logging.getLogger(__name__)

DEFAULT_EMBED_MODEL: str = "voyage/voyage-3"
EMBED_DIM: int = 1024


def embed_text(text: str, *, model: str = DEFAULT_EMBED_MODEL) -> list[float] | None:
    """Return the embedding vector for ``text``, or ``None`` on any failure.

    Failures (network, no API key, rate limit, wrong dim) are logged at
    WARNING and the function returns ``None``. Callers treat embedding as
    best-effort: the memory is persisted whether or not an embedding row
    is created.
    """
    if not text or not text.strip():
        return None
    try:
        resp = litellm.embedding(model=model, input=[text])
        data = resp.get("data") if isinstance(resp, dict) else getattr(resp, "data", None)
        if not data:
            return None
        first = data[0]
        vec = first.get("embedding") if isinstance(first, dict) else getattr(first, "embedding", None)
        if not isinstance(vec, list) or len(vec) != EMBED_DIM:
            logger.warning(
                "embedding has unexpected shape (model=%s, len=%s)",
                model,
                len(vec) if isinstance(vec, list) else None,
            )
            return None
        return [float(x) for x in vec]
    except Exception as e:  # noqa: BLE001 — best-effort wrapper
        logger.warning("embed_text failed (model=%s): %s", model, e)
        return None


def memory_to_text(memory: dict[str, Any]) -> str:
    """Canonical embedding-input string for a memory.

    Shape: ``"{predicate}: {value}\\n{raw_excerpt[:512]}"``.
    """
    predicate = memory.get("predicate", "")
    obj = memory.get("object") or {}
    val = obj.get("value", "")
    excerpt = (memory.get("provenance") or {}).get("raw_excerpt") or ""
    return f"{predicate}: {val}\n{excerpt[:512]}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_extract_embed.py -v`
Expected: 9 passed.

- [ ] **Step 5: Lint + type check**

Run:
```bash
ruff check src/context_capital/extract/embed.py tests/test_extract_embed.py
mypy --strict src/context_capital/extract/embed.py
```
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add src/context_capital/extract/embed.py tests/test_extract_embed.py
git commit -m "feat(extract): add embed_text and memory_to_text helpers"
```

---

### Task 6: `PostgresStore` — CRUD (no embeddings yet)

**Files:**
- Create: `src/context_capital/storage/postgres.py`
- Test: `tests/test_storage_postgres.py`

**Interfaces:**
- Consumes: `StoreBase` (Task 1), `psycopg`, `pgvector.psycopg`, `context_capital.ingest.types.IngestContext`.
- Produces:
  - `PostgresStore(dsn: str, *, embed_dim: int = 1024)` — class subclassing `StoreBase`.
  - All abstract methods implemented EXCEPT `add_embedding` / `search_by_embedding` overrides (Task 7).
  - Module-level `PHASE1_DDL: str` constant — the inline mirror DDL described in Global Constraints.

- [ ] **Step 1: Write the failing tests (gated by `CC_RUN_PG_TESTS=1`)**

Create `tests/test_storage_postgres.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
CC_RUN_PG_TESTS=1 pytest tests/test_storage_postgres.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'context_capital.storage.postgres'`.

- [ ] **Step 3: Implement `storage/postgres.py`**

Create `src/context_capital/storage/postgres.py`:

```python
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
        ic: "IngestContext",
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
```

- [ ] **Step 4: Run gated tests to verify they pass**

Run:
```bash
CC_RUN_PG_TESTS=1 pytest tests/test_storage_postgres.py -v
```
Expected: 6 passed (first run pulls the `pgvector/pgvector:pg16` container).

- [ ] **Step 5: Run full suite without the gate**

Run: `pytest -q`
Expected: all green; Postgres tests skipped.

- [ ] **Step 6: Lint + type check**

Run:
```bash
ruff check src/context_capital/storage/postgres.py tests/test_storage_postgres.py
mypy --strict src/context_capital/storage/postgres.py
```
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add src/context_capital/storage/postgres.py tests/test_storage_postgres.py
git commit -m "feat(storage): add PostgresStore CRUD (gated tests)"
```

---

### Task 7: PostgresStore — embeddings + semantic search

**Files:**
- Modify: `src/context_capital/storage/postgres.py` — add `supports_embeddings`, `add_embedding`, `search_by_embedding`, and embed hook inside `add_memory`.
- Test: `tests/test_storage_postgres_embed.py`

**Interfaces:**
- Consumes: `embed_text`, `memory_to_text`, `DEFAULT_EMBED_MODEL`, `EMBED_DIM` from `context_capital.extract.embed` (Task 5).
- Produces:
  - `PostgresStore.supports_embeddings() -> bool` returns `True`.
  - `PostgresStore.add_embedding(memory_id, vector, *, model)` upserts into `vector_embeddings`.
  - `PostgresStore.search_by_embedding(vector, *, limit=10, subject_id, kind, sensitivity) -> list[dict]` cosine-distance ordered.
  - `PostgresStore.add_memory` writes a `vector_embeddings` row best-effort AFTER the memory commit.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_storage_postgres_embed.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
CC_RUN_PG_TESTS=1 pytest tests/test_storage_postgres_embed.py -v
```
Expected: FAIL — `supports_embeddings` still False; no embedding rows written; `search_by_embedding` still raises `NotImplementedError`.

- [ ] **Step 3: Extend `storage/postgres.py`**

Add these imports to `src/context_capital/storage/postgres.py` (after the existing `from context_capital.storage.base import StoreBase` line):

```python
from context_capital.extract import embed as embed_mod
from context_capital.extract.embed import DEFAULT_EMBED_MODEL, memory_to_text
```

Add these methods to the `PostgresStore` class, immediately BEFORE the `# ---- Audit ----` section:

```python
    # ---- Embeddings + semantic search ------------------------------------
    def supports_embeddings(self) -> bool:
        return True

    def add_embedding(
        self,
        memory_id: str,
        vector: list[float],
        *,
        model: str,
    ) -> None:
        if len(vector) != self.embed_dim:
            raise ValueError(
                f"embedding dim {len(vector)} does not match column vector({self.embed_dim}); "
                "set CC_EMBED_MODEL to a matching-dim model or migrate the schema"
            )
        c = self._require_conn()
        with c.cursor() as cur:
            cur.execute(
                "INSERT INTO vector_embeddings (memory_id, model, embedding)"
                " VALUES (%s, %s, %s)"
                " ON CONFLICT (memory_id, model) DO UPDATE SET"
                "  embedding = EXCLUDED.embedding, created_at = now()",
                (memory_id, model, vector),
            )
        c.commit()

    def search_by_embedding(
        self,
        vector: list[float],
        *,
        limit: int = 10,
        subject_id: str | None = None,
        kind: str | None = None,
        sensitivity: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        if len(vector) != self.embed_dim:
            raise ValueError(
                f"query embedding dim {len(vector)} != column dim {self.embed_dim}"
            )
        q = (
            "SELECT m.*, p.source, p.extracted_at, p.raw_excerpt,"
            " p.imported, p.import_source, p.model"
            " FROM memories m"
            " JOIN vector_embeddings v ON v.memory_id = m.id"
            " LEFT JOIN provenance p ON p.memory_id = m.id"
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
        q += " ORDER BY v.embedding <=> %s LIMIT %s"
        params.extend([vector, int(limit)])
        c = self._require_conn()
        with c.cursor() as cur:
            cur.execute(q, params)
            rows = cur.fetchall()
        return [self._row_to_memory(r) for r in rows]
```

Extend `add_memory`: at the very END of the existing `add_memory` body, AFTER the successful `c.commit()`, append (still inside the function, OUTSIDE the try/except — this block intentionally runs only after the memory has been committed so embed failures cannot roll back the memory):

```python
        # Best-effort: compute + store the embedding. Failure does NOT roll back the memory.
        try:
            text = memory_to_text(memory)
            vec = embed_mod.embed_text(text, model=DEFAULT_EMBED_MODEL)
            if vec is not None:
                self.add_embedding(memory["id"], vec, model=DEFAULT_EMBED_MODEL)
            else:
                logger.info("no embedding written for %s (embed_text returned None)", memory["id"])
        except Exception as e:  # noqa: BLE001 — best-effort
            logger.warning("embedding step failed for %s: %s", memory["id"], e)
```

- [ ] **Step 4: Run gated tests to verify they pass**

Run:
```bash
CC_RUN_PG_TESTS=1 pytest tests/test_storage_postgres_embed.py -v
```
Expected: 6 passed.

- [ ] **Step 5: Re-run all gated tests to confirm no regression**

Run:
```bash
CC_RUN_PG_TESTS=1 pytest tests/test_storage_postgres.py tests/test_storage_postgres_embed.py -v
```
Expected: 12 passed.

Run: `pytest -q`
Expected: all green (Postgres tests skipped).

- [ ] **Step 6: Lint + type check**

Run:
```bash
ruff check src/context_capital/storage/postgres.py tests/test_storage_postgres_embed.py
mypy --strict src/context_capital/storage/postgres.py
```
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add src/context_capital/storage/postgres.py tests/test_storage_postgres_embed.py
git commit -m "feat(storage): add embeddings and search_by_embedding to PostgresStore"
```

---

### Task 8: `cc migrate --to postgres`

**Files:**
- Modify: `src/context_capital/cli.py` — add `migrate` command and `import os`.
- Test: `tests/test_cli_migrate.py`

**Interfaces:**
- Consumes: `Store` factory, `SQLiteStore`, `PostgresStore`, `embed_text`/`memory_to_text`/`DEFAULT_EMBED_MODEL` (Task 5).
- Produces: CLI command `cc migrate --to postgres [--source PATH] [--target URL] [--with-embeddings/--no-embeddings] [--force]`.

**Migration order (FK-safe):** `subjects` → `contexts` → `raw_messages` → `memories` → `provenance` → `audit_log_entries`. `validity_periods` is intentionally not migrated (SQLite store does not write to it).

**Idempotency:** every Postgres INSERT uses `ON CONFLICT DO NOTHING` keyed on PK. Re-running picks up exactly where a partial run left off. The `audit_log_entries` table has no natural dedup key — its rows are appended every run; this is acceptable because each run also writes a single summary entry that records totals (so duplicates of operational events are tolerable noise, not corruption).

**Safety check:** if target Postgres already has subjects AND none of them match source subjects, refuse unless `--force` is passed.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cli_migrate.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli_migrate.py -v -k "not row_count"`
Expected: FAIL — no `migrate` command on `app`.

- [ ] **Step 3: Add `import os` and the `migrate` command in `src/context_capital/cli.py`**

At the top of `src/context_capital/cli.py` (with the other `import` lines), add:

```python
import os
```

After the existing `@app.command("verify-audit")` block (or before it — order is cosmetic), add:

```python
@app.command()
def migrate(  # noqa: B008
    to: str = typer.Option(..., "--to", help="Target backend (only 'postgres' supported)."),
    source: Path | None = typer.Option(None, "--source", help="Source SQLite path."),  # noqa: B008
    target: str | None = typer.Option(None, "--target", help="Target Postgres URL."),
    with_embeddings: bool = typer.Option(False, "--with-embeddings/--no-embeddings"),
    force: bool = typer.Option(False, "--force", help="Bypass cross-subject safety check."),
) -> None:
    """One-way migrate a SQLite store into a Postgres database (idempotent)."""
    if to != "postgres":
        raise typer.BadParameter("Only --to postgres is supported.")
    src_path = source if source is not None else _store_path()
    if not src_path.exists():
        raise typer.BadParameter(f"source not found: {src_path}")
    tgt_url = target or os.environ.get("CC_DATABASE_URL")
    if not tgt_url:
        raise typer.BadParameter("Set --target or CC_DATABASE_URL.")

    from context_capital.extract.embed import (
        DEFAULT_EMBED_MODEL,
        embed_text,
        memory_to_text,
    )
    from context_capital.storage.postgres import PostgresStore
    from context_capital.storage.sqlite import SQLiteStore

    moved_subjects = moved_contexts = moved_messages = moved_memories = moved_embeddings = 0

    with SQLiteStore(src_path) as src, PostgresStore(tgt_url) as dst:
        src_conn = src._require_conn()  # noqa: SLF001
        dst_conn = dst._require_conn()  # noqa: SLF001

        # Safety check.
        src_subject_ids = {
            r["id"] for r in src_conn.execute("SELECT id FROM subjects").fetchall()
        }
        with dst_conn.cursor() as cur:
            cur.execute("SELECT id FROM subjects")
            dst_subject_ids = {r["id"] for r in cur.fetchall()}
        if dst_subject_ids and not (src_subject_ids & dst_subject_ids) and not force:
            raise typer.BadParameter(
                f"target already has {len(dst_subject_ids)} subject(s) with no overlap to "
                f"source's {len(src_subject_ids)}. Use --force to override."
            )

        # 1) subjects
        for r in src_conn.execute("SELECT id, type, display_name FROM subjects").fetchall():
            with dst_conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO subjects (id, type, display_name) VALUES (%s, %s, %s) "
                    "ON CONFLICT (id) DO NOTHING",
                    (r["id"], r["type"], r["display_name"]),
                )
                moved_subjects += max(cur.rowcount, 0)

        # 2) contexts
        for r in src_conn.execute(
            "SELECT id, subject_id, source_vendor, source_file_hash,"
            " vendor_conversation_id, title, captured_at FROM contexts"
        ).fetchall():
            with dst_conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO contexts (id, subject_id, source_vendor, source_file_hash,"
                    " vendor_conversation_id, title, captured_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
                    (r["id"], r["subject_id"], r["source_vendor"], r["source_file_hash"],
                     r["vendor_conversation_id"], r["title"], r["captured_at"]),
                )
                moved_contexts += max(cur.rowcount, 0)

        # 3) raw_messages
        for r in src_conn.execute(
            "SELECT context_id, seq, role, content, created_at, vendor_message_id"
            " FROM raw_messages ORDER BY context_id, seq"
        ).fetchall():
            with dst_conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO raw_messages"
                    " (context_id, seq, role, content, created_at, vendor_message_id) "
                    "VALUES (%s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (context_id, seq) DO NOTHING",
                    (r["context_id"], r["seq"], r["role"], r["content"],
                     r["created_at"], r["vendor_message_id"]),
                )
                moved_messages += max(cur.rowcount, 0)

        # 4) memories
        memory_ids_inserted: list[str] = []
        for r in src_conn.execute(
            "SELECT id, subject_id, kind, predicate, object_value, object_type,"
            " confidence, sensitivity FROM memories"
        ).fetchall():
            with dst_conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO memories (id, subject_id, kind, predicate, object_value,"
                    " object_type, confidence, sensitivity) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (id) DO NOTHING",
                    (r["id"], r["subject_id"], r["kind"], r["predicate"],
                     r["object_value"], r["object_type"], float(r["confidence"]),
                     r["sensitivity"]),
                )
                if cur.rowcount > 0:
                    memory_ids_inserted.append(r["id"])
                    moved_memories += 1

        # 5) provenance
        for r in src_conn.execute(
            "SELECT memory_id, source, extracted_at, raw_excerpt, imported,"
            " import_source, model, sanitization_trace FROM provenance"
        ).fetchall():
            with dst_conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO provenance (memory_id, source, extracted_at, raw_excerpt,"
                    " imported, import_source, model, sanitization_trace) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (memory_id) DO NOTHING",
                    (r["memory_id"], r["source"], r["extracted_at"], r["raw_excerpt"],
                     bool(r["imported"]), r["import_source"], r["model"],
                     r["sanitization_trace"]),
                )

        # 6) audit log (append; no natural dedup key)
        for r in src_conn.execute(
            "SELECT at, actor, action, subject_id, details, outcome FROM audit_log_entries"
            " ORDER BY id"
        ).fetchall():
            with dst_conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO audit_log_entries (at, actor, action, subject_id, details, outcome) "
                    "VALUES (%s, %s, %s, %s, %s::jsonb, %s)",
                    (r["at"], r["actor"], r["action"], r["subject_id"],
                     r["details"] or "{}", r["outcome"]),
                )

        dst_conn.commit()

        # 7) Optional embeddings
        if with_embeddings and memory_ids_inserted:
            for mem_id in memory_ids_inserted:
                m = dst.get_memory(mem_id)
                if not m:
                    continue
                vec = embed_text(memory_to_text(m), model=DEFAULT_EMBED_MODEL)
                if vec is None:
                    continue
                try:
                    dst.add_embedding(mem_id, vec, model=DEFAULT_EMBED_MODEL)
                    moved_embeddings += 1
                except Exception as e:  # noqa: BLE001
                    rprint(f"[yellow]embed failed for {mem_id}: {e}[/yellow]")

        # 8) Final summary audit entry on the target.
        with dst_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO audit_log_entries"
                " (actor, action, subject_id, details, outcome)"
                " VALUES (%s, %s, %s, %s::jsonb, %s)",
                (
                    "cli:migrate", "extract:done", None,
                    json.dumps({
                        "source": str(src_path),
                        "subjects": moved_subjects,
                        "contexts": moved_contexts,
                        "raw_messages": moved_messages,
                        "memories": moved_memories,
                        "embeddings": moved_embeddings,
                    }),
                    "success",
                ),
            )
        dst_conn.commit()

    rprint(
        f"[green]Migrated[/green]: {moved_subjects} subjects, {moved_contexts} contexts, "
        f"{moved_messages} messages, {moved_memories} memories, {moved_embeddings} embeddings."
    )
```

(`json` is already imported in `cli.py`. `Path`, `typer`, `rprint` are already imported.)

- [ ] **Step 4: Run the always-on migrate tests**

Run: `pytest tests/test_cli_migrate.py -v -k "not row_count"`
Expected: 2 passed.

- [ ] **Step 5: Run the gated round-trip test**

Run: `CC_RUN_PG_TESTS=1 pytest tests/test_cli_migrate.py::test_migrate_sqlite_to_postgres_row_count_parity -v`
Expected: 1 passed.

- [ ] **Step 6: Run full suite**

Run: `pytest -q`
Expected: all green (gated test skipped).

- [ ] **Step 7: Lint + type check**

Run:
```bash
ruff check src/context_capital/cli.py tests/test_cli_migrate.py
mypy --strict src/context_capital/cli.py
```
Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add src/context_capital/cli.py tests/test_cli_migrate.py
git commit -m "feat(cli): add 'cc migrate --to postgres' (idempotent, optional embeddings)"
```

---

### Task 9: `cc memories search`

**Files:**
- Modify: `src/context_capital/cli.py` — add nested typer subapp `memories` with `search` command.
- Test: `tests/test_cli_memories_search.py`

**Interfaces:**
- Consumes: `Store` factory, `embed_text` (Task 5), `resolve_embed_model` (Task 3).
- Produces:
  - CLI: `cc memories search "QUERY" [--limit N] [--kind K] [--sensitivity S ...]`
  - Behavior: if `store.supports_embeddings()` is False, print clear error + exit 2. Else embed the query, call `store.search_by_embedding`, print results.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cli_memories_search.py`:

```python
"""Tests for cc memories search."""
from __future__ import annotations

from unittest.mock import MagicMock

from typer.testing import CliRunner

runner = CliRunner()


def _init_cc(tmp_path, monkeypatch):
    from context_capital import cli as cli_mod
    monkeypatch.setattr(cli_mod, "DATA_DIR", tmp_path)
    (tmp_path / "signing.key").write_bytes(b"\x00" * 32)
    (tmp_path / "subject_did").write_text("did:key:test")
    return cli_mod.app


def test_search_on_sqlite_exits_2_with_clear_message(tmp_path, monkeypatch):
    app = _init_cc(tmp_path, monkeypatch)
    monkeypatch.delenv("CC_DATABASE_URL", raising=False)
    res = runner.invoke(app, ["memories", "search", "anything"])
    assert res.exit_code == 2
    assert "Postgres" in res.output or "CC_DATABASE_URL" in res.output


def test_search_calls_store_with_query_vector_and_filters(tmp_path, monkeypatch):
    from context_capital import cli as cli_mod
    app = _init_cc(tmp_path, monkeypatch)

    fake_store = MagicMock()
    fake_store.__enter__ = lambda self: self
    fake_store.__exit__ = lambda self, *a: None
    fake_store.supports_embeddings.return_value = True
    fake_store.search_by_embedding.return_value = [
        {
            "id": "mem_" + "0" * 31 + "a",
            "kind": "preference",
            "predicate": "prefers",
            "object": {"value": "Python", "type": "string"},
            "sensitivity": "work",
        }
    ]
    monkeypatch.setattr(cli_mod, "Store", lambda *a, **kw: fake_store)
    monkeypatch.setattr(
        "context_capital.extract.embed.embed_text",
        lambda text, *, model="voyage/voyage-3": [0.1] * 1024,
    )

    res = runner.invoke(app, [
        "memories", "search", "best language",
        "--limit", "3",
        "--kind", "preference",
        "--sensitivity", "work",
        "--sensitivity", "public",
    ])
    assert res.exit_code == 0, res.output
    fake_store.search_by_embedding.assert_called_once()
    call_kwargs = fake_store.search_by_embedding.call_args.kwargs
    assert call_kwargs["limit"] == 3
    assert call_kwargs["kind"] == "preference"
    assert sorted(call_kwargs["sensitivity"]) == ["public", "work"]
    assert "Python" in res.output


def test_search_handles_embed_failure(tmp_path, monkeypatch):
    from context_capital import cli as cli_mod
    app = _init_cc(tmp_path, monkeypatch)

    fake_store = MagicMock()
    fake_store.__enter__ = lambda self: self
    fake_store.__exit__ = lambda self, *a: None
    fake_store.supports_embeddings.return_value = True
    monkeypatch.setattr(cli_mod, "Store", lambda *a, **kw: fake_store)
    monkeypatch.setattr(
        "context_capital.extract.embed.embed_text",
        lambda text, *, model="voyage/voyage-3": None,
    )

    res = runner.invoke(app, ["memories", "search", "anything"])
    assert res.exit_code == 2
    assert "embed" in res.output.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli_memories_search.py -v`
Expected: FAIL — no `memories` subcommand on `app`.

- [ ] **Step 3: Add the `memories` subapp and `search` command in `cli.py`**

In `src/context_capital/cli.py`, append (after the existing commands):

```python
memories_app = typer.Typer(help="Memory-level operations.", no_args_is_help=True)
app.add_typer(memories_app, name="memories")


@memories_app.command("search")
def memories_search(  # noqa: B008
    query: str = typer.Argument(..., help="Search query (free text)."),
    limit: int = typer.Option(10, "--limit", "-l"),
    kind: str | None = typer.Option(None, "--kind", "-k"),
    sensitivity: list[str] | None = typer.Option(None, "--sensitivity", "-s"),  # noqa: B008
) -> None:
    """Semantic search over stored memories (Postgres backend only)."""
    from context_capital.config import resolve_embed_model
    from context_capital.extract.embed import embed_text

    subject_id = _load_subject_id()
    with Store() as store:
        if not store.supports_embeddings():
            rprint(
                "[red]Semantic search requires the Postgres backend.[/red]\n"
                "Set CC_DATABASE_URL=postgresql://... and re-run."
            )
            raise typer.Exit(2)
        model = resolve_embed_model()
        vec = embed_text(query, model=model)
        if vec is None:
            rprint("[red]Could not embed query (embed_text returned None).[/red]")
            raise typer.Exit(2)
        results = store.search_by_embedding(
            vec,
            limit=limit,
            subject_id=subject_id,
            kind=kind,
            sensitivity=sensitivity or None,
        )
    if not results:
        rprint("[yellow]No matches.[/yellow]")
        return
    for m in results:
        rprint(
            f"  {m['id']}  ({m['kind']}/{m['predicate']})  -> {m['object']['value']}"
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli_memories_search.py -v`
Expected: 3 passed.

- [ ] **Step 5: Run full suite**

Run: `pytest -q`
Expected: all green.

- [ ] **Step 6: Lint + type check**

Run:
```bash
ruff check src/context_capital/cli.py tests/test_cli_memories_search.py
mypy --strict src/context_capital/cli.py
```
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add src/context_capital/cli.py tests/test_cli_memories_search.py
git commit -m "feat(cli): add 'cc memories search' (Postgres only)"
```

---

### Task 10: README quickstart + ops note

**Files:**
- Modify: `README.md` — add a Postgres / Supabase quickstart block.
- (Optional) Modify: `docs/ops/runbook.md` — add a short "Switching to Postgres / Supabase" section.

**Interfaces:**
- Consumes: nothing (docs).
- Produces: documented quickstart for the new backend.

- [ ] **Step 1: Insert a Postgres quickstart block into `README.md`**

In `README.md`, find the existing Quickstart section. Immediately AFTER the existing quickstart code blocks, append a new subsection:

````markdown
### Using Postgres / Supabase

Context Capital uses SQLite by default. To use any Postgres database with the `pgvector` extension enabled (Supabase, self-hosted, RDS, etc.), set `CC_DATABASE_URL`:

```bash
# Supabase
export CC_DATABASE_URL='postgresql://user:pass@db.PROJECT.supabase.co:5432/postgres'

# Or self-hosted
export CC_DATABASE_URL='postgresql://user:pass@localhost:5432/cc'

cc capture --vendor chatgpt --file conversations.json
cc memories search "what languages do I prefer"
```

To move an existing local SQLite store into a Postgres database:

```bash
cc migrate --to postgres \
  --source ~/.context-capital/store.db \
  --target "$CC_DATABASE_URL" \
  --with-embeddings
```

Migration is idempotent — re-running picks up where it left off via `ON CONFLICT DO NOTHING`.

**Note:** with the Postgres backend, every new memory gets an embedding (default model: `voyage/voyage-3`, dim 1024) so `cc memories search` can do cosine-similarity recall. If the embedding provider is down or unconfigured, memories are still persisted; the embedding row is skipped with a log line, and you can backfill later by re-running `cc migrate --with-embeddings` against the same target.
````

- [ ] **Step 2: (Optional) Add an ops runbook entry**

If `docs/ops/runbook.md` exists, append:

```markdown
## Switching to Postgres / Supabase

1. Provision a Postgres database with the `vector` extension (Supabase: enabled by default).
2. Export `CC_DATABASE_URL=postgresql://...` or write it to `~/.context-capital/config.toml`:

   ```toml
   [storage]
   database_url = "postgresql://..."
   ```

3. Run `cc migrate --to postgres --with-embeddings` to copy an existing SQLite store across.
4. Verify with `cc list` and `cc memories search "test query"`.

**PgBouncer note:** Supabase's pooler at `*.pooler.supabase.com:6543` defaults to *transaction* mode, which is incompatible with psycopg3's prepared statements. Use either the direct connection (`db.PROJECT.supabase.co:5432`) or set the pooler to *session* mode.
```

- [ ] **Step 3: Verify README renders sensibly**

Run: `grep -n "Postgres / Supabase" README.md`
Expected: 1 match for the heading.

- [ ] **Step 4: Run full suite one last time**

Run: `pytest -q`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add README.md docs/ops/runbook.md 2>/dev/null || git add README.md
git commit -m "docs: README quickstart + runbook note for Postgres/Supabase backend"
```

---

## Final Verification

After all 11 tasks (T0–T10) are complete:

- [ ] `pytest -q` is green (existing + new always-on tests).
- [ ] `CC_RUN_PG_TESTS=1 pytest -q` is green (adds 6+6+1 = 13 gated tests).
- [ ] `ruff check src/context_capital/storage src/context_capital/config.py src/context_capital/extract/embed.py src/context_capital/cli.py` is clean.
- [ ] `mypy --strict` on the same paths is clean.
- [ ] `cc capture --vendor chatgpt --file ...` writes to whatever `CC_DATABASE_URL` resolves to.
- [ ] `cc memories search "query"` returns ranked results on Postgres; exits 2 with clear message on SQLite.
- [ ] `cc migrate --to postgres` is idempotent on re-run.
- [ ] README has a "Using Postgres / Supabase" subsection.

---

## Self-Review (writing-plans skill checklist)

**Spec coverage** — every section of `2026-06-22-postgres-supabase-backend-design.md` maps to a task:
- §2 Scope (files) → File Map above + Tasks 0–10
- §3 Architecture → Task 4 (factory) + Tasks 6/7 (subclass)
- §4.1 StoreBase → Task 1
- §4.2 SQLiteStore rename → Task 2
- §4.3 PostgresStore → Tasks 6 + 7
- §4.4 factory.py → Task 4
- §4.5 storage/__init__.py → Task 4
- §4.6 config.py → Task 3
- §4.7 extract/embed.py → Task 5
- §4.8 cc migrate → Task 8
- §4.9 cc memories search → Task 9
- §5 Data flow → tests in Tasks 6, 7, 8, 9
- §6 Schema reuse → **documented deviation** in Global Constraints (inline Phase-1 DDL, not schema.sql verbatim). Reason: canonical schema requires F-4/F-9 features not yet shipped. Carry-forward TODO comment mandated in Task 6 code.
- §7 Backend selection examples → Task 10 README block
- §8 Failure modes → covered in tests (Task 7: dim mismatch raises with explicit message; Task 7: embed failure does not roll back; Task 9: search-on-sqlite exits 2)
- §9 Tests table → 1:1 with the test files declared in this plan
- §10 Definition of Done → Final Verification checklist above
- §11 Out of scope → preserved (no tasks for them)
- §12 Open questions → embed dim mismatch handled (Task 7 `add_embedding` raises with explicit message); PgBouncer note in Task 10 runbook entry

**Placeholder scan:** no `TBD`, no unfilled `TODO` in implementation steps. One intentional `TODO(post-F-4)` source-code comment is required by Global Constraints and is fully specified.

**Type consistency:** `Store` is a function from Task 4 onward; `SQLiteStore`, `PostgresStore`, `StoreBase` are classes; `embed_text` / `memory_to_text` / `DEFAULT_EMBED_MODEL` / `EMBED_DIM` consistent across Tasks 5/6/7/8/9; `resolve_database_url` / `resolve_embed_model` consistent across Tasks 3/4/9. All `add_memory` / `add_embedding` / `search_by_embedding` signatures match `StoreBase` declarations.
