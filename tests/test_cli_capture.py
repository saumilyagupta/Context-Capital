"""Smoke tests for cc capture via typer.testing.CliRunner."""
from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

import context_capital.cli as cli_mod
from context_capital.cli import app

runner = CliRunner()


@pytest.fixture
def isolated_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(cli_mod, "DATA_DIR", fake_home / ".context-capital")
    return fake_home


def _init() -> None:
    res = runner.invoke(app, ["init"])
    assert res.exit_code == 0, res.output


def _copy_fixture(name: str, dest: Path) -> Path:
    src = Path(__file__).parent / "fixtures" / "captures" / name
    out = dest / name
    shutil.copy(src, out)
    return out


def test_capture_chatgpt_with_mock(isolated_home: Path, tmp_path: Path) -> None:
    _init()
    fixture = _copy_fixture("chatgpt-synthetic.json", tmp_path)
    res = runner.invoke(app, ["capture", "--vendor", "chatgpt", "--file", str(fixture), "--mock"])
    assert res.exit_code == 0, res.output


def test_capture_claude_with_mock(isolated_home: Path, tmp_path: Path) -> None:
    _init()
    fixture = _copy_fixture("claude-synthetic.json", tmp_path)
    res = runner.invoke(app, ["capture", "--vendor", "claude", "--file", str(fixture), "--mock"])
    assert res.exit_code == 0, res.output


def test_capture_unknown_vendor_fails(isolated_home: Path, tmp_path: Path) -> None:
    _init()
    fixture = tmp_path / "x.json"
    fixture.write_text("[]")
    res = runner.invoke(app, ["capture", "--vendor", "gemini", "--file", str(fixture), "--mock"])
    assert res.exit_code != 0


def test_capture_idempotent(isolated_home: Path, tmp_path: Path) -> None:
    _init()
    fixture = _copy_fixture("chatgpt-synthetic.json", tmp_path)
    res1 = runner.invoke(app, ["capture", "--vendor", "chatgpt", "--file", str(fixture), "--mock"])
    res2 = runner.invoke(app, ["capture", "--vendor", "chatgpt", "--file", str(fixture), "--mock"])
    assert res1.exit_code == 0
    assert res2.exit_code == 0


def test_extract_text_with_mock_still_works(isolated_home: Path) -> None:
    _init()
    res = runner.invoke(app, ["extract", "--text", "I prefer PyTorch and use Python.", "--mock"])
    assert res.exit_code == 0, res.output


def test_capture_real_model_path_uses_llm(
    isolated_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _init()
    fixture = _copy_fixture("chatgpt-synthetic.json", tmp_path)

    def fake_real(**kw: Any) -> list[dict[str, Any]]:
        return [{
            "id": "mem_" + "0" * 32,
            "kind": "preference",
            "subject_id": kw["subject_id"],
            "predicate": "prefers",
            "object": {"value": "Real", "type": "tool"},
            "confidence": 0.9,
            "sensitivity": "work",
            "provenance": {
                "source": "chatgpt:conv_a1b2c3",
                "extracted_at": datetime.now(timezone.utc).isoformat(),
                "raw_excerpt": "test",
                "imported": False,
                "model": "mocked",
            },
        }]

    monkeypatch.setattr(cli_mod, "extract_memories", fake_real)
    res = runner.invoke(app, ["capture", "--vendor", "chatgpt", "--file", str(fixture)])
    assert res.exit_code == 0, res.output
