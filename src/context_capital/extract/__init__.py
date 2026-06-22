"""Memory extraction — mock keyword (offline) and real LLM (litellm-fronted)."""
from __future__ import annotations

from context_capital.extract.llm import DEFAULT_MODEL, extract_memories
from context_capital.extract.mock import extract_mock_memories

__all__ = ["DEFAULT_MODEL", "extract_memories", "extract_mock_memories"]
