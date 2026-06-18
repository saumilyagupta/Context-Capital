"""Embedded JSON Schema 2020-12 for Context Protocol v0.1 — spec §6."""
from __future__ import annotations

from typing import Any

CONTEXT_PROTOCOL_V0_1_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://contextprotocol.org/schema/v0.1.json",
    "title": "Context Protocol v0.1.0",
    "type": "object",
    "required": ["@context", "context_protocol_version", "subject", "issuer", "memories", "signature"],
    "properties": {
        "@context": {"oneOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]},
        "context_protocol_version": {"type": "string", "const": "0.1.0"},
        "subject": {
            "type": "object",
            "required": ["id", "type"],
            "properties": {
                "id": {"type": "string", "pattern": r"^did:[a-z0-9]+:.+"},
                "type": {"enum": ["person", "organization", "agent"]},
                "display_name": {"type": "string"},
            },
            "additionalProperties": False,
        },
        "issuer": {
            "type": "object",
            "required": ["tool", "exported_at"],
            "properties": {
                "tool": {"type": "string"},
                "exported_at": {"type": "string", "format": "date-time"},
                "verifier_hint": {"type": "string", "format": "uri"},
            },
            "additionalProperties": False,
        },
        "memories": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "kind", "subject_id", "predicate", "object", "confidence", "provenance", "sensitivity"],
                "properties": {
                    "id": {"type": "string", "pattern": r"^mem_[a-f0-9]{32}$"},
                    "kind": {"enum": ["preference", "fact", "decision", "project", "workflow", "skill"]},
                    "subject_id": {"type": "string", "pattern": r"^did:[a-z0-9]+:.+"},
                    "predicate": {"type": "string", "minLength": 1, "maxLength": 64},
                    "object": {
                        "type": "object",
                        "required": ["value"],
                        "properties": {"value": {}, "type": {"type": "string"}},
                    },
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "provenance": {
                        "type": "object",
                        "required": ["source", "extracted_at"],
                        "properties": {
                            "source": {"type": "string"},
                            "extracted_at": {"type": "string", "format": "date-time"},
                            "raw_excerpt": {"type": "string", "maxLength": 4096},
                            "imported": {"type": "boolean"},
                            "import_source": {"type": "string"},
                            "model": {"type": "string"},
                        },
                    },
                    "validity": {
                        "type": "object",
                        "properties": {
                            "valid_from": {"type": "string", "format": "date-time"},
                            "valid_until": {"type": ["string", "null"], "format": "date-time"},
                            "superseded_by": {"type": ["string", "null"]},
                        },
                    },
                    "sensitivity": {"enum": ["public", "work", "personal", "secret"]},
                    "permissions": {
                        "type": "object",
                        "properties": {
                            "allow": {"type": "array", "items": {"type": "string"}},
                            "deny": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                },
            },
        },
        "signature": {
            "type": "object",
            "required": ["alg", "value", "public_key"],
            "properties": {
                "alg": {"const": "ed25519"},
                "value": {"type": "string"},
                "public_key": {"type": "string"},
                "canonicalization": {"const": "jcs"},
            },
        },
        "schema_version_log": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["from", "to", "at"],
                "properties": {
                    "from": {"type": "string"},
                    "to": {"type": "string"},
                    "at": {"type": "string", "format": "date-time"},
                    "by": {"type": "string"},
                },
            },
        },
        "extensions": {"type": "object"},
    },
    "additionalProperties": False,
}
