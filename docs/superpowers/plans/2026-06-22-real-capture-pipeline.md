# Real Capture Pipeline Implementation Plan (F-1 + F-2 + F-3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the mock keyword extractor with a real capture pipeline: ChatGPT and Claude export parsers feeding a `litellm`-fronted Claude extractor, all wired into a new `cc capture` CLI command. Closes SRS gate G-1.

**Architecture:** Vendor adapters (`ingest/chatgpt.py`, `ingest/claude.py`) emit a canonical `IngestContext` Pydantic type that the extractor consumes vendor-blind. Large files are streamed via `ijson`. The extractor chunks, calls Claude through `litellm` with prompt-cache and `response_format=json_object`, validates each memory against the v0.1 schema, and returns plain dicts the existing `Store` persists. The mock extractor is preserved as a `--mock` fallback.

**Tech Stack:** Python 3.12+; Pydantic v2; `ijson ≥ 3.3` (streaming); `litellm ≥ 1.50` (LLM dispatcher); `jsonschema ≥ 4.22`; existing `pynacl` / `pytest` / `ruff` / `mypy --strict`.

## Global Constraints

- `from __future__ import annotations` at top of every Python module.
- Datetimes are ISO 8601 UTC; serialize with `.isoformat()`.
- Memory IDs are content-addressed via existing `compute_memory_id`.
- Audit log MUST NOT include raw memory text (FR-9.6) — only memory IDs.
- `sensitivity = "secret"` memories MUST NOT cross export/MCP boundaries by default.
- `temperature=0` for all LLM calls; deterministic IDs.
- No real LLM call in CI. Tests mock `litellm.completion`; one live-LLM test only when `CONTEXT_CAPITAL_RUN_LIVE_LLM=1`.
- Code passes `ruff check src tests` and `mypy --strict src`.
- TDD discipline: failing test first → run to verify fail → implement → run to verify pass → commit.

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `src/context_capital/ingest/__init__.py` | Re-export types + parsers | T1 |
| `src/context_capital/ingest/types.py` | Canonical Pydantic types | T1 |
| `src/context_capital/ingest/streaming.py` | `ijson`-based reader; size-threshold switch | T2 |
| `src/context_capital/ingest/chatgpt.py` | ChatGPT `conversations.json` → `IngestContext` | T3 |
| `src/context_capital/ingest/claude.py` | Claude data-export → `IngestContext` | T4 |
| `tools/__init__.py` + `tools/anonymize_export.py` | PII-stripping anonymizer | T5 |
| `src/context_capital/storage/sqlite.py` *(modify)* | Add `contexts` + `raw_messages` + `persist_ingest_context` | T6 |
| `src/context_capital/extract/llm.py` | `litellm`-fronted real extractor | T7 |
| `src/context_capital/cli.py` *(modify)* | `cc capture`; `--mock`/`--model` on `cc extract` | T8 |
| `README.md`, `docs/srs.md` *(modify)* | Quickstart + G-1 progress note | T9 |
| `tests/test_ingest_types.py` | Model validation tests | T1 |
| `tests/test_ingest_streaming.py` | Threshold + streaming tests | T2 |
| `tests/test_ingest_chatgpt.py` | Parser + synthetic fixture | T3 |
| `tests/test_ingest_claude.py` | Parser + synthetic fixture | T4 |
| `tests/test_tools_anonymize.py` | Determinism + pattern coverage | T5 |
| `tests/test_storage_contexts.py` | `persist_ingest_context` + idempotency | T6 |
| `tests/test_extract_llm.py` | Mocked `litellm.completion`; chunking, schema drop, dedup | T7 |
| `tests/test_cli_capture.py` | typer CliRunner smoke + idempotency | T8 |
| `tests/fixtures/captures/chatgpt-synthetic.json` | Tiny CI-safe fixture | T3 |
| `tests/fixtures/captures/claude-synthetic.json` | Tiny CI-safe fixture | T4 |

---

### Task 1: Canonical ingest types

**Files:**
- Create: `src/context_capital/ingest/__init__.py`
- Create: `src/context_capital/ingest/types.py`
- Create: `tests/test_ingest_types.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `class IngestRole(StrEnum)`: `USER`, `ASSISTANT`, `TOOL`, `SYSTEM`, `OTHER`
  - `class IngestMessage(BaseModel)`: `seq: int (>=0)`, `role: IngestRole`, `content: str`, `created_at: datetime | None`, `vendor_message_id: str | None`
  - `class IngestContext(BaseModel)`: `vendor: str`, `vendor_conversation_id: str`, `title: str | None`, `captured_at: datetime`, `source_file_hash: str`, `messages: list[IngestMessage]`

- [ ] **Step 1.1: Write failing test `tests/test_ingest_types.py`**

```python
"""Tests for ingest canonical types."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from context_capital.ingest.types import IngestContext, IngestMessage, IngestRole


def _now() -> datetime:
    return datetime(2026, 6, 22, 10, 0, 0, tzinfo=timezone.utc)


def test_ingest_message_minimal() -> None:
    m = IngestMessage(seq=0, role=IngestRole.USER, content="hello")
    assert m.seq == 0
    assert m.role == "user"
    assert m.created_at is None


def test_ingest_message_negative_seq_rejected() -> None:
    with pytest.raises(ValidationError):
        IngestMessage(seq=-1, role=IngestRole.USER, content="x")


def test_ingest_message_extra_field_forbidden() -> None:
    with pytest.raises(ValidationError):
        IngestMessage.model_validate(
            {"seq": 0, "role": "user", "content": "x", "extra": "nope"}
        )


def test_ingest_message_unknown_role_rejected() -> None:
    with pytest.raises(ValidationError):
        IngestMessage.model_validate({"seq": 0, "role": "bot", "content": "x"})


def test_ingest_context_minimal() -> None:
    ctx = IngestContext(
        vendor="chatgpt",
        vendor_conversation_id="conv_abc",
        captured_at=_now(),
        source_file_hash="a" * 64,
        messages=[],
    )
    assert ctx.vendor == "chatgpt"
    assert ctx.messages == []
    assert ctx.title is None


def test_ingest_context_with_messages() -> None:
    ctx = IngestContext(
        vendor="claude",
        vendor_conversation_id="conv_xyz",
        title="Project planning",
        captured_at=_now(),
        source_file_hash="b" * 64,
        messages=[
            IngestMessage(seq=0, role=IngestRole.USER, content="hi"),
            IngestMessage(seq=1, role=IngestRole.ASSISTANT, content="hello"),
        ],
    )
    assert len(ctx.messages) == 2
    assert ctx.messages[1].role == IngestRole.ASSISTANT


def test_ingest_context_extra_field_forbidden() -> None:
    with pytest.raises(ValidationError):
        IngestContext.model_validate({
            "vendor": "chatgpt",
            "vendor_conversation_id": "x",
            "captured_at": _now().isoformat(),
            "source_file_hash": "c" * 64,
            "messages": [],
            "extra": "nope",
        })
```

- [ ] **Step 1.2: Run — verify failure**

```bash
source .venv/bin/activate
pytest tests/test_ingest_types.py -v
```

Expected: ImportError on `context_capital.ingest.types`.

- [ ] **Step 1.3: Write `src/context_capital/ingest/types.py`**

```python
"""Canonical ingest types — vendor-blind shape produced by ingest adapters
and consumed by the extractor.
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class IngestRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    SYSTEM = "system"
    OTHER = "other"


class IngestMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seq: int = Field(ge=0)
    role: IngestRole
    content: str
    created_at: datetime | None = None
    vendor_message_id: str | None = None


class IngestContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vendor: str
    vendor_conversation_id: str
    title: str | None = None
    captured_at: datetime
    source_file_hash: str
    messages: list[IngestMessage] = Field(default_factory=list)
```

- [ ] **Step 1.4: Write `src/context_capital/ingest/__init__.py`**

```python
"""Ingest package — vendor-specific adapters that produce canonical IngestContexts."""
from __future__ import annotations

from context_capital.ingest.types import IngestContext, IngestMessage, IngestRole

