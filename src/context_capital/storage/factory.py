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
        from context_capital.storage.postgres import PostgresStore  # type: ignore[import-untyped]
        return PostgresStore(resolved)  # type: ignore[no-any-return]
    from context_capital.storage.sqlite import SQLiteStore
    path = resolved if isinstance(resolved, Path) else Path(resolved)
    return SQLiteStore(path)
