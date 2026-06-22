"""Ingest package — vendor-specific adapters that produce canonical IngestContexts."""
from __future__ import annotations

from context_capital.ingest.types import IngestContext, IngestMessage, IngestRole

__all__ = ["IngestContext", "IngestMessage", "IngestRole"]