__all__ = ["IngestContext", "IngestMessage", "IngestRole"]
```

- [ ] **Step 1.5: Run — verify pass**

```bash
pytest tests/test_ingest_types.py -v
```

Expected: 7 passed.

- [ ] **Step 1.6: Lint + type-check**

```bash
ruff check src/context_capital/ingest tests/test_ingest_types.py
mypy --strict src/context_capital/ingest
```

Expected: clean.

- [ ] **Step 1.7: Commit**

```bash
git add src/context_capital/ingest/__init__.py src/context_capital/ingest/types.py tests/test_ingest_types.py
git commit -m "feat(ingest): canonical IngestContext / IngestMessage / IngestRole types"
```

---

### Task 2: Streaming reader

**Files:**
- Modify: `pyproject.toml` (add `ijson>=3.3` to `dependencies`)
- Create: `src/context_capital/ingest/streaming.py`
- Create: `tests/test_ingest_streaming.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `DEFAULT_STREAM_THRESHOLD: int`, `should_stream(path)`, `stream_top_level_array(path)`, `load_all(path)`, `iter_items(path)`.

- [ ] **Step 2.1: Add ijson dependency**

In `pyproject.toml`, locate `dependencies` and insert `"ijson>=3.3",` so the block reads:

```toml
dependencies = [
    "pydantic>=2.7",
    "jsonschema>=4.22",
    "rfc8785>=0.1.4",
    "ijson>=3.3",
    "pynacl>=1.5",
    "argon2-cffi>=23.1",
    "typer>=0.12",
    "rich>=13.7",
    "mcp>=1.0",
    "anyio>=4.4",
]
```

Then install:

```bash
pip install -e ".[dev]"
```

- [ ] **Step 2.2: Write failing test `tests/test_ingest_streaming.py`**

```python
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
```

- [ ] **Step 2.3: Run — verify failure**

```bash
pytest tests/test_ingest_streaming.py -v
```

Expected: ImportError on `context_capital.ingest.streaming`.

- [ ] **Step 2.4: Write `src/context_capital/ingest/streaming.py`**

```python
"""Streaming JSON reader for large vendor exports."""
from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import ijson

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
```

- [ ] **Step 2.5: Run — verify pass**

```bash
pytest tests/test_ingest_streaming.py -v
```

Expected: 6 passed.

- [ ] **Step 2.6: Lint + type-check**

```bash
ruff check src/context_capital/ingest tests/test_ingest_streaming.py
mypy --strict src/context_capital/ingest
```

Expected: clean.

- [ ] **Step 2.7: Commit**

```bash
git add pyproject.toml src/context_capital/ingest/streaming.py tests/test_ingest_streaming.py
git commit -m "feat(ingest): ijson-backed streaming reader with size threshold"
```

---

### Task 3: ChatGPT export parser

**Files:**
- Create: `src/context_capital/ingest/chatgpt.py`
- Create: `tests/fixtures/captures/chatgpt-synthetic.json`
- Create: `tests/test_ingest_chatgpt.py`
- Modify: `src/context_capital/ingest/__init__.py` (re-export)

**Interfaces:**
- Consumes: `IngestContext`, `IngestMessage`, `IngestRole`, `iter_items`.
- Produces: `def parse_chatgpt_export(path: Path) -> Iterator[IngestContext]`.

- [ ] **Step 3.1: Write fixture `tests/fixtures/captures/chatgpt-synthetic.json`**

```json
[
  {
    "id": "conv_a1b2c3",
    "title": "Project planning",
    "create_time": 1717372800.0,
    "mapping": {
      "node-1": {
        "id": "node-1",
        "parent": null,
        "children": ["node-2"],
        "message": null
      },
      "node-2": {
        "id": "node-2",
        "parent": "node-1",
        "children": ["node-3"],
        "message": {
          "id": "msg-1",
          "author": {"role": "user", "name": null},
          "create_time": 1717372900.0,
          "content": {"content_type": "text", "parts": ["I prefer PyTorch for ML."]}
        }
      },
      "node-3": {
        "id": "node-3",
        "parent": "node-2",
        "children": ["node-4"],
        "message": {
          "id": "msg-2",
          "author": {"role": "assistant", "name": null},
          "create_time": 1717372950.0,
          "content": {"content_type": "text", "parts": ["Good choice."]}
        }
      },
      "node-4": {
        "id": "node-4",
        "parent": "node-3",
        "children": [],
        "message": {
          "id": "msg-3",
          "author": {"role": "tool", "name": "web_search"},
          "create_time": 1717372960.0,
          "content": {"content_type": "text", "parts": ["[search result]"]}
        }
      }
    }
  },
  {
    "id": "conv_d4e5f6",
    "title": "Empty conversation",
    "create_time": 1717400000.0,
    "mapping": {
      "node-x": {
        "id": "node-x",
        "parent": null,
        "children": [],
        "message": null
      }
    }
  }
]
```

- [ ] **Step 3.2: Write failing test `tests/test_ingest_chatgpt.py`**

```python
"""Tests for ChatGPT export parser."""
from __future__ import annotations

from pathlib import Path

import pytest

from context_capital.ingest.chatgpt import parse_chatgpt_export
from context_capital.ingest.types import IngestRole


@pytest.fixture
def fixture_path() -> Path:
    return Path(__file__).parent / "fixtures" / "captures" / "chatgpt-synthetic.json"


def test_parses_synthetic_fixture(fixture_path: Path) -> None:
    contexts = list(parse_chatgpt_export(fixture_path))
    assert len(contexts) == 2
    assert contexts[0].vendor == "chatgpt"
    assert contexts[0].vendor_conversation_id == "conv_a1b2c3"
    assert contexts[0].title == "Project planning"


def test_walks_mapping_in_node_order(fixture_path: Path) -> None:
    ctx = next(parse_chatgpt_export(fixture_path))
    assert [m.seq for m in ctx.messages] == [0, 1, 2]
    assert ctx.messages[0].role == IngestRole.USER
    assert ctx.messages[1].role == IngestRole.ASSISTANT
    assert ctx.messages[2].role == IngestRole.TOOL


def test_concatenates_content_parts(fixture_path: Path) -> None:
    ctx = next(parse_chatgpt_export(fixture_path))
    assert ctx.messages[0].content == "I prefer PyTorch for ML."


def test_skips_conversations_with_no_messages(fixture_path: Path) -> None:
    contexts = list(parse_chatgpt_export(fixture_path))
    assert contexts[1].vendor_conversation_id == "conv_d4e5f6"
    assert contexts[1].messages == []


def test_file_hash_is_deterministic(fixture_path: Path) -> None:
    a = list(parse_chatgpt_export(fixture_path))
    b = list(parse_chatgpt_export(fixture_path))
    assert a[0].source_file_hash == b[0].source_file_hash
    assert len(a[0].source_file_hash) == 64


def test_created_at_decoded_from_unix_epoch(fixture_path: Path) -> None:
    ctx = next(parse_chatgpt_export(fixture_path))
    assert ctx.messages[0].created_at is not None
    assert ctx.messages[0].created_at.year == 2024


def test_vendor_message_id_preserved(fixture_path: Path) -> None:
    ctx = next(parse_chatgpt_export(fixture_path))
    assert ctx.messages[0].vendor_message_id == "msg-1"
```

- [ ] **Step 3.3: Run — verify failure**

```bash
pytest tests/test_ingest_chatgpt.py -v
```

Expected: ImportError on `context_capital.ingest.chatgpt`.

- [ ] **Step 3.4: Write `src/context_capital/ingest/chatgpt.py`**

