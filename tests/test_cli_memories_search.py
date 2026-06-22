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
