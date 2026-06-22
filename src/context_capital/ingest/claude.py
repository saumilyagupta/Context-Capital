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
