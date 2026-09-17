"""Required tests 3 and 5-8: enums, clocks, authority, finality and halt rules."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Any

import pytest
from pydantic import ValidationError

from cannae_kernel.actor import ActorKind
from cannae_kernel.authority import AuthorityRecord
from cannae_kernel.clocks import EventTimes
from cannae_kernel.delivery import ClearingMethod, DeliveryPattern
from cannae_kernel.disposition import Disposition, coerce_disposition
from cannae_kernel.domains import Domain
from cannae_kernel.finality import (
    ConditionalityStatus,
    FinalityAssertion,
    FinalityType,
    RevocabilityStatus,
)
from cannae_kernel.halt import HaltContext, gate_under_halt
from cannae_kernel.journal import ChainIssueCode
from cannae_kernel.provenance import Provenance
from tests.factories import (
    T0,
    authority_record,
    finality_assertion,
    halt_context,
    human,
    replace,
    service,
)

ALL_ENUMS: list[type[StrEnum]] = [
    ActorKind,
    ChainIssueCode,
    ClearingMethod,
    ConditionalityStatus,
    DeliveryPattern,
    Disposition,
    Domain,
    FinalityType,
    Provenance,
    RevocabilityStatus,
]

# ---- 3. Unknown enum values -------------------------------------------------------------


@pytest.mark.parametrize("enum", ALL_ENUMS)
def test_every_member_value_is_its_name(enum: type[StrEnum]) -> None:
    assert all(member.value == name for name, member in enum.__members__.items())


@pytest.mark.parametrize("enum", ALL_ENUMS)
@pytest.mark.parametrize("bad", ["UNKNOWN_VALUE", "", " PASS"])
def test_unknown_enum_value_raises(enum: type[StrEnum], bad: str) -> None:
    if bad in enum.__members__:
        pytest.skip("value is a member of this enum")
    with pytest.raises(ValueError):
        enum(bad)


def test_unknown_or_case_variant_enum_value_raises_inside_a_model() -> None:
    raw = finality_assertion().model_dump(mode="json")
    for bad in ("cash_final", "SETTLED"):
        with pytest.raises(ValidationError):
            FinalityAssertion.model_validate({**raw, "finality_type": bad}, strict=False)
    with pytest.raises(ValidationError):
        FinalityAssertion.model_validate_json(
            finality_assertion().model_dump_json().replace('"CASH_FINAL"', '"cash_final"')
        )
    # Strict Python construction takes members only; a matching string is not coerced.
    with pytest.raises(ValidationError):
        replace(finality_assertion(), finality_type="CASH_FINAL")


class _Other(StrEnum):
    PASS = "PASS"


@pytest.mark.parametrize(
    "value", ["pass", "PROCEED", "", None, "Pass", " PASS", 1, True, b"PASS", _Other.PASS]
)
def test_coerce_disposition_fails_safe(value: object) -> None:
    assert coerce_disposition(value) is Disposition.INDETERMINATE


@pytest.mark.parametrize("member", list(Disposition))
def test_coerce_disposition_accepts_exact_values(member: Disposition) -> None:
    assert coerce_disposition(member.value) is member
    assert coerce_disposition(member) is member


# ---- 5. Clocks ----------------------------------------------------------------------------


def _times(**kw: Any) -> EventTimes:
    base = {
        "event_time": T0,
        "observation_time": T0 + timedelta(seconds=1),
        "processing_time": T0 + timedelta(seconds=2),
        "decision_time": T0 + timedelta(seconds=3),
    }
    return EventTimes(**{**base, **kw})


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"observation_time": T0 - timedelta(microseconds=1)}, "observation_time"),
        ({"processing_time": T0}, "processing_time"),
        ({"decision_time": T0 + timedelta(seconds=1)}, "decision_time"),
    ],
)
def test_clock_ordering_violations_raise(changes: dict[str, datetime], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        _times(**changes)


def test_equal_times_and_absent_decision_are_allowed() -> None:
    _times(observation_time=T0, processing_time=T0, decision_time=T0)
    assert _times(decision_time=None).decision_time is None


@pytest.mark.parametrize(
    "bad", [datetime(2026, 9, 16), T0.astimezone(timezone(timedelta(hours=-4)))]
)
def test_times_must_be_utc(bad: datetime) -> None:
    with pytest.raises(ValidationError, match="UTC"):
        _times(event_time=bad)


# ---- 6. Authority -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "kind",
    [k for k in ActorKind if k not in (ActorKind.HUMAN, ActorKind.DETERMINISTIC_SERVICE)],
)
def test_non_authorizing_kinds_raise(kind: ActorKind) -> None:
    actor = replace(human(), actor_kind=kind)
    with pytest.raises(ValidationError, match="may not authorize"):
        replace(authority_record(), authorizing_actor=actor)


def test_agent_h_cannot_authorize() -> None:
    with pytest.raises(ValidationError, match="AGENT_H may not authorize"):
        replace(
            authority_record(), authorizing_actor=replace(human(), actor_kind=ActorKind.AGENT_H)
        )


def test_unauthenticated_actor_cannot_authorize() -> None:
    with pytest.raises(ValidationError, match="authenticated"):
        replace(authority_record(), authorizing_actor=human(authenticated=False))


def test_human_and_deterministic_service_can_authorize() -> None:
    assert replace(authority_record(), authorizing_actor=service()).authorizing_actor == service()
    assert authority_record().authorizing_actor.actor_kind is ActorKind.HUMAN


# ---- 7. Finality ------------------------------------------------------------------------


def test_forecast_without_confidence_raises() -> None:
    with pytest.raises(ValidationError, match="FORECAST"):
        replace(finality_assertion(), confidence=None)


@pytest.mark.parametrize("fact", [Provenance.FACT_EXTERNAL, Provenance.FACT_SYNTHETIC])
def test_fact_with_confidence_raises(fact: Provenance) -> None:
    with pytest.raises(ValidationError, match="authoritative"):
        replace(finality_assertion(), provenance=fact)
    assert replace(finality_assertion(), provenance=fact, confidence=None).confidence is None


@pytest.mark.parametrize(
    "provenance",
    [Provenance.RECOMMENDATION, Provenance.HUMAN_JUDGMENT, Provenance.POLICY_RESULT],
)
def test_other_provenances_may_omit_confidence(provenance: Provenance) -> None:
    replace(finality_assertion(), provenance=provenance, confidence=None)


@pytest.mark.parametrize("bad", [Decimal("-0.01"), Decimal("1.01")])
def test_confidence_is_between_zero_and_one(bad: Decimal) -> None:
    with pytest.raises(ValidationError):
        replace(finality_assertion(), confidence=bad)


def test_confidence_rejects_float() -> None:
    raw = finality_assertion().model_dump_json().replace('"0.85"', "0.85")
    with pytest.raises(ValidationError):
        FinalityAssertion.model_validate_json(raw)


# ---- 8. Halt ------------------------------------------------------------------------------


def test_active_in_scope_halt_blocks() -> None:
    ctx = halt_context()
    assert gate_under_halt(ctx, Domain.LC) is Disposition.BLOCK
    assert gate_under_halt(ctx, Domain.ATREIDES) is Disposition.BLOCK


def test_out_of_scope_or_inactive_halt_passes() -> None:
    ctx = halt_context()
    assert gate_under_halt(ctx, Domain.AUREON) is Disposition.PASS
    cleared = replace(ctx, active=False, version=2)
    assert all(gate_under_halt(cleared, d) is Disposition.PASS for d in Domain)


def test_all_scope_blocks_every_domain() -> None:
    ctx = replace(halt_context(), scope="ALL")
    assert all(gate_under_halt(ctx, d) is Disposition.BLOCK for d in Domain)


@pytest.mark.parametrize("bad", ["LC", "lc", "ATREIDES", None])
def test_gate_under_halt_refuses_raw_domain_strings(bad: object) -> None:
    with pytest.raises(TypeError, match="Domain member"):
        gate_under_halt(halt_context(), bad)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="HaltContext"):
        gate_under_halt("halt", Domain.LC)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("scope", "message"),
    [((), "at least one"), ((Domain.LC, Domain.LC), "repeat"), (("NOWHERE",), "NOWHERE")],
)
def test_malformed_scope_raises(scope: Any, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        replace(halt_context(), scope=scope)


def test_halt_version_starts_at_one() -> None:
    with pytest.raises(ValidationError):
        replace(halt_context(), version=0)


def test_models_are_frozen_and_closed() -> None:
    ctx: HaltContext = halt_context()
    with pytest.raises(ValidationError):
        ctx.active = False  # type: ignore[misc]
    with pytest.raises(ValidationError, match="Extra inputs"):
        HaltContext.model_validate({**ctx.model_dump(), "note": "x"})
    record: AuthorityRecord = authority_record()
    assert hash(record) == hash(authority_record())
