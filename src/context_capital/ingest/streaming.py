"""Streaming JSON reader for large vendor exports."""
from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import ijson  # type: ignore[import-untyped]

DEFAULT_STREAM_THRESHOLD: int = 50 * 1024 * 1024  # 50 MB


def _threshold() -> int:
    raw = os.environ.get("CC_STREAM_THRESHOLD_BYTES")
    if raw is None or raw.strip() == "":
        return DEFAULT_STREAM_THRESHOLD
    try:
        return int(raw)
    except ValueError:
        return DEFAULT_STREAM_THRESHOLD


def should_stream(path: Path) -> bool:
    return path.stat().st_size > _threshold()


def stream_top_level_array(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("rb") as f:
        for item in ijson.items(f, "item"):
            if isinstance(item, dict):
                yield item


def load_all(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text())
    if not isinstance(raw, list):
        raise ValueError(f"top level of {path} is not an array")
    return [item for item in raw if isinstance(item, dict)]


def iter_items(path: Path) -> Iterator[dict[str, Any]]:
    if should_stream(path):
        yield from stream_top_level_array(path)
    else:
        yield from load_all(path)
