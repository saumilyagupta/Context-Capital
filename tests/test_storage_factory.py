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
