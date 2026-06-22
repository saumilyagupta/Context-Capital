"""Embedding helper (litellm-fronted, best-effort)."""
from __future__ import annotations

import logging
from typing import Any

import litellm

logger = logging.getLogger(__name__)

DEFAULT_EMBED_MODEL: str = "voyage/voyage-3"
EMBED_DIM: int = 1024


def embed_text(text: str, *, model: str = DEFAULT_EMBED_MODEL) -> list[float] | None:
    """Return the embedding vector for ``text``, or ``None`` on any failure.

    Failures (network, no API key, rate limit, wrong dim) are logged at
    WARNING and the function returns ``None``. Callers treat embedding as
    best-effort: the memory is persisted whether or not an embedding row
    is created.
    """
    if not text or not text.strip():
        return None
    try:
        resp: Any = litellm.embedding(model=model, input=[text])
        data = (
            resp.get("data")
            if isinstance(resp, dict)
            else getattr(resp, "data", None)
        )
        if not data:
            return None
        first: Any = data[0]
        vec = (
            first.get("embedding")
            if isinstance(first, dict)
            else getattr(first, "embedding", None)
        )
        if not isinstance(vec, list) or len(vec) != EMBED_DIM:
            logger.warning(
                "embedding has unexpected shape (model=%s, len=%s)",
                model,
                len(vec) if isinstance(vec, list) else None,
            )
            return None
        return [float(x) for x in vec]
    except Exception as e:  # noqa: BLE001 — best-effort wrapper
        logger.warning("embed_text failed (model=%s): %s", model, e)
        return None


def memory_to_text(memory: dict[str, Any]) -> str:
    """Canonical embedding-input string for a memory.

    Shape: ``"{predicate}: {value}\\n{raw_excerpt[:512]}"``.
    """
    predicate = memory.get("predicate", "")
    obj = memory.get("object") or {}
    val = obj.get("value", "")
    excerpt = (memory.get("provenance") or {}).get("raw_excerpt") or ""
    return f"{predicate}: {val}\n{excerpt[:512]}"
