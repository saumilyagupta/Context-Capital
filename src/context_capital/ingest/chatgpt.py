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
