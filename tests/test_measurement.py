"""R1: the consumer refuses, and a later caller cannot route around it.

The requirement these tests exist for, from `W3-contract-freeze.md` § R1:

    The consumer refuses, not the producer's caller. A gate that accepts a bare
    float and trusts whoever passed it is the shape that failed in P07 §8.5 [...]
    it survives only because one caller remembers to filter. A second caller added
    later reintroduces the whole class silently. Make the type carry the check.

So the load-bearing test here is not "a constant is refused". It is
`test_a_new_caller_cannot_reintroduce_the_class`: a gate written against
`ObservedFact` refuses a fabricated value **without the gate or the first caller
being changed**, because there is no way to construct the argument.

The concrete case throughout is F1: with FRED and the OFR page both unreachable,
a fallback constant produced a plausible stress reading of 0.38, and gate 6 read
it as PASS.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import TypeAdapter, ValidationError

from cannae_kernel.measurement import (
    ADMISSIBLE_WITH_DERIVATION,
    OBSERVED,
    Constant,
    Measurement,
    NotAnObservationError,
    ObservedFact,
    Reading,
    require_observation,
)
from cannae_kernel.provenance import Provenance

T0 = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
STRESS = Decimal("0.38")


def _measurement(provenance: Provenance = Provenance.FACT_EXTERNAL) -> Measurement:
    return Measurement(
        value=STRESS,
        provenance=provenance,
        source="OFR Financial Stress Index",
        observed_at=T0,
    )


def _fallback() -> Constant:
    """F1, exactly: the constant that stood in when nothing could be read."""
    return Constant(
        value=STRESS,
        source="fallback_macro_snapshot",
        reason="FRED and the OFR page were both unreachable",
    )


# --- the requirement -----------------------------------------------------------


def test_a_new_caller_cannot_reintroduce_the_class() -> None:
    """The reason the check lives in the type and not in a filter.

    `stress_gate` is written once. A second caller is added later by someone who
    does not know about the fallback. There is nothing they can pass that makes
    the gate act on a fabricated number, and they find out at the call site.
    """

    def stress_gate(reading: ObservedFact) -> str:
        return "PASS" if reading.value < Decimal("0.7") else "HOLD"

    # The first caller, who remembered to filter.
    assert stress_gate(require_observation(_measurement())) == "PASS"

    # The second caller, who did not. There is no argument they can build.
    with pytest.raises(NotAnObservationError):
        stress_gate(require_observation(_fallback()))

    # Nor by going around require_observation: the constant has no observation to
    # copy, so ObservedFact cannot be assembled from its fields.
    assert not hasattr(_fallback(), "observed_at")
    assert not hasattr(_fallback(), "provenance")


def test_the_fabricated_reading_cannot_satisfy_a_gate() -> None:
    """F1 as a one-liner: 0.38 with nothing behind it is not permission."""
    with pytest.raises(NotAnObservationError) as refusal:
        require_observation(_fallback())
    message = str(refusal.value)
    assert "no observation was made" in message
    assert "FRED and the OFR page were both unreachable" in message, (
        "the refusal does not carry the reason, so the operator learns nothing"
    )


# --- what a measurement is -----------------------------------------------------


def test_a_measurement_must_say_when_it_was_observed() -> None:
    """A value without an observation time is not a measurement."""
    with pytest.raises(ValidationError):
        Measurement(
            value=STRESS, provenance=Provenance.FACT_EXTERNAL, source="OFR Financial Stress Index"
        )  # type: ignore[call-arg]


def test_a_constant_cannot_be_given_an_observation_time() -> None:
    """Not merely absent by convention — the field does not exist."""
    with pytest.raises(ValidationError):
        Constant(
            value=STRESS, source="fallback_macro_snapshot", reason="unreachable", observed_at=T0
        )  # type: ignore[call-arg]


def test_a_constant_must_say_why_there_is_no_observation() -> None:
    with pytest.raises(ValidationError):
        Constant(value=STRESS, source="fallback_macro_snapshot")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        Constant(value=STRESS, source="fallback_macro_snapshot", reason="")


# --- which provenances satisfy a gate ------------------------------------------


def test_a_synthetic_reading_may_cross_a_boundary_but_not_satisfy_a_gate() -> None:
    """P08 §4: do not block the input, type it, and make the consumer refuse."""
    synthetic = _measurement(Provenance.FACT_SYNTHETIC)

    # It crosses: it serializes and reads back unchanged.
    assert Measurement.model_validate_json(synthetic.model_dump_json()) == synthetic

    # It does not satisfy.
    with pytest.raises(NotAnObservationError) as refusal:
        require_observation(synthetic)
    assert "FACT_SYNTHETIC" in str(refusal.value)


def test_a_gate_may_admit_a_derived_reading_but_has_to_say_so() -> None:
    """The aureon stress proxy: a real computation over real data, not the reading."""
    derived = _measurement(Provenance.POLICY_RESULT)

    with pytest.raises(NotAnObservationError):
        require_observation(derived)

    admitted = require_observation(derived, admitting=ADMISSIBLE_WITH_DERIVATION)
    assert admitted.provenance is Provenance.POLICY_RESULT


@pytest.mark.parametrize("provenance", [Provenance.FORECAST, Provenance.RECOMMENDATION])
def test_a_forecast_is_never_an_observation_however_widely_a_gate_admits(
    provenance: Provenance,
) -> None:
    """A gate cannot opt into treating something unseen as something seen."""
    reading = _measurement(provenance)
    with pytest.raises((NotAnObservationError, ValidationError)):
        require_observation(reading, admitting=set(Provenance))


def test_the_default_admitted_set_is_external_authority_only() -> None:
    assert OBSERVED == {Provenance.FACT_EXTERNAL}
    assert Provenance.FACT_SYNTHETIC not in OBSERVED


# --- the boundary --------------------------------------------------------------


def test_a_serialized_reading_cannot_be_read_back_as_the_other_kind() -> None:
    """The discriminator is what stops a constant arriving as a measurement."""
    adapter: TypeAdapter[Measurement | Constant] = TypeAdapter(Reading)
    for reading in (_measurement(), _fallback()):
        assert adapter.validate_json(adapter.dump_json(reading)) == reading

    disguised = adapter.dump_json(_fallback()).replace(b'"constant"', b'"measurement"')
    with pytest.raises(ValidationError):
        adapter.validate_json(disguised)


def test_an_observed_fact_keeps_what_it_was_built_from() -> None:
    observed = require_observation(_measurement())
    assert (observed.value, observed.source, observed.observed_at) == (
        STRESS,
        "OFR Financial Stress Index",
        T0,
    )
