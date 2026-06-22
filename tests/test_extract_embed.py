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
