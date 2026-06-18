from __future__ import annotations
from typing import Any

import nacl.signing
import pytest

from context_capital.crypto.signing import generate_signing_key, sign_document, verify_document


def test_sign_then_verify_roundtrip(signing_key: nacl.signing.SigningKey, minimal_doc: dict[str, Any]) -> None:
    signed = sign_document(minimal_doc, signing_key)
    assert "signature" in signed
    assert signed["signature"]["alg"] == "ed25519"
    assert signed["signature"]["canonicalization"] == "jcs"
    assert verify_document(signed) is True


def test_tampered_memory_fails_verification(signing_key: nacl.signing.SigningKey, minimal_doc: dict[str, Any]) -> None:
    signed = sign_document(minimal_doc, signing_key)
    signed["memories"][0]["predicate"] = "different"
    assert verify_document(signed) is False


def test_tampered_signature_fails(signing_key: nacl.signing.SigningKey, minimal_doc: dict[str, Any]) -> None:
    signed = sign_document(minimal_doc, signing_key)
    signed["signature"]["value"] = "AAAA" + signed["signature"]["value"][4:]
    assert verify_document(signed) is False


def test_missing_signature_returns_false(minimal_doc: dict[str, Any]) -> None:
    assert verify_document(minimal_doc) is False


def test_wrong_alg_rejected(signing_key: nacl.signing.SigningKey, minimal_doc: dict[str, Any]) -> None:
    signed = sign_document(minimal_doc, signing_key)
    signed["signature"]["alg"] = "hs256"
    assert verify_document(signed) is False


def test_sign_refuses_doc_with_existing_signature(signing_key: nacl.signing.SigningKey, minimal_doc: dict[str, Any]) -> None:
    minimal_doc["signature"] = {"alg": "ed25519", "value": "AA", "public_key": "BB", "canonicalization": "jcs"}
    with pytest.raises(ValueError):
        sign_document(minimal_doc, signing_key)


def test_generate_signing_key_returns_signing_key() -> None:
    key = generate_signing_key()
    assert isinstance(key, nacl.signing.SigningKey)