```python
"""ChatGPT `conversations.json` parser → IngestContext stream.

ChatGPT's export shape is an array of conversation objects. Each conversation
has a `mapping` dict that forms a tree of message nodes (parent / children
links). We walk the tree depth-first from the root (parent=null) in node
order, emitting IngestMessages for nodes whose `message.author.role` is one
of {user, assistant, tool, system}.
"""
from __future__ import annotations

import hashlib
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from context_capital.ingest.streaming import iter_items
from context_capital.ingest.types import IngestContext, IngestMessage, IngestRole

_VALID_ROLES: frozenset[str] = frozenset(r.value for r in IngestRole if r != IngestRole.OTHER)


def parse_chatgpt_export(path: Path) -> Iterator[IngestContext]:
    """Yield one IngestContext per conversation in a ChatGPT data export."""
    file_hash = _sha256_file(path)
    captured = datetime.now(timezone.utc)
    for conv in iter_items(path):
        yield _conversation_to_context(conv, file_hash, captured)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _conversation_to_context(
    conv: dict[str, Any], file_hash: str, captured_at: datetime
) -> IngestContext:
    conv_id = str(conv.get("id") or conv.get("conversation_id") or "unknown")
    title_raw = conv.get("title")
    title = title_raw if isinstance(title_raw, str) and title_raw else None
    mapping = conv.get("mapping")
    messages: list[IngestMessage] = []
    if isinstance(mapping, dict):
        messages = list(_walk_mapping(mapping))
    return IngestContext(
        vendor="chatgpt",
        vendor_conversation_id=conv_id,
        title=title,
        captured_at=captured_at,
        source_file_hash=file_hash,
        messages=messages,
    )


def _walk_mapping(mapping: dict[str, Any]) -> Iterator[IngestMessage]:
    root_id: str | None = None
    for node_id, node in mapping.items():
        if isinstance(node, dict) and node.get("parent") is None:
            root_id = node_id
            break
    if root_id is None:
        return
    seq = 0
    stack: list[str] = [root_id]
    while stack:
        nid = stack.pop()
        node = mapping.get(nid)
        if not isinstance(node, dict):
            continue
        msg = node.get("message")
        if isinstance(msg, dict):
            im = _message_to_ingest(msg, seq)
            if im is not None:
                yield im
                seq += 1
        children = node.get("children")
        if isinstance(children, list):
            for c in reversed(children):
                if isinstance(c, str):
                    stack.append(c)


def _message_to_ingest(msg: dict[str, Any], seq: int) -> IngestMessage | None:
    author = msg.get("author")
    if not isinstance(author, dict):
        return None
    role = author.get("role")
    if role not in _VALID_ROLES:
        return None
    text = _extract_text(msg.get("content"))
    if not text:
        return None
    created_at = _parse_create_time(msg.get("create_time"))
    vmid = msg.get("id")
    return IngestMessage(
        seq=seq,
        role=IngestRole(role),
        content=text,
        created_at=created_at,
        vendor_message_id=str(vmid) if isinstance(vmid, str) else None,
    )


def _extract_text(content: Any) -> str:
    if not isinstance(content, dict):
        return ""
    parts = content.get("parts")
    if not isinstance(parts, list):
        return ""
    chunks: list[str] = []
    for part in parts:
        if isinstance(part, str):
            chunks.append(part)
        else:
            chunks.append("[non-text part]")
    return "".join(chunks).strip()


def _parse_create_time(raw: Any) -> datetime | None:
    if isinstance(raw, (int, float)):
        return datetime.fromtimestamp(float(raw), tz=timezone.utc)
    return None
```

- [ ] **Step 3.5: Update `src/context_capital/ingest/__init__.py`**

```python
"""Ingest package — vendor-specific adapters that produce canonical IngestContexts."""
from __future__ import annotations

from context_capital.ingest.chatgpt import parse_chatgpt_export
from context_capital.ingest.types import IngestContext, IngestMessage, IngestRole

__all__ = ["IngestContext", "IngestMessage", "IngestRole", "parse_chatgpt_export"]
```

- [ ] **Step 3.6: Run — verify pass**

```bash
pytest tests/test_ingest_chatgpt.py -v
```

Expected: 7 passed.

- [ ] **Step 3.7: Lint + type-check**

```bash
ruff check src/context_capital/ingest tests/test_ingest_chatgpt.py
mypy --strict src/context_capital/ingest
```

Expected: clean.

- [ ] **Step 3.8: Commit**

```bash
git add src/context_capital/ingest/chatgpt.py src/context_capital/ingest/__init__.py tests/fixtures/captures/chatgpt-synthetic.json tests/test_ingest_chatgpt.py
git commit -m "feat(ingest): ChatGPT conversations.json parser"
```

---

### Task 4: Claude export parser

**Files:**
- Create: `src/context_capital/ingest/claude.py`
- Create: `tests/fixtures/captures/claude-synthetic.json`
- Create: `tests/test_ingest_claude.py`
- Modify: `src/context_capital/ingest/__init__.py` (re-export)

**Interfaces:**
- Consumes: `IngestContext`, `IngestMessage`, `IngestRole`, `iter_items`.
- Produces: `def parse_claude_export(path: Path) -> Iterator[IngestContext]`.

- [ ] **Step 4.1: Write fixture `tests/fixtures/captures/claude-synthetic.json`**

```json
[
  {
    "uuid": "conv_xyz789",
    "name": "Project planning",
    "created_at": "2025-01-01T00:00:00Z",
    "updated_at": "2025-01-01T00:30:00Z",
    "chat_messages": [
      {
        "uuid": "msg-uuid-1",
        "sender": "human",
        "created_at": "2025-01-01T00:01:00Z",
        "text": "I prefer PyTorch for ML.",
        "content": [
          {"type": "text", "text": "I prefer PyTorch for ML."}
        ]
      },
      {
        "uuid": "msg-uuid-2",
        "sender": "assistant",
        "created_at": "2025-01-01T00:01:05Z",
        "text": "Got it!",
        "content": [
          {"type": "text", "text": "Got it!"},
          {"type": "tool_use", "name": "web_search"}
        ]
      },
      {
        "uuid": "msg-uuid-3",
        "sender": "human",
        "created_at": "2025-01-01T00:02:00Z",
        "text": "",
        "content": []
      }
    ]
  }
]
```

- [ ] **Step 4.2: Write failing test `tests/test_ingest_claude.py`**

```python
"""Tests for Claude export parser."""
from __future__ import annotations

from pathlib import Path

import pytest

from context_capital.ingest.claude import parse_claude_export
from context_capital.ingest.types import IngestRole


@pytest.fixture
def fixture_path() -> Path:
    return Path(__file__).parent / "fixtures" / "captures" / "claude-synthetic.json"


def test_parses_synthetic_fixture(fixture_path: Path) -> None:
    contexts = list(parse_claude_export(fixture_path))
    assert len(contexts) == 1
    assert contexts[0].vendor == "claude"
    assert contexts[0].vendor_conversation_id == "conv_xyz789"
    assert contexts[0].title == "Project planning"


def test_human_sender_maps_to_user(fixture_path: Path) -> None:
    ctx = next(parse_claude_export(fixture_path))
    assert ctx.messages[0].role == IngestRole.USER


def test_assistant_sender_preserved(fixture_path: Path) -> None:
    ctx = next(parse_claude_export(fixture_path))
    assert ctx.messages[1].role == IngestRole.ASSISTANT


def test_tool_use_block_emitted_as_marker(fixture_path: Path) -> None:
    ctx = next(parse_claude_export(fixture_path))
    assert "[tool_use: web_search]" in ctx.messages[1].content


def test_empty_text_and_content_skipped(fixture_path: Path) -> None:
    ctx = next(parse_claude_export(fixture_path))
    assert len(ctx.messages) == 2


def test_file_hash_is_deterministic(fixture_path: Path) -> None:
    a = list(parse_claude_export(fixture_path))
    b = list(parse_claude_export(fixture_path))
    assert a[0].source_file_hash == b[0].source_file_hash
    assert len(a[0].source_file_hash) == 64


def test_created_at_parsed_from_iso8601(fixture_path: Path) -> None:
    ctx = next(parse_claude_export(fixture_path))
    assert ctx.messages[0].created_at is not None
    assert ctx.messages[0].created_at.year == 2025
```

- [ ] **Step 4.3: Run — verify failure**

```bash
pytest tests/test_ingest_claude.py -v
```

Expected: ImportError on `context_capital.ingest.claude`.

- [ ] **Step 4.4: Write `src/context_capital/ingest/claude.py`**

