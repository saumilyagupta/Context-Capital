from __future__ import annotations

from context_capital.extract.mock import extract_mock_memories

SUBJECT = "did:key:zABC"


def test_no_cues_returns_empty() -> None:
    assert extract_mock_memories(subject_id=SUBJECT, raw_text="hello world") == []


def test_pytorch_cue_extracts_preference() -> None:
    mems = extract_mock_memories(subject_id=SUBJECT, raw_text="I prefer PyTorch for ML.")
    assert len(mems) == 1
    assert mems[0]["kind"] == "preference"
    assert mems[0]["object"]["value"] == "PyTorch"


def test_multiple_cues_extract_multiple_memories() -> None:
    text = "My Python code for the Drone uses PyTorch."
    mems = extract_mock_memories(subject_id=SUBJECT, raw_text=text)
    kinds = {m["kind"] for m in mems}
    assert {"preference", "skill", "project"} <= kinds


def test_ids_are_deterministic() -> None:
    a = extract_mock_memories(subject_id=SUBJECT, raw_text="I prefer PyTorch.")
    b = extract_mock_memories(subject_id=SUBJECT, raw_text="I prefer PyTorch.")
    assert [m["id"] for m in a] == [m["id"] for m in b]


def test_extracted_memories_have_provenance_and_confidence() -> None:
    mems = extract_mock_memories(subject_id=SUBJECT, raw_text="PyTorch is great.")
    assert mems[0]["provenance"]["model"] == "mock/extractor-v0"
    assert mems[0]["provenance"]["imported"] is False
    assert 0.0 <= mems[0]["confidence"] <= 1.0
