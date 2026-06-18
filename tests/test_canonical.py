from __future__ import annotations

from context_capital.crypto import canonicalize


def test_canonicalize_returns_bytes() -> None:
    assert canonicalize({"a": 1}) == b'{"a":1}'


def test_canonicalize_orders_keys() -> None:
    a = canonicalize({"b": 2, "a": 1})
    b = canonicalize({"a": 1, "b": 2})
    assert a == b
    assert b == b'{"a":1,"b":2}'


def test_canonicalize_handles_nested() -> None:
    out = canonicalize({"outer": {"b": 2, "a": 1}})
    assert out == b'{"outer":{"a":1,"b":2}}'


def test_canonicalize_handles_arrays_in_original_order() -> None:
    out = canonicalize({"xs": [3, 1, 2]})
    assert out == b'{"xs":[3,1,2]}'
