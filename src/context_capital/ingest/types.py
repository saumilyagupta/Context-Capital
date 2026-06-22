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