```python
"""Claude data-export JSON parser → IngestContext stream.

Claude's export is an array of conversations. Each has a flat
`chat_messages` list. Each message has a `sender` (human/assistant) and
either a top-level `text` field or a `content` array of typed blocks
(text, tool_use, etc.).
"""
from __future__ import annotations

import hashlib
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from context_capital.ingest.streaming import iter_items
from context_capital.ingest.types import IngestContext, IngestMessage, IngestRole

_SENDER_TO_ROLE: dict[str, IngestRole] = {
    "human": IngestRole.USER,
    "user": IngestRole.USER,
    "assistant": IngestRole.ASSISTANT,
}


def parse_claude_export(path: Path) -> Iterator[IngestContext]:
    """Yield one IngestContext per conversation in a Claude data export."""
    file_hash = _sha256_file(path)
    captured = datetime.now(timezone.utc)
    for conv in iter_items(path):
        yield _conversation_to_context(conv, file_hash, captured)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _conversation_to_context(
    conv: dict[str, Any], file_hash: str, captured_at: datetime
) -> IngestContext:
    conv_id = str(conv.get("uuid") or conv.get("id") or "unknown")
    title_raw = conv.get("name") or conv.get("title")
    title = title_raw if isinstance(title_raw, str) and title_raw else None
    chat_messages = conv.get("chat_messages")
    messages: list[IngestMessage] = []
    if isinstance(chat_messages, list):
        seq = 0
        for raw in chat_messages:
            if not isinstance(raw, dict):
                continue
            im = _message_to_ingest(raw, seq)
            if im is not None:
                messages.append(im)
                seq += 1
    return IngestContext(
        vendor="claude",
        vendor_conversation_id=conv_id,
        title=title,
        captured_at=captured_at,
        source_file_hash=file_hash,
        messages=messages,
    )


def _message_to_ingest(raw: dict[str, Any], seq: int) -> IngestMessage | None:
    sender = raw.get("sender")
    if not isinstance(sender, str):
        return None
    role = _SENDER_TO_ROLE.get(sender)
    if role is None:
        return None
    text = _extract_text(raw)
    if not text:
        return None
    created_at = _parse_iso8601(raw.get("created_at"))
    vmid = raw.get("uuid")
    return IngestMessage(
        seq=seq,
        role=role,
        content=text,
        created_at=created_at,
        vendor_message_id=str(vmid) if isinstance(vmid, str) else None,
    )


def _extract_text(raw: dict[str, Any]) -> str:
    content = raw.get("content")
    if isinstance(content, list) and content:
        parts: list[str] = []
        for part in content:
            if not isinstance(part, dict):
                continue
            ptype = part.get("type")
            if ptype == "text":
                txt = part.get("text")
                if isinstance(txt, str):
                    parts.append(txt)
            elif isinstance(ptype, str):
                name = part.get("name") or ptype
                parts.append(f"[{ptype}: {name}]")
        return "\n".join(p for p in parts if p).strip()
    top_text = raw.get("text")
    if isinstance(top_text, str):
        return top_text.strip()
    return ""


def _parse_iso8601(raw: Any) -> datetime | None:
    if not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
```

- [ ] **Step 4.5: Update `src/context_capital/ingest/__init__.py`**

```python
"""Ingest package — vendor-specific adapters that produce canonical IngestContexts."""
from __future__ import annotations

from context_capital.ingest.chatgpt import parse_chatgpt_export
from context_capital.ingest.claude import parse_claude_export
from context_capital.ingest.types import IngestContext, IngestMessage, IngestRole

__all__ = [
    "IngestContext",
    "IngestMessage",
    "IngestRole",
    "parse_chatgpt_export",
    "parse_claude_export",
]
```

- [ ] **Step 4.6: Run — verify pass**

```bash
pytest tests/test_ingest_claude.py -v
```

Expected: 7 passed.

- [ ] **Step 4.7: Lint + type-check**

```bash
ruff check src/context_capital/ingest tests/test_ingest_claude.py
mypy --strict src/context_capital/ingest
```

Expected: clean.

- [ ] **Step 4.8: Commit**

```bash
git add src/context_capital/ingest/claude.py src/context_capital/ingest/__init__.py tests/fixtures/captures/claude-synthetic.json tests/test_ingest_claude.py
git commit -m "feat(ingest): Claude data-export parser"
```

---

### Task 5: Anonymizer tool

**Files:**
- Create: `tools/__init__.py` (empty)
- Create: `tools/anonymize_export.py`
- Create: `tests/test_tools_anonymize.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `dataclass AnonymizeReport`, `def anonymize(*, vendor, in_path, out_path, seed=None, aggressive=False) -> AnonymizeReport`, `def main(argv=None) -> int`.

- [ ] **Step 5.1: Write failing test `tests/test_tools_anonymize.py`**

```python
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
```

- [ ] **Step 5.2: Run — verify failure**

```bash
pytest tests/test_tools_anonymize.py -v
```

Expected: ImportError on `tools.anonymize_export`.

- [ ] **Step 5.3: Write `tools/__init__.py`** (empty)

```python
```

- [ ] **Step 5.4: Write `tools/anonymize_export.py`**

```python
"""Deterministic PII-stripping anonymizer for ChatGPT and Claude exports.

CLI: python -m tools.anonymize_export --vendor chatgpt --in real.json --out anon.json --seed 42
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

COMMON_NAMES: frozenset[str] = frozenset({
    "James", "John", "Robert", "Michael", "William", "David", "Joseph", "Charles",
    "Thomas", "Daniel", "Matthew", "Anthony", "Mark", "Donald", "Steven", "Paul",
    "Andrew", "Joshua", "Kenneth", "Kevin", "Brian", "George", "Edward", "Ronald",
    "Timothy", "Jason", "Jeffrey", "Ryan", "Jacob", "Gary", "Nicholas", "Eric",
    "Stephen", "Jonathan", "Larry", "Justin", "Scott", "Brandon", "Frank", "Benjamin",
    "Gregory", "Samuel", "Raymond", "Patrick", "Alexander", "Jack", "Dennis", "Jerry",
    "Tyler", "Aaron",
    "Mary", "Patricia", "Jennifer", "Linda", "Elizabeth", "Barbara",
    "Susan", "Jessica", "Sarah", "Karen", "Nancy", "Lisa", "Margaret", "Betty",
    "Sandra", "Ashley", "Kimberly", "Emily", "Donna", "Michelle", "Carol", "Amanda",
    "Melissa", "Deborah", "Stephanie", "Rebecca", "Sharon", "Laura", "Cynthia", "Amy",
    "Kathleen", "Angela", "Shirley", "Brenda", "Emma", "Anna", "Pamela", "Nicole",
    "Samantha", "Katherine", "Christine", "Helen", "Debra", "Rachel", "Carolyn", "Janet",
    "Maria", "Catherine", "Heather", "Diane", "Olivia", "Julie", "Joyce", "Victoria",
    "Ruth", "Virginia", "Lauren", "Kelly", "Christina", "Joan", "Evelyn", "Judith",
    "Andrea", "Hannah", "Megan", "Cheryl", "Jacqueline", "Martha",
})

_STOP: frozenset[str] = frozenset({
    "This", "That", "With", "From", "They", "What", "When", "Where", "Which", "While",
    "After", "Before", "About", "Because", "Could", "Would", "Should", "There", "These",
    "Their", "Them", "Than", "Then", "Also", "Just", "Like", "More", "Most", "Some",
    "Other", "Such", "Into", "Over", "Onto", "Upon", "Being", "Been", "Very",
    "Even", "Each", "Every", "Really", "Quite", "Always", "Never", "Often", "Again",
    "Still", "Said", "Says", "Make", "Made", "Done", "Take", "Took", "Goes", "Gone",
    "Have", "Will", "Want",
})

_EMAIL_RE = re.compile(r"\b[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+\b")
_URL_RE = re.compile(r"https?://[^\s\"'<>)]+", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?:\+?1[\s.\-]?)?\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}\b")
_API_KEY_RES: dict[str, re.Pattern[str]] = {
    "openai": re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    "anthropic": re.compile(r"\bsk-ant-[A-Za-z0-9\-]{20,}\b"),
    "aws": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "github": re.compile(r"\bghp_[A-Za-z0-9]{30,}\b"),
}
_WORD_RE = re.compile(r"\b[A-Za-z][A-Za-z'\-]+\b")


@dataclass
class AnonymizeReport:
    emails_replaced: int = 0
    urls_replaced: int = 0
    phones_replaced: int = 0
    names_replaced: int = 0
    api_keys_detected: int = 0


def anonymize(
    *,
    vendor: str,
    in_path: Path,
    out_path: Path,
    seed: int | None = None,
    aggressive: bool = False,
) -> AnonymizeReport:
    if vendor not in ("chatgpt", "claude"):
        raise ValueError(f"unsupported vendor: {vendor}")
    actual_seed = seed if seed is not None else int.from_bytes(os.urandom(8), "big")
    rng = random.Random(actual_seed)
    raw: Any = json.loads(in_path.read_text())
    report = AnonymizeReport()
    out = _walk(raw, rng, report, aggressive=aggressive)
    out_path.write_text(json.dumps(out, indent=2))
    if seed is not None:
        out_path.with_suffix(out_path.suffix + ".seed.txt").write_text(str(seed))
    return report


def _walk(obj: Any, rng: random.Random, report: AnonymizeReport, *, aggressive: bool) -> Any:
    if isinstance(obj, str):
        return _scrub_string(obj, rng, report, aggressive=aggressive)
    if isinstance(obj, dict):
        return {k: _walk(v, rng, report, aggressive=aggressive) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_walk(item, rng, report, aggressive=aggressive) for item in obj]
    return obj


def _scrub_string(s: str, rng: random.Random, report: AnonymizeReport, *, aggressive: bool) -> str:
    for regex in _API_KEY_RES.values():
        hits = len(regex.findall(s))
        if hits:
            report.api_keys_detected += hits
            s = regex.sub("<api-key>", s)

    def email_sub(_m: re.Match[str]) -> str:
        report.emails_replaced += 1
        return f"<email-{rng.randint(1, 9999)}@example.invalid>"

    s = _EMAIL_RE.sub(email_sub, s)

    def url_sub(m: re.Match[str]) -> str:
        report.urls_replaced += 1
        return f"https://example.invalid/{abs(hash(m.group(0))) % 10**8:08x}"

    s = _URL_RE.sub(url_sub, s)

    def phone_sub(_m: re.Match[str]) -> str:
        report.phones_replaced += 1
        return f"<phone-{rng.randint(1, 9999)}>"

    s = _PHONE_RE.sub(phone_sub, s)

    def word_sub(m: re.Match[str]) -> str:
        word = m.group(0)
        cap = word.capitalize()
        if cap in COMMON_NAMES:
            report.names_replaced += 1
            return f"Person{rng.randint(1, 999)}"
        if aggressive and len(word) >= 4 and word[0].isupper() and cap not in _STOP:
            return f"Project{rng.randint(1, 999)}"
        return word

    s = _WORD_RE.sub(word_sub, s)
    return s


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="anonymize-export")
    p.add_argument("--vendor", required=True, choices=["chatgpt", "claude"])
    p.add_argument("--in", dest="in_path", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--aggressive", action="store_true")
    args = p.parse_args(argv)
    report = anonymize(
        vendor=args.vendor,
        in_path=args.in_path,
        out_path=args.out,
        seed=args.seed,
        aggressive=args.aggressive,
    )
    sys.stdout.write(f"Anonymized -> {args.out}\n")
    sys.stdout.write(
        f"  emails: {report.emails_replaced}  urls: {report.urls_replaced}  "
        f"phones: {report.phones_replaced}  names: {report.names_replaced}  "
        f"api-keys: {report.api_keys_detected}\n"
    )
    if report.api_keys_detected:
        sys.stderr.write("WARNING: API keys detected and redacted. Investigate the source.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5.5: Run — verify pass**

```bash
pytest tests/test_tools_anonymize.py -v
```

Expected: 7 passed.

- [ ] **Step 5.6: Lint + type-check**

```bash
ruff check tools tests/test_tools_anonymize.py
mypy --strict tools
```

Expected: clean.

- [ ] **Step 5.7: Commit**

```bash
git add tools/ tests/test_tools_anonymize.py
git commit -m "feat(tools): anonymize_export — deterministic PII stripper"
```

---

### Task 6: Storage extension — contexts + raw_messages

**Files:**
- Modify: `src/context_capital/storage/sqlite.py`
- Create: `tests/test_storage_contexts.py`

**Interfaces:**
- Consumes: `IngestContext`.
- Produces: `def persist_ingest_context(self, ic, *, subject_id, actor="system") -> str`, `def get_context_by_unique(self, subject_id, source_file_hash, vendor_conversation_id) -> dict | None`. New tables: `contexts`, `raw_messages`.

- [ ] **Step 6.1: Write failing test `tests/test_storage_contexts.py`**

```python
"""Tests for Store.persist_ingest_context."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from context_capital.ingest.types import IngestContext, IngestMessage, IngestRole
from context_capital.storage import Store


