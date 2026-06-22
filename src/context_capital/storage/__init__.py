"""Storage backends (ADR-003) — SQLite default, Postgres+pgvector when configured."""
from context_capital.storage.base import StoreBase
from context_capital.storage.factory import Store

__all__ = ["Store", "StoreBase"]
