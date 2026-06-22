"""Tests for the streaming JSON reader."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from context_capital.ingest.streaming import (
    DEFAULT_STREAM_THRESHOLD,
    iter_items,
    load_all,
    should_stream,
    stream_top_level_array,
)


def _write_array(path: Path, n: int) -> None:
    arr = [{"i": i, "text": f"item-{i}"} for i in range(n)]
    path.write_text(json.dumps(arr))


def test_load_all_reads_full_array(tmp_path: Path) -> None:
    p = tmp_path / "small.json"
    _write_array(p, 5)
    items = load_all(p)
    assert len(items) == 5
    assert items[2] == {"i": 2, "text": "item-2"}


def test_stream_top_level_array_yields_one_at_a_time(tmp_path: Path) -> None:
    p = tmp_path / "stream.json"
    _write_array(p, 100)
    items = list(stream_top_level_array(p))
    assert len(items) == 100
    assert items[42]["i"] == 42


def test_should_stream_below_threshold_false(tmp_path: Path) -> None:
    p = tmp_path / "tiny.json"
    p.write_text("[]")
    assert should_stream(p) is False


def test_should_stream_honors_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "x.json"
    p.write_text("[]")
    monkeypatch.setenv("CC_STREAM_THRESHOLD_BYTES", "1")
    assert should_stream(p) is True


def test_iter_items_dispatches_by_size(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "x.json"
    _write_array(p, 3)
    monkeypatch.setenv("CC_STREAM_THRESHOLD_BYTES", "0")
    items = list(iter_items(p))
    assert [it["i"] for it in items] == [0, 1, 2]


def test_default_threshold_is_50mb() -> None:
    assert DEFAULT_STREAM_THRESHOLD == 50 * 1024 * 1024
