"""Ed25519 detached signature over JCS-canonicalized documents (spec §8)."""
from __future__ import annotations

import base64
from typing import Any

import nacl.exceptions
import nacl.signing

from context_capital.crypto.canonical import canonicalize


def generate_signing_key() -> nacl.signing.SigningKey:
    return nacl.signing.SigningKey.generate()


def sign_document(doc: dict[str, Any], signing_key: nacl.signing.SigningKey) -> dict[str, Any]:
    if "signature" in doc:
        raise ValueError("Document already has a signature; remove before signing.")
    canonical = canonicalize(doc)
    sig = signing_key.sign(canonical)
    return {
        **doc,
        "signature": {
            "alg": "ed25519",
            "value": base64.b64encode(sig.signature).decode("ascii"),
            "public_key": base64.b64encode(bytes(signing_key.verify_key)).decode("ascii"),
            "canonicalization": "jcs",
        },
    }


def verify_document(doc: dict[str, Any]) -> bool:
    sig_obj = doc.get("signature")
    if not isinstance(sig_obj, dict):
        return False
    if sig_obj.get("alg") != "ed25519":
        return False
    if sig_obj.get("canonicalization") != "jcs":
        return False
    try:
        sig_bytes = base64.b64decode(sig_obj["value"])
        pk_bytes = base64.b64decode(sig_obj["public_key"])
    except (ValueError, KeyError):
        return False
    doc_without_sig = {k: v for k, v in doc.items() if k != "signature"}
    canonical = canonicalize(doc_without_sig)
    verify_key = nacl.signing.VerifyKey(pk_bytes)
    try:
        verify_key.verify(canonical, sig_bytes)
        return True
    except nacl.exceptions.BadSignatureError:
        return False
