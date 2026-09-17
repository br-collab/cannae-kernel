"""Canonical serialization and content digests.

``canonical_bytes`` is the one byte form every domain hashes. The rules are part of the
contract; changing any of them is a breaking change (see CLAUDE.md):

- JSON (JavaScript Object Notation) encoded as UTF-8, with no insignificant whitespace.
- Object keys must be ASCII, and are sorted. A non-ASCII key raises: code-point order and the
  UTF-16 order other languages use agree only for ASCII (JUM-D-24). Non-ASCII string *values*
  are allowed and emitted as UTF-8, not escaped.
- Integers must lie within ±(2^53 - 1), the range every JSON consumer represents exactly.
  Anything larger raises. Quantities and money are ``Decimal`` strings, not integers.
- ``Decimal`` as a JSON string in plain notation, keeping its scale (``"1000000.00"``, never
  ``"1E+6"``). Non-finite values raise.
- ``datetime`` as a JSON string in UTC ISO-8601 with six fractional digits and ``Z``
  (``"2026-09-16T21:30:00.000000Z"``). A naive datetime raises; an aware one in another
  zone is converted to UTC.
- Enums as their values; ``None`` as ``null``; tuples and lists as arrays.
- Floats raise anywhere, at any depth. So does any type not listed here.

This is deliberately not full RFC 8785 (JSON Canonicalization Scheme). The key and integer
rules above remove the two differences that matter across languages: key ordering and
large-number formatting. The golden vectors, not RFC 8785, are the reference.

``digest`` is ``"sha256:"`` followed by the lower-case hex SHA-256 of ``canonical_bytes``.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, StringConstraints

from cannae_kernel._model import MAX_SAFE_INTEGER

__all__ = [
    "CanonicalizationError",
    "Digest",
    "canonical_bytes",
    "canonical_bytes_of",
    "digest",
    "digest_bytes",
]

Digest = Annotated[str, StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$")]
"""``sha256:`` followed by 64 lower-case hex characters."""


class CanonicalizationError(TypeError):
    """A value has no canonical form: a float, a naive datetime, or an unsupported type."""


def _canonical_value(value: Any, path: str) -> Any:  # noqa: PLR0911, PLR0912
    # One branch per JSON type is the rule table itself; splitting it would hide the order.
    # Order matters: bool is an int, and StrEnum members are str.
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, Enum):
        return _canonical_value(value.value, path)
    if isinstance(value, str):
        return str(value)
    if isinstance(value, int):
        if not -MAX_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER:
            raise CanonicalizationError(
                f"integer at {path or '<root>'} is outside ±(2^53 - 1); use a Decimal"
            )
        return int(value)
    if isinstance(value, float):
        raise CanonicalizationError(f"float at {path or '<root>'} has no canonical form")
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise CanonicalizationError(f"non-finite Decimal at {path or '<root>'}")
        return format(value, "f")
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise CanonicalizationError(f"naive datetime at {path or '<root>'}")
        u = value.astimezone(UTC)
        return (
            f"{u.year:04d}-{u.month:02d}-{u.day:02d}T{u.hour:02d}:{u.minute:02d}:"
            f"{u.second:02d}.{u.microsecond:06d}Z"
        )
    if isinstance(value, BaseModel):
        return _canonical_value(value.model_dump(mode="python"), path)
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalizationError(f"non-string key {key!r} at {path or '<root>'}")
            if not key.isascii():
                raise CanonicalizationError(f"non-ASCII key {key!r} at {path or '<root>'}")
            out[str(key)] = _canonical_value(item, f"{path}.{key}" if path else key)
        return out
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item, f"{path}[{i}]") for i, item in enumerate(value)]
    raise CanonicalizationError(
        f"{type(value).__name__} at {path or '<root>'} has no canonical form"
    )


def canonical_bytes_of(value: Any) -> bytes:
    """Canonical bytes of any supported value. Prefer ``canonical_bytes`` for models."""
    return json.dumps(
        _canonical_value(value, ""),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_bytes(model: BaseModel) -> bytes:
    """Deterministic JSON bytes for ``model`` under the rules in this module's docstring."""
    return canonical_bytes_of(model)


def digest_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def digest(model: BaseModel) -> str:
    """``sha256:<hex>`` over ``canonical_bytes(model)``."""
    return digest_bytes(canonical_bytes(model))
