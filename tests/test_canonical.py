from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from cannae_kernel._model import KernelDecimal, KernelModel
from cannae_kernel.canonical import (
    CanonicalizationError,
    canonical_bytes,
    canonical_bytes_of,
    digest,
)
from cannae_kernel.disposition import Disposition
from tests.factories import finality_assertion, halt_context, replace


class _Loose(KernelModel):
    """A payload with an open field, to put arbitrary values through the canonical rules."""

    value: Any


def _bytes(value: Any) -> bytes:
    return canonical_bytes(_Loose(value=value))


def test_keys_sorted_no_whitespace_utf8() -> None:
    assert _bytes({"b": 1, "a": "é", "c": [True, None]}) == (
        '{"value":{"a":"é","b":1,"c":[true,null]}}'.encode()
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("1000000.00"), '"1000000.00"'),
        (Decimal("1E+6"), '"1000000"'),
        (Decimal("0.000001"), '"0.000001"'),
        (Decimal("-12.50"), '"-12.50"'),
    ],
)
def test_decimal_is_a_plain_string_keeping_scale(value: Decimal, expected: str) -> None:
    assert _bytes(value) == ('{"value":' + expected + "}").encode()


@pytest.mark.parametrize("value", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_non_finite_decimal_raises(value: Decimal) -> None:
    with pytest.raises(CanonicalizationError, match="non-finite"):
        _bytes(value)


def test_datetime_is_utc_with_microseconds_and_z() -> None:
    plus2 = datetime(2026, 9, 16, 23, 30, 1, 5, tzinfo=timezone(timedelta(hours=2)))
    assert _bytes(plus2) == b'{"value":"2026-09-16T21:30:01.000005Z"}'
    assert _bytes(datetime(999, 1, 2, tzinfo=UTC)) == b'{"value":"0999-01-02T00:00:00.000000Z"}'


def test_naive_datetime_raises() -> None:
    with pytest.raises(CanonicalizationError, match="naive datetime"):
        _bytes(datetime(2026, 1, 1))


def test_enum_is_its_value() -> None:
    assert _bytes(Disposition.HOLD) == b'{"value":"HOLD"}'


@pytest.mark.parametrize(
    "value",
    [
        1.5,
        {"a": {"b": [1, 2, 0.1]}},
        [Decimal(1), (0.0,)],
        {"nested": _Loose(value={"x": float("nan")})},
    ],
)
def test_float_raises_at_any_depth(value: Any) -> None:
    with pytest.raises(CanonicalizationError, match="float"):
        _bytes(value)


def test_non_ascii_key_raises() -> None:
    # JUM-D-24: key order is only language-independent for ASCII keys.
    with pytest.raises(CanonicalizationError, match="non-ASCII key"):
        _bytes({"montant": 1, "déjà": 2})
    assert _bytes({"a": "déjà"}) == '{"value":{"a":"déjà"}}'.encode()


@pytest.mark.parametrize("value", [2**53, -(2**53), 10**30])
def test_integer_outside_the_safe_range_raises(value: int) -> None:
    with pytest.raises(CanonicalizationError, match="outside"):
        _bytes({"n": [value]})


@pytest.mark.parametrize("value", [2**53 - 1, -(2**53 - 1), 0, True])
def test_integer_at_the_safe_boundary_is_allowed(value: int) -> None:
    assert _bytes(value) == f'{{"value":{str(value).lower()}}}'.encode()


def test_kernel_integer_fields_refuse_values_they_could_not_serialize() -> None:
    with pytest.raises(ValidationError):
        replace(halt_context(), version=2**53)


def test_unsupported_type_and_non_string_key_raise() -> None:
    with pytest.raises(CanonicalizationError, match="set"):
        _bytes({1, 2})
    with pytest.raises(CanonicalizationError, match="non-string key"):
        _bytes({1: "a"})


def test_digest_is_sha256_of_canonical_bytes() -> None:
    model = finality_assertion()
    expected = "sha256:" + hashlib.sha256(canonical_bytes(model)).hexdigest()
    assert digest(model) == expected
    assert canonical_bytes_of(model) == canonical_bytes(model)


class _Money(KernelModel):
    amount: KernelDecimal


def test_kernel_decimal_rejects_floats_on_the_way_in() -> None:
    for raw in ('{"amount": 1.5}', '{"amount": 2}', '{"amount": "NaN"}', '{"amount": "abc"}'):
        with pytest.raises(ValidationError):
            _Money.model_validate_json(raw)
    for bad in (1.5, "1.50", 2):
        with pytest.raises(ValidationError):
            _Money(amount=bad)  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="finite"):
        _Money(amount=Decimal("NaN"))
    assert _Money.model_validate_json('{"amount": "1.50"}').amount == Decimal("1.50")
