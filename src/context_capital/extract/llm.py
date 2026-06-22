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
    excerpt = str(excerpt_raw)[:4096] if excerpt_raw else ""
    obj_out: dict[str, Any] = {"value": obj_val}
    if obj_type is not None:
        obj_out["type"] = obj_type
    return {
        "id": mid,
        "kind": kind,
        "subject_id": subject_id,
        "predicate": predicate[:64],
        "object": obj_out,
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
