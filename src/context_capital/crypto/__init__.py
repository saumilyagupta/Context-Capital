"""Cryptographic primitives — JCS canonicalization + Ed25519 signing (ADR-004)."""
from __future__ import annotations

from context_capital.crypto.canonical import canonicalize
from context_capital.crypto.signing import generate_signing_key, sign_document, verify_document

__all__ = ["canonicalize", "generate_signing_key", "sign_document", "verify_document"]
