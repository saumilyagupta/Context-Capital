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
