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
