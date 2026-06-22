"""Tests for the export anonymizer."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.anonymize_export import anonymize, main


def _write(tmp_path: Path, name: str, payload: object) -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(payload))
    return p


def test_emails_are_replaced(tmp_path: Path) -> None:
    src = _write(tmp_path, "in.json", [{"text": "contact alice@example.com please"}])
    out = tmp_path / "out.json"
    report = anonymize(vendor="chatgpt", in_path=src, out_path=out, seed=42)
    body = out.read_text()
    assert "alice@example.com" not in body
    assert "example.invalid" in body
    assert report.emails_replaced == 1


def test_urls_are_replaced(tmp_path: Path) -> None:
    src = _write(tmp_path, "in.json", [{"text": "see https://internal.acme.com/secret"}])
    out = tmp_path / "out.json"
    anonymize(vendor="chatgpt", in_path=src, out_path=out, seed=1)
    body = out.read_text()
    assert "acme.com" not in body
    assert "example.invalid" in body


def test_api_keys_detected_and_redacted(tmp_path: Path) -> None:
    src = _write(tmp_path, "in.json",
                 [{"text": "key: sk-ABCDEFGHIJKLMNOPQRSTUVWX leak"}])
    out = tmp_path / "out.json"
    report = anonymize(vendor="chatgpt", in_path=src, out_path=out, seed=1)
    body = out.read_text()
    assert "sk-ABCDEFGHIJKLMNOPQRSTUVWX" not in body
    assert "<api-key>" in body
    assert report.api_keys_detected >= 1


def test_common_names_replaced(tmp_path: Path) -> None:
    src = _write(tmp_path, "in.json", [{"text": "James went home with Sarah."}])
    out = tmp_path / "out.json"
    report = anonymize(vendor="chatgpt", in_path=src, out_path=out, seed=42)
    body = out.read_text()
    assert "James" not in body
    assert "Sarah" not in body
    assert report.names_replaced >= 2


def test_deterministic_with_seed(tmp_path: Path) -> None:
    src = _write(tmp_path, "in.json", [{"text": "alice@example.com and bob@example.com"}])
    out1 = tmp_path / "a.json"
    out2 = tmp_path / "b.json"
    anonymize(vendor="chatgpt", in_path=src, out_path=out1, seed=42)
    anonymize(vendor="chatgpt", in_path=src, out_path=out2, seed=42)
    assert out1.read_text() == out2.read_text()


def test_main_writes_output(tmp_path: Path) -> None:
    src = _write(tmp_path, "in.json", [{"text": "hi alice@example.com"}])
    out = tmp_path / "out.json"
    rc = main(["--vendor", "chatgpt", "--in", str(src), "--out", str(out), "--seed", "1"])
    assert rc == 0
    assert out.exists()


def test_unknown_vendor_raises(tmp_path: Path) -> None:
    src = _write(tmp_path, "in.json", [{}])
    out = tmp_path / "out.json"
    with pytest.raises(ValueError):
        anonymize(vendor="gemini", in_path=src, out_path=out, seed=0)
