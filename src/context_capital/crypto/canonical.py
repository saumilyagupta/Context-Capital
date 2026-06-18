"""RFC 8785 JSON Canonicalization Scheme (JCS) wrapper."""
from __future__ import annotations

from typing import Any

import rfc8785


def canonicalize(obj: Any) -> bytes:  # noqa: ANN401
    """Return the canonical UTF-8 bytes of `obj` per RFC 8785."""
    return rfc8785.dumps(obj)