def _now() -> datetime:
    return datetime(2026, 6, 22, 10, 0, 0, tzinfo=timezone.utc)


def _ic(messages_count: int = 2) -> IngestContext:
    return IngestContext(
        vendor="chatgpt",
        vendor_conversation_id="conv_abc",
        title="t",
        captured_at=_now(),
        source_file_hash="a" * 64,
        messages=[
            IngestMessage(
                seq=i,
                role=IngestRole.USER if i % 2 == 0 else IngestRole.ASSISTANT,
                content=f"m{i}",
            )
            for i in range(messages_count)
        ],
    )


def _subject() -> str:
    return "did:key:zABC"


def test_persists_context_and_messages(tmp_path: Path) -> None:
    db = tmp_path / "store.db"
    with Store(db) as store:
        store.ensure_subject(_subject())
        cid = store.persist_ingest_context(_ic(messages_count=3), subject_id=_subject())
        assert isinstance(cid, str) and len(cid) > 0
        row = store.get_context_by_unique(_subject(), "a" * 64, "conv_abc")
        assert row is not None
        assert row["source_vendor"] == "chatgpt"


def test_idempotent_on_same_file_and_conversation(tmp_path: Path) -> None:
    db = tmp_path / "store.db"
    with Store(db) as store:
        store.ensure_subject(_subject())
        cid1 = store.persist_ingest_context(_ic(), subject_id=_subject())
        cid2 = store.persist_ingest_context(_ic(), subject_id=_subject())
        assert cid1 == cid2


def test_different_file_hash_creates_new_context(tmp_path: Path) -> None:
    db = tmp_path / "store.db"
    with Store(db) as store:
        store.ensure_subject(_subject())
        ic1 = _ic()
        ic2 = _ic().model_copy(update={"source_file_hash": "b" * 64})
        cid1 = store.persist_ingest_context(ic1, subject_id=_subject())
        cid2 = store.persist_ingest_context(ic2, subject_id=_subject())
        assert cid1 != cid2


def test_writes_audit_entry_for_capture(tmp_path: Path) -> None:
    db = tmp_path / "store.db"
    with Store(db) as store:
        store.ensure_subject(_subject())
        store.persist_ingest_context(_ic(), subject_id=_subject(), actor="test")
        entries = store.audit_log(limit=10)
    assert any(e["action"] == "capture" for e in entries)
