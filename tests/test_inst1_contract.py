"""INST-1 WP0 acceptance for the breaking institutional binding contract."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from cannae_kernel._model import KernelModel
from cannae_kernel.canonical import canonical_bytes_of, digest
from cannae_kernel.envelopes import FirmSecuritiesDirection, SettlementObligationEnvelope
from tests.factories import settlement_obligation


def test_settlement_obligation_binds_approved_intent_and_direction() -> None:
    """E-H2: the cross-domain contract carries both institutional bindings."""
    validated = settlement_obligation()
    assert isinstance(validated, SettlementObligationEnvelope)
    assert validated.approved_intent_digest == "sha256:" + "a" * 64
    assert validated.firm_securities_direction is FirmSecuritiesDirection.RECEIVE
    assert validated.schema_version == "cannae.settlement_obligation/2.0"


def test_decimal_scale_does_not_change_canonical_bytes_or_digest() -> None:
    """L2/E-L6 quotes WP0.2: "100 and 100.00 produce the same digest."""
    assert canonical_bytes_of(Decimal("100")) == b'"100"'
    assert canonical_bytes_of(Decimal("100.00")) == b'"100"'
    assert canonical_bytes_of(Decimal("1E+2")) == b'"100"'
    assert digest(_Amount(amount=Decimal("100"))) == digest(_Amount(amount=Decimal("100.00")))


@pytest.mark.parametrize("value", [Decimal("1E+1000"), Decimal("1E-1000")])
def test_extreme_finite_decimals_stay_plain_and_exact(value: Decimal) -> None:
    encoded = canonical_bytes_of(value)
    assert b"E" not in encoded and b"e" not in encoded
    assert Decimal(json.loads(encoded)) == value


def test_normalisation_does_not_collapse_different_economics() -> None:
    assert digest(_Amount(amount=Decimal("100"))) != digest(_Amount(amount=Decimal("100.01")))


class _Amount(KernelModel):
    amount: Decimal
