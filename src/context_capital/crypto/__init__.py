"""Cryptographic primitives — JCS canonicalization + Ed25519 signing (ADR-004).

NOTE: This module's re-exports are expanded in Task 3 (signing). For Task 2,
only `canonicalize` is publicly exposed.
"""
from __future__ import annotations

from context_capital.crypto.canonical import canonicalize

__all__ = ["canonicalize"]