```

- [ ] **Step 6.2: Run — verify failure**

```bash
pytest tests/test_storage_contexts.py -v
```

Expected: AttributeError on `Store.persist_ingest_context` (method not implemented).

- [ ] **Step 6.3: Modify `src/context_capital/storage/sqlite.py`**

Replace the `SCHEMA_DDL` constant with the version below (adds `contexts` + `raw_messages` at the end; existing statements unchanged):

```python
SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS subjects (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK (type IN ('person','organization','agent')),
    display_name TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL REFERENCES subjects(id),
    kind TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object_value TEXT NOT NULL,
    object_type TEXT,
    confidence REAL NOT NULL,
    sensitivity TEXT NOT NULL CHECK (sensitivity IN ('public','work','personal','secret')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS memories_subject_kind_idx ON memories (subject_id, kind);
CREATE INDEX IF NOT EXISTS memories_subject_predicate_idx ON memories (subject_id, predicate);

CREATE TABLE IF NOT EXISTS provenance (
    memory_id TEXT PRIMARY KEY REFERENCES memories(id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    extracted_at TEXT NOT NULL,
    raw_excerpt TEXT,
    imported INTEGER NOT NULL DEFAULT 0,
    import_source TEXT,
    model TEXT,
    sanitization_trace TEXT
);

CREATE TABLE IF NOT EXISTS audit_log_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL DEFAULT (datetime('now')),
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    subject_id TEXT,
    details TEXT NOT NULL DEFAULT '{}',
    outcome TEXT NOT NULL CHECK (outcome IN ('success','denied','error'))
);

CREATE TABLE IF NOT EXISTS contexts (
    id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL REFERENCES subjects(id),
    source_vendor TEXT NOT NULL,
    source_file_hash TEXT NOT NULL,
    vendor_conversation_id TEXT NOT NULL,
    title TEXT,
    captured_at TEXT NOT NULL,
    UNIQUE (subject_id, source_file_hash, vendor_conversation_id)
);
CREATE INDEX IF NOT EXISTS contexts_subject_idx ON contexts (subject_id);

CREATE TABLE IF NOT EXISTS raw_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    context_id TEXT NOT NULL REFERENCES contexts(id) ON DELETE CASCADE,
    seq INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT,
    vendor_message_id TEXT,
    UNIQUE (context_id, seq)
);
CREATE INDEX IF NOT EXISTS raw_messages_context_idx ON raw_messages (context_id);
"""
```

Add the `TYPE_CHECKING` import (top of the file, near `from typing import Any`):

```python
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from context_capital.ingest.types import IngestContext
```

Add these two methods to the `Store` class (after `audit_log`):

```python
    def persist_ingest_context(
        self,
        ic: "IngestContext",
        *,
        subject_id: str,
        actor: str = "system",
    ) -> str:
        """Persist an IngestContext + its messages. Idempotent on
        (subject_id, source_file_hash, vendor_conversation_id). Returns the
        context UUID (existing one if duplicate).
        """
        import uuid as _uuid

        c = self._require_conn()
        existing = c.execute(
            "SELECT id FROM contexts WHERE subject_id = ? AND source_file_hash = ? "
            "AND vendor_conversation_id = ?",
            (subject_id, ic.source_file_hash, ic.vendor_conversation_id),
        ).fetchone()
        if existing is not None:
            return str(existing["id"])
        cid = str(_uuid.uuid4())
        with c:
            c.execute(
                """INSERT INTO contexts (id, subject_id, source_vendor, source_file_hash,
                                          vendor_conversation_id, title, captured_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    cid,
                    subject_id,
                    ic.vendor,
                    ic.source_file_hash,
                    ic.vendor_conversation_id,
                    ic.title,
                    ic.captured_at.isoformat(),
                ),
            )
            for m in ic.messages:
                c.execute(
                    """INSERT INTO raw_messages
                           (context_id, seq, role, content, created_at, vendor_message_id)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        cid,
                        m.seq,
                        str(m.role),
                        m.content,
                        m.created_at.isoformat() if m.created_at else None,
                        m.vendor_message_id,
                    ),
                )
            c.execute(
                "INSERT INTO audit_log_entries (actor, action, subject_id, details, outcome) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    actor,
                    "capture",
                    subject_id,
                    json.dumps(
                        {
                            "context_id": cid,
                            "vendor": ic.vendor,
                            "vendor_conversation_id": ic.vendor_conversation_id,
                            "messages": len(ic.messages),
                        }
                    ),
                    "success",
                ),
            )
        return cid

    def get_context_by_unique(
        self,
        subject_id: str,
        source_file_hash: str,
        vendor_conversation_id: str,
    ) -> dict[str, Any] | None:
        c = self._require_conn()
        row = c.execute(
            "SELECT * FROM contexts WHERE subject_id = ? AND source_file_hash = ? "
            "AND vendor_conversation_id = ?",
            (subject_id, source_file_hash, vendor_conversation_id),
        ).fetchone()
        return dict(row) if row else None
```

- [ ] **Step 6.4: Run — verify pass**

```bash
pytest tests/test_storage_contexts.py tests/test_storage.py -v
```

Expected: 4 new passes + existing 6 storage tests still pass.

- [ ] **Step 6.5: Lint + type-check**

```bash
ruff check src/context_capital/storage tests/test_storage_contexts.py
mypy --strict src/context_capital/storage
```

Expected: clean.

- [ ] **Step 6.6: Commit**

```bash
git add src/context_capital/storage/sqlite.py tests/test_storage_contexts.py
git commit -m "feat(storage): persist_ingest_context with contexts + raw_messages tables"
```

---

### Task 7: LiteLLM-backed extractor

**Files:**
- Modify: `pyproject.toml` (add `litellm>=1.50`)
- Create: `src/context_capital/extract/llm.py`
- Modify: `src/context_capital/extract/__init__.py`
- Create: `tests/test_extract_llm.py`

**Interfaces:**
- Consumes: `IngestContext`, `CONTEXT_PROTOCOL_V0_1_SCHEMA`, `compute_memory_id`, `MemoryKind`, `Sensitivity`.
- Produces: `DEFAULT_MODEL`, `EXTRACTION_SYSTEM_PROMPT`, `def extract_memories(*, subject_id, context, model=DEFAULT_MODEL, prompt_cache=True, chunk_tokens=6000, chunk_overlap_tokens=500, from_chunk=0) -> list[dict[str, Any]]`.

- [ ] **Step 7.1: Add litellm dependency**

Insert `"litellm>=1.50",` after the `ijson` line in `pyproject.toml`. Result:

```toml
dependencies = [
    "pydantic>=2.7",
    "jsonschema>=4.22",
    "rfc8785>=0.1.4",
    "ijson>=3.3",
    "litellm>=1.50",
    "pynacl>=1.5",
    "argon2-cffi>=23.1",
    "typer>=0.12",
    "rich>=13.7",
    "mcp>=1.0",
    "anyio>=4.4",
]
```

Reinstall:

```bash
pip install -e ".[dev]"
```

- [ ] **Step 7.2: Write failing test `tests/test_extract_llm.py`**

```python
"""Tests for the litellm-fronted real extractor (no live API)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pytest

import context_capital.extract.llm as llm_mod
from context_capital.extract.llm import extract_memories
from context_capital.ingest.types import IngestContext, IngestMessage, IngestRole


def _ctx(messages: list[tuple[str, str]]) -> IngestContext:
    return IngestContext(
        vendor="chatgpt",
        vendor_conversation_id="conv_x",
        title="t",
        captured_at=datetime(2026, 6, 22, tzinfo=timezone.utc),
        source_file_hash="a" * 64,
        messages=[
            IngestMessage(seq=i, role=IngestRole(role), content=content)
            for i, (role, content) in enumerate(messages)
        ],
    )


def _mock_response(memories: list[dict[str, Any]]) -> dict[str, Any]:
    return {"choices": [{"message": {"content": json.dumps({"memories": memories})}}]}


def _patch_completion(monkeypatch: pytest.MonkeyPatch, response: dict[str, Any]) -> None:
    monkeypatch.setattr(llm_mod.litellm, "completion", lambda **_kw: response)
    monkeypatch.setattr(llm_mod.litellm, "token_counter", lambda **_kw: 100)


def test_extracts_valid_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_completion(monkeypatch, _mock_response([{
        "kind": "preference",
        "predicate": "prefers",
        "object": {"value": "PyTorch", "type": "tool"},
        "confidence": 0.9,
        "sensitivity": "work",
        "provenance_excerpt": "I prefer PyTorch.",
    }]))
    mems = extract_memories(subject_id="did:key:zABC", context=_ctx([("user", "I prefer PyTorch.")]))
    assert len(mems) == 1
    assert mems[0]["kind"] == "preference"
    assert mems[0]["object"]["value"] == "PyTorch"
    assert mems[0]["provenance"]["source"] == "chatgpt:conv_x"
    assert mems[0]["provenance"]["imported"] is False


def test_drops_invalid_kind(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_completion(monkeypatch, _mock_response([{
        "kind": "opinion",
        "predicate": "thinks",
        "object": {"value": "x"},
        "confidence": 0.5,
        "sensitivity": "work",
    }]))
    mems = extract_memories(subject_id="did:key:zABC", context=_ctx([("user", "I think.")]))
    assert mems == []


def test_drops_missing_required(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_completion(monkeypatch, _mock_response([{
        "kind": "preference",
        "predicate": "prefers",
        "confidence": 0.5,
        "sensitivity": "work",
    }]))
    mems = extract_memories(subject_id="did:key:zABC", context=_ctx([("user", "x")]))
    assert mems == []


def test_confidence_clamped_in_range(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_completion(monkeypatch, _mock_response([{
        "kind": "preference",
        "predicate": "prefers",
        "object": {"value": "x"},
        "confidence": 1.5,
        "sensitivity": "work",
    }]))
    mems = extract_memories(subject_id="did:key:zABC", context=_ctx([("user", "x")]))
    assert len(mems) == 1
    assert mems[0]["confidence"] == 1.0


def test_deduplicates_within_one_call(monkeypatch: pytest.MonkeyPatch) -> None:
    same = {
        "kind": "preference",
        "predicate": "prefers",
        "object": {"value": "PyTorch", "type": "tool"},
        "confidence": 0.9,
        "sensitivity": "work",
        "provenance_excerpt": "x",
    }
    _patch_completion(monkeypatch, _mock_response([same, same, same]))
    mems = extract_memories(subject_id="did:key:zABC", context=_ctx([("user", "x")]))
    assert len(mems) == 1


def test_empty_context_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_completion(monkeypatch, _mock_response([]))
    mems = extract_memories(subject_id="did:key:zABC", context=_ctx([]))
    assert mems == []


def test_invalid_json_from_model_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    bad = {"choices": [{"message": {"content": "not json"}}]}
    monkeypatch.setattr(llm_mod.litellm, "completion", lambda **_kw: bad)
    monkeypatch.setattr(llm_mod.litellm, "token_counter", lambda **_kw: 100)
    mems = extract_memories(subject_id="did:key:zABC", context=_ctx([("user", "x")]))
    assert mems == []


def test_llm_exception_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(**_kw: Any) -> Any:
        raise RuntimeError("api down")
    monkeypatch.setattr(llm_mod.litellm, "completion", boom)
    monkeypatch.setattr(llm_mod.litellm, "token_counter", lambda **_kw: 100)
    mems = extract_memories(subject_id="did:key:zABC", context=_ctx([("user", "x")]))
    assert mems == []
```

- [ ] **Step 7.3: Run — verify failure**

```bash
pytest tests/test_extract_llm.py -v
```

Expected: ImportError on `context_capital.extract.llm`.

- [ ] **Step 7.4: Write `src/context_capital/extract/llm.py`**

```python
"""LiteLLM-fronted memory extractor.

Calls a real LLM (default Anthropic Claude) via litellm with prompt caching
and JSON-mode response_format. Validates returned memories against the
Context Protocol v0.1 schema; drops anything invalid. Deterministic IDs
via the existing compute_memory_id.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import litellm
from jsonschema import Draft202012Validator

from context_capital.ingest.types import IngestContext
from context_capital.schema import (
    CONTEXT_PROTOCOL_V0_1_SCHEMA,
    MemoryKind,
    Sensitivity,
    compute_memory_id,
)

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "anthropic/claude-sonnet-4-5"

EXTRACTION_SYSTEM_PROMPT = """You extract durable, factual long-term memories about a user from a chat conversation.

Output ONLY a JSON object with this exact shape:
{
  "memories": [
    {
      "kind": "preference|fact|decision|project|workflow|skill",
      "predicate": "kebab-case-verb",
      "object": {"value": "...", "type": "optional-type-hint"},
      "confidence": 0.0-1.0,
      "sensitivity": "public|work|personal|secret",
      "provenance_excerpt": "short verbatim quote from the conversation grounding this memory"
    }
  ]
}

Rules:
- Extract only durable facts: preferences, projects, decisions, skills, workflows. Ignore one-time questions and small talk.
- confidence >= 0.85 for explicit statements; <= 0.7 for inferred.
- sensitivity defaults to "work" unless clearly personal/secret.
- Up to 10 memories per chunk. Quality over quantity.
- Output valid JSON only — no prose before or after.
"""


def extract_memories(
    *,
    subject_id: str,
    context: IngestContext,
    model: str = DEFAULT_MODEL,
    prompt_cache: bool = True,
    chunk_tokens: int = 6000,
    chunk_overlap_tokens: int = 500,
    from_chunk: int = 0,
) -> list[dict[str, Any]]:
    """Extract memories from one IngestContext. Resumable via `from_chunk`."""
    chunks = _chunk_messages(context, chunk_tokens, chunk_overlap_tokens)
    if not chunks:
        return []
    memory_schema = CONTEXT_PROTOCOL_V0_1_SCHEMA["properties"]["memories"]["items"]
    validator = Draft202012Validator(memory_schema)
    source = f"{context.vendor}:{context.vendor_conversation_id}"
    now = context.captured_at.isoformat()
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for idx, chunk_text in enumerate(chunks):
        if idx < from_chunk:
            continue
        raw = _call_llm(model=model, chunk_text=chunk_text, prompt_cache=prompt_cache)
        for rm in raw:
            mem = _build_memory(rm, subject_id=subject_id, source=source, now=now, model=model)
            if mem is None:
                continue
            errors = list(validator.iter_errors(mem))
            if errors:
                logger.warning("dropping invalid memory: %s", errors[0].message)
                continue
            if mem["id"] in seen:
                continue
            seen.add(mem["id"])
            out.append(mem)
    return out


def _chunk_messages(ctx: IngestContext, chunk_tokens: int, overlap: int) -> list[str]:
    if not ctx.messages:
        return []
    full = "\n\n".join(f"{m.role.upper()}: {m.content}" for m in ctx.messages)
    if not full.strip():
        return []
    try:
        total_tokens = litellm.token_counter(model=DEFAULT_MODEL, text=full)
    except Exception:  # noqa: BLE001
        total_tokens = max(1, len(full) // 4)
    if total_tokens <= chunk_tokens:
        return [full]
    chars_per_token = max(1, len(full) // max(1, total_tokens))
    window = chunk_tokens * chars_per_token
    step = max(1, (chunk_tokens - overlap) * chars_per_token)
    chunks: list[str] = []
    start = 0
    while start < len(full):
        chunks.append(full[start : start + window])
        start += step
    return chunks


def _call_llm(*, model: str, chunk_text: str, prompt_cache: bool) -> list[dict[str, Any]]:
    system_msg: dict[str, Any] = {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT}
    if prompt_cache and model.startswith("anthropic/"):
        system_msg["cache_control"] = [{"type": "ephemeral"}]
    try:
        response = litellm.completion(
            model=model,
            messages=[system_msg, {"role": "user", "content": chunk_text}],
            temperature=0,
            response_format={"type": "json_object"},
        )
    except Exception as e:  # noqa: BLE001
        logger.error("LLM call failed: %s", e)
        return []
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return []
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        logger.warning("LLM returned invalid JSON")
        return []
    raw_mems = parsed.get("memories") if isinstance(parsed, dict) else None
    if not isinstance(raw_mems, list):
        return []
    return [m for m in raw_mems if isinstance(m, dict)]


def _build_memory(
    raw: dict[str, Any],
    *,
    subject_id: str,
    source: str,
    now: str,
    model: str,
) -> dict[str, Any] | None:
    try:
        kind = raw["kind"]
        predicate = str(raw["predicate"])
        obj = raw["object"]
        obj_val = obj["value"]
        obj_type = obj.get("type") if isinstance(obj, dict) else None
        confidence = float(raw["confidence"])
        sensitivity = str(raw.get("sensitivity", "work"))
        excerpt_raw = raw.get("provenance_excerpt", "")
    except (KeyError, TypeError, ValueError):
        return None
    if kind not in {k.value for k in MemoryKind}:
        return None
    if sensitivity not in {s.value for s in Sensitivity}:
        return None
    confidence = max(0.0, min(1.0, confidence))
    mid = compute_memory_id(
        kind=kind,
        predicate=predicate,
        subject_id=subject_id,
        object_value=obj_val,
        object_type=obj_type,
        sensitivity=sensitivity,
    )
    excerpt = str(excerpt_raw)[:4096] if excerpt_raw else None
    return {
        "id": mid,
        "kind": kind,
        "subject_id": subject_id,
        "predicate": predicate[:64],
        "object": {"value": obj_val, "type": obj_type},
        "confidence": confidence,
        "sensitivity": sensitivity,
        "provenance": {
            "source": source,
            "extracted_at": now,
            "raw_excerpt": excerpt,
            "imported": False,
            "model": model,
        },
    }
```

- [ ] **Step 7.5: Update `src/context_capital/extract/__init__.py`**

```python
"""Memory extraction — mock keyword (offline) and real LLM (litellm-fronted)."""
from __future__ import annotations

from context_capital.extract.llm import DEFAULT_MODEL, extract_memories
from context_capital.extract.mock import extract_mock_memories

__all__ = ["DEFAULT_MODEL", "extract_memories", "extract_mock_memories"]
```

- [ ] **Step 7.6: Run — verify pass**

```bash
pytest tests/test_extract_llm.py -v
```

Expected: 8 passed.

- [ ] **Step 7.7: Lint + type-check**

```bash
ruff check src/context_capital/extract tests/test_extract_llm.py
mypy --strict src/context_capital/extract
```

Expected: clean.

- [ ] **Step 7.8: Commit**

```bash
git add pyproject.toml src/context_capital/extract/llm.py src/context_capital/extract/__init__.py tests/test_extract_llm.py
git commit -m "feat(extract): litellm-fronted Claude extractor with prompt cache + schema validation"
```

---

### Task 8: CLI integration — `cc capture` + `--mock`/`--model`

**Files:**
- Modify: `src/context_capital/cli.py`
- Create: `tests/test_cli_capture.py`

**Interfaces:**
- New CLI command: `cc capture --vendor <chatgpt|claude> --file <path> [--mock] [--model <id>]`.
- Modified `cc extract`: adds `--mock` (default ON) and `--model` flags.

- [ ] **Step 8.1: Write failing test `tests/test_cli_capture.py`**

```python
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
```

- [ ] **Step 8.2: Run — verify failure**

```bash
pytest tests/test_cli_capture.py -v
```

Expected: errors — `capture` subcommand does not exist yet.

- [ ] **Step 8.3: Modify `src/context_capital/cli.py`**

Add new imports near the existing imports:

```python
from context_capital.extract import extract_memories
from context_capital.ingest.chatgpt import parse_chatgpt_export
from context_capital.ingest.claude import parse_claude_export
from context_capital.ingest.types import IngestContext, IngestMessage, IngestRole
```

Replace the existing `@app.command()` for `extract` with this version (adds `--mock`/`--model`):

```python
@app.command()
def extract(
    text: str = typer.Option(..., "--text", "-t"),
    mock: bool = typer.Option(True, "--mock/--no-mock", help="Use deterministic mock extractor"),
    model: str = typer.Option("anthropic/claude-sonnet-4-5", "--model"),
) -> None:
    """Run the extractor against text and persist memories."""
    subject_id = _load_subject_id()
    if mock:
        memories = extract_mock_memories(subject_id=subject_id, raw_text=text)
    else:
        ic = IngestContext(
            vendor="manual",
            vendor_conversation_id=f"manual:{abs(hash(text)) % 10**12:012x}",
            captured_at=datetime.now(timezone.utc),
            source_file_hash="0" * 64,
            messages=[IngestMessage(seq=0, role=IngestRole.USER, content=text)],
        )
        memories = extract_memories(subject_id=subject_id, context=ic, model=model)
    with Store(_store_path()) as store:
        store.ensure_subject(subject_id)
        for m in memories:
            store.add_memory(m, actor="cli")
    rprint(f"[green]Extracted {len(memories)} memories.[/green]")
    for m in memories:
        rprint(f"  - {m['kind']}/{m['predicate']} -> {m['object']['value']}  ({m['id']})")
```

Add the new `capture` command after `extract`:

```python
@app.command()
def capture(
    vendor: str = typer.Option(..., "--vendor", help="chatgpt | claude"),
    file: Path = typer.Option(..., "--file", help="Path to the vendor export JSON"),
    mock: bool = typer.Option(False, "--mock/--no-mock", help="Skip LLM and use keyword mock extractor"),
    model: str = typer.Option("anthropic/claude-sonnet-4-5", "--model"),
) -> None:
    """Ingest an official vendor export and extract memories from each conversation."""
    if vendor not in ("chatgpt", "claude"):
        raise typer.BadParameter(f"unsupported vendor '{vendor}'. Use chatgpt or claude.")
    if not file.exists():
        raise typer.BadParameter(f"file not found: {file}")
    subject_id = _load_subject_id()
    parser = parse_chatgpt_export if vendor == "chatgpt" else parse_claude_export
    total_contexts = 0
    total_memories = 0
    with Store(_store_path()) as store:
        store.ensure_subject(subject_id)
        for ic in parser(file):
            total_contexts += 1
            store.persist_ingest_context(ic, subject_id=subject_id, actor="cli:capture")
            if mock:
                raw_text = "\n".join(m.content for m in ic.messages)
                mems = extract_mock_memories(subject_id=subject_id, raw_text=raw_text)
            else:
                mems = extract_memories(subject_id=subject_id, context=ic, model=model)
            for m in mems:
                store.add_memory(m, actor="cli:capture")
            total_memories += len(mems)
    rprint(f"[green]Captured {total_contexts} conversations.[/green]")
    rprint(f"[green]Extracted {total_memories} memories.[/green]")
```

- [ ] **Step 8.4: Run — verify pass**

```bash
pytest tests/test_cli_capture.py -v
```

Expected: 6 passed.

- [ ] **Step 8.5: Smoke-test the CLI**

```bash
python -m context_capital.cli capture --help
```

Expected: typer help listing `--vendor`, `--file`, `--mock`, `--model`.

- [ ] **Step 8.6: Run full suite — no regressions**

```bash
pytest -q
```

Expected: existing tests + everything from this plan pass.

- [ ] **Step 8.7: Lint + type-check**

```bash
ruff check src/context_capital tests
mypy --strict src/context_capital
```

Expected: clean.

- [ ] **Step 8.8: Commit**

```bash
git add src/context_capital/cli.py tests/test_cli_capture.py
git commit -m "feat(cli): cc capture command + --mock/--model flags on cc extract"
```

---

### Task 9: README + SRS update

**Files:**
- Modify: `README.md`
- Modify: `docs/srs.md`

- [ ] **Step 9.1: Update `README.md` quickstart**

Replace the existing `# Extract memories from text` example with:

```bash
# Capture from a real ChatGPT or Claude export (preferred)
cc capture --vendor chatgpt --file ~/Downloads/conversations.json
# Or for quick offline iteration without an LLM:
cc capture --vendor chatgpt --file ~/Downloads/conversations.json --mock
```

- [ ] **Step 9.2: Update `docs/srs.md` §7.1**

Find the line beginning `- [ ] **G-1 Round-trip.**` and update it to:

```
- [ ] **G-1 Round-trip.** A real ChatGPT export AND a real Claude export, each ≥ 200 conversations, capture → extract → export → import-into-clean-instance → verify with no memory loss, no schema errors, no signature failures. (Pipeline shipped 2026-06-22; awaiting first real ≥200-conversation export to flip to ✅)
```

- [ ] **Step 9.3: Run full suite + lints**

```bash
pytest -q
ruff check src/context_capital tools tests
mypy --strict src/context_capital tools
```

Expected: all green.

- [ ] **Step 9.4: Final commit + push**

```bash
git add README.md docs/srs.md
git commit -m "docs: quickstart uses cc capture; G-1 progress note"
git push origin main
```

---

## Self-Review

**1. Spec coverage.**

| Spec section | Task |
|---|---|
| §4.1 ingest/types.py | T1 |
| §4.2 ingest/chatgpt.py | T3 |
| §4.3 ingest/claude.py | T4 |
| §4.4 ingest/streaming.py | T2 |
| §4.5 extract/llm.py | T7 |
| §4.6 tools/anonymize_export.py | T5 |
| §4.7 cc capture | T8 |
| §4.8 cc extract --mock/--model | T8 |
| §6 failure modes | T6 idempotency, T7 invalid-JSON / exception tests |
| §8 DoD: round-trip + docs | T9 |

**2. Placeholder scan.** No `TBD`, `TODO`, `implement later`, or vague text. Every code step has complete code; every command has expected output.

**3. Type consistency.**

- `IngestRole` / `IngestMessage` / `IngestContext` referenced identically across T1, T3, T4, T6, T7, T8.
- `extract_memories(*, subject_id, context, model, prompt_cache, chunk_tokens, chunk_overlap_tokens, from_chunk)` — same signature in T7 definition and T8 call site.
- `Store.persist_ingest_context(ic, *, subject_id, actor)` — consistent in T6 definition and T8 call.
- `parse_chatgpt_export(path)` / `parse_claude_export(path)` — consistent across T3, T4, T8.

**4. Carry-forward backlog** (deferred, not blockers):
- Per-chunk checkpoint persistence in `extraction_jobs` (T7 accepts `from_chunk` but doesn't persist progress).
- Real anonymized fixtures at `tests/fixtures/captures/*-anonymized.json` (user-supplied post-implementation).
- Flipping `G-1` to ✅ after a 200+ conversation real-data round-trip is verified.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-22-real-capture-pipeline.md`. Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
