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


@pytest.mark.parametrize("provenance", [Provenance.FORECAST, Provenance.RECOMMENDATION])
def test_inferred_provenance_without_confidence_raises(provenance: Provenance) -> None:
    # JUM-D-21: forecasts and recommendations must state a confidence.
    with pytest.raises(ValidationError, match="inferred and must carry a confidence"):
        replace(finality_assertion(), provenance=provenance, confidence=None)
    assert replace(finality_assertion(), provenance=provenance).confidence == Decimal("0.85")


def _fact_timed(provenance: Provenance, **changes: Any) -> FinalityAssertion:
    """``finality_assertion()`` as a fact, observed one minute after it took effect."""
    base = finality_assertion()
    defaults: dict[str, Any] = {
        "provenance": provenance,
        "confidence": None,
        "observation_time": base.effective_time + timedelta(minutes=1),
    }
    return replace(base, **{**defaults, **changes})


@pytest.mark.parametrize(
    "provenance",
    [Provenance.FACT_EXTERNAL, Provenance.FACT_SYNTHETIC, Provenance.POLICY_RESULT],
)
def test_authoritative_or_deterministic_with_confidence_raises(provenance: Provenance) -> None:
    # JUM-D-21: facts and policy results must not look inferred.
    with pytest.raises(ValidationError, match="must not carry a confidence"):
        _fact_timed(provenance, confidence=Decimal("0.9"))
    assert _fact_timed(provenance).confidence is None


@pytest.mark.parametrize("confidence", [None, Decimal("0.4")])
def test_human_judgment_confidence_is_optional(confidence: Decimal | None) -> None:
    assessed = replace(
        finality_assertion(), provenance=Provenance.HUMAN_JUDGMENT, confidence=confidence
    )
    assert assessed.confidence == confidence


@pytest.mark.parametrize("fact", [Provenance.FACT_EXTERNAL, Provenance.FACT_SYNTHETIC])
def test_fact_observed_before_it_takes_effect_raises(fact: Provenance) -> None:
    # JUM-D-22.
    base = finality_assertion()
    with pytest.raises(ValidationError, match="observed before it takes effect"):
        _fact_timed(fact, observation_time=base.effective_time - timedelta(microseconds=1))
    assert _fact_timed(fact, observation_time=base.effective_time).confidence is None


@pytest.mark.parametrize(
    "provenance",
    [
        Provenance.FORECAST,
        Provenance.RECOMMENDATION,
        Provenance.HUMAN_JUDGMENT,
        Provenance.POLICY_RESULT,
    ],
)
def test_non_facts_may_describe_a_future_effective_time(provenance: Provenance) -> None:
    base = finality_assertion()
    assert base.observation_time < base.effective_time
    confidence = None if provenance is Provenance.POLICY_RESULT else base.confidence
    replace(base, provenance=provenance, confidence=confidence)


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


@pytest.mark.parametrize("bad", [0, -1, 2**53])
def test_halt_version_is_a_positive_safe_integer(bad: int) -> None:
    with pytest.raises(ValidationError):
        replace(halt_context(), version=bad)


@pytest.mark.parametrize("kind", list(ActorKind))
def test_any_authenticated_kind_may_declare_a_halt(kind: ActorKind) -> None:
    # JUM-D-19: halting is the safe direction.
    declarer = replace(human(), actor_kind=kind)
    assert replace(halt_context(), declared_by=declarer).declared_by.actor_kind is kind


def test_unauthenticated_actor_may_not_declare_a_halt() -> None:
    with pytest.raises(ValidationError, match="must be authenticated"):
        replace(halt_context(), declared_by=human(authenticated=False))


@pytest.mark.parametrize("kind", [k for k in ActorKind if k is not ActorKind.HUMAN])
def test_only_a_human_may_clear_a_halt(kind: ActorKind) -> None:
    clearer = replace(human(), actor_kind=kind)
    with pytest.raises(ValidationError, match=f"only a HUMAN may clear a halt; {kind.value}"):
        replace(halt_context(), active=False, version=2, declared_by=clearer)


def test_unauthenticated_human_may_not_clear_a_halt() -> None:
    with pytest.raises(ValidationError, match="must be authenticated"):
        replace(halt_context(), active=False, version=2, declared_by=human(authenticated=False))
    assert not replace(halt_context(), active=False, version=2).active


def test_models_are_frozen_and_closed() -> None:
    ctx: HaltContext = halt_context()
    with pytest.raises(ValidationError):
        ctx.active = False  # type: ignore[misc]
    with pytest.raises(ValidationError, match="Extra inputs"):
        HaltContext.model_validate({**ctx.model_dump(), "note": "x"})
    record: AuthorityRecord = authority_record()
    assert hash(record) == hash(authority_record())
