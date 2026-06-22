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
