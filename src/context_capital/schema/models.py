"""Pydantic v2 models for Context Protocol v0.1 — see docs/spec/context-protocol-v0.1.md §5."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

DID_PATTERN = r"^did:[a-z0-9]+:.+"
MEMORY_ID_PATTERN = r"^mem_[a-f0-9]{32}$"


class SubjectType(StrEnum):
    PERSON = "person"
    ORGANIZATION = "organization"
    AGENT = "agent"


class MemoryKind(StrEnum):
    PREFERENCE = "preference"
    FACT = "fact"
    DECISION = "decision"
    PROJECT = "project"
    WORKFLOW = "workflow"
    SKILL = "skill"


class Sensitivity(StrEnum):
    PUBLIC = "public"
    WORK = "work"
    PERSONAL = "personal"
    SECRET = "secret"


class Subject(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=DID_PATTERN)
    type: SubjectType
    display_name: str | None = None


class Issuer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool: str
    exported_at: datetime
    verifier_hint: str | None = None


class MemoryObject(BaseModel):
    value: Any
    type: str | None = None


class Provenance(BaseModel):
    source: str
    extracted_at: datetime
    raw_excerpt: str | None = Field(default=None, max_length=4096)
    imported: bool | None = None
    import_source: str | None = None
    model: str | None = None


class Validity(BaseModel):
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    superseded_by: str | None = None


class Permissions(BaseModel):
    allow: list[str] | None = None
    deny: list[str] | None = None


class Memory(BaseModel):
    id: str = Field(pattern=MEMORY_ID_PATTERN)
    kind: MemoryKind
    subject_id: str = Field(pattern=DID_PATTERN)
    predicate: str = Field(min_length=1, max_length=64)
    object: MemoryObject
    confidence: float = Field(ge=0.0, le=1.0)
    provenance: Provenance
    validity: Validity | None = None
    sensitivity: Sensitivity
    permissions: Permissions | None = None


class Signature(BaseModel):
    alg: Literal["ed25519"]
    value: str
    public_key: str
    canonicalization: Literal["jcs"] = "jcs"


class SchemaVersionLogEntry(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    from_version: str = Field(alias="from")
    to_version: str = Field(alias="to")
    at: datetime
    by: str | None = None


class ContextDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")
    context_url: str | list[str] = Field(alias="@context")
    context_protocol_version: Literal["0.1.0"]
    subject: Subject
    issuer: Issuer
    memories: list[Memory] = Field(default_factory=list)
    signature: Signature
    schema_version_log: list[SchemaVersionLogEntry] | None = None
    extensions: dict[str, Any] | None = None


def compute_memory_id(
    *,
    kind: MemoryKind | str,
    predicate: str,
    subject_id: str,
    object_value: Any,
    object_type: str | None,
    sensitivity: Sensitivity | str,
) -> str:
    """Content-addressed memory ID. Canonical form omits provenance/confidence/validity
    so two extractions of the same conclusion deduplicate (SRS FR-3.4)."""
    payload = {
        "kind": str(kind),
        "predicate": predicate,
        "subject_id": subject_id,
        "object": {"value": object_value, "type": object_type},
        "sensitivity": str(sensitivity),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()[:32]
    return f"mem_{digest}"
