"""Phase C.0: what Thifur-H is allowed to say, and what the type will not let it.

Three properties carry this contract — provenance is always a forecast,
abstention is a value with a reason, and a number never travels without its
confidence — and one absence: the type cannot express an instruction. The last
is tested by trying, not asserted by reading the field list.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from cannae_kernel.absence import AbsenceKind, Absent, Recorded
from cannae_kernel.ids import LifecycleId
from cannae_kernel.provenance import Provenance
from cannae_kernel.recommendation import (
    DISTRIBUTION_TOLERANCE,
    LiquidityPeak,
    OutcomeProbability,
    ProbabilityDistribution,
    Recommendation,
)

T0 = datetime(2026, 9, 21, 22, 0, tzinfo=UTC)
LIFECYCLE = LifecycleId("lif_01M2P20SY00000000000000001")


def absent(reason: str, kind: AbsenceKind = AbsenceKind.NOT_YET_KNOWN) -> Absent:
    return Absent(kind=kind, reason=reason)


def distribution(*pairs: tuple[str, str]) -> ProbabilityDistribution:
    return ProbabilityDistribution(
        outcomes=tuple(
            OutcomeProbability(outcome=name, probability=Decimal(p)) for name, p in pairs
        )
    )


def recommendation(**overrides: object) -> Recommendation:
    fields: dict[str, object] = {
        "recommendation_id": "REC-1",
        "lifecycle_id": LIFECYCLE,
        "issued_at": T0,
        "provenance": Provenance.FORECAST,
        "c2_handoff": absent("operator-direct under CAOM-001", AbsenceKind.NOTHING_RECORDED),
        "model_ref": "condition-A/1.0",
        "funding_distribution": Recorded[ProbabilityDistribution](
            value=distribution(("will_queue", "0.7"), ("funded", "0.3"))
        ),
        "expected_queue_seconds": Recorded[int](value=5400),
        "window_miss_probability": absent("no window model in the baseline"),
        "peak_liquidity": absent("the baseline projects one obligation, not a profile"),
        "regime": absent("regime classification needs a time series"),
        "confidence": Recorded[Decimal](value=Decimal("0.82")),
    }
    fields.update(overrides)
    return Recommendation(**fields)  # type: ignore[arg-type]


class TestAModelOutputIsAlwaysAForecast:
    @pytest.mark.parametrize(
        "claimed",
        [
            Provenance.FACT_EXTERNAL,
            Provenance.FACT_SYNTHETIC,
            Provenance.POLICY_RESULT,
            Provenance.HUMAN_JUDGMENT,
            Provenance.RECOMMENDATION,
        ],
    )
    def test_no_other_provenance_can_be_claimed(self, claimed: Provenance) -> None:
        with pytest.raises(ValidationError, match="is a FORECAST"):
            recommendation(provenance=claimed)

    def test_policy_result_is_refused_for_its_own_reason(self) -> None:
        """A deterministic gate's output is reproducible and this is not."""
        with pytest.raises(ValidationError, match="deterministic gate"):
            recommendation(provenance=Provenance.POLICY_RESULT)

    def test_a_forecast_is_accepted(self) -> None:
        assert recommendation().provenance is Provenance.FORECAST


class TestTheTypeCannotExpressAnInstruction:
    """Tested by trying to construct one, per AMD2 § 2."""

    @pytest.mark.parametrize(
        "field",
        [
            "instruction",
            "order",
            "settlement_instruction",
            "release",
            "submit",
            "submission",
            "approve",
            "approval",
            "execute",
            "authorize",
            "payment",
            "amount_to_send",
        ],
    )
    def test_an_instruction_field_cannot_be_added(self, field: str) -> None:
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            recommendation(**{field: "PAY 1000000 USD TO ACCT 123"})

    def test_no_declared_field_could_carry_one(self) -> None:
        """The field list, as a second check on the construction test above."""
        forbidden = {
            "instruction",
            "order",
            "release",
            "submit",
            "submission",
            "approve",
            "approval",
            "execute",
            "authorize",
            "payment",
            "action",
            "command",
        }
        assert set(Recommendation.model_fields).isdisjoint(forbidden)

    def test_ranked_paths_rank_and_do_not_approve(self) -> None:
        """A ranking is an opinion about order. Thifur-J validates each path
        against the approved set; nothing here asserts a path is approved."""
        rec = recommendation(ranked_paths=("fedwire", "chips"))
        assert rec.ranked_paths == ("fedwire", "chips")
        assert "approved" not in " ".join(Recommendation.model_fields)


class TestAbstentionIsAValueWithAReason:
    def test_a_complete_abstention_is_valid(self) -> None:
        """ "I have nothing useful to say" is a real answer, and the type lets a
        model give it."""
        rec = recommendation(
            funding_distribution=absent("insufficient history for this counterparty"),
            expected_queue_seconds=absent("insufficient history for this counterparty"),
            confidence=absent("nothing was estimated, so there is nothing to be confident in"),
        )
        assert rec.abstained

    def test_a_partial_answer_is_not_an_abstention(self) -> None:
        assert not recommendation().abstained

    def test_every_absence_carries_its_reason(self) -> None:
        rec = recommendation()
        for name in ("window_miss_probability", "peak_liquidity", "regime"):
            value = getattr(rec, name)
            assert isinstance(value, Absent)
            assert value.reason
            assert value.disposition.value == "INDETERMINATE"

    def test_an_absence_cannot_be_written_without_a_reason(self) -> None:
        with pytest.raises(ValidationError):
            recommendation(regime=Absent(kind=AbsenceKind.NOT_YET_KNOWN, reason=""))

    def test_the_handoff_basis_is_never_a_bare_null(self) -> None:
        """The rule that produced A-T6, applied to this contract."""
        with pytest.raises(ValidationError):
            recommendation(c2_handoff=None)


class TestANumberTravelsWithItsConfidence:
    def test_an_answer_without_confidence_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="dressed as an answer"):
            recommendation(confidence=absent("the model does not self-assess"))

    def test_the_refusal_names_which_fields_were_answered(self) -> None:
        with pytest.raises(ValidationError) as raised:
            recommendation(confidence=absent("no self-assessment"))
        assert "funding_distribution" in str(raised.value)

    def test_a_ranking_is_a_forecast_and_carries_confidence_too(self) -> None:
        with pytest.raises(ValidationError, match="ranking is a forecast"):
            recommendation(
                funding_distribution=absent("nothing estimated"),
                expected_queue_seconds=absent("nothing estimated"),
                ranked_paths=("fedwire",),
                confidence=absent("nothing estimated"),
            )

    def test_abstaining_from_everything_may_abstain_from_confidence(self) -> None:
        """The pairing binds answers, not silence. A model that said nothing has
        nothing to be confident about, and requiring a number there would invite
        an invented one."""
        rec = recommendation(
            funding_distribution=absent("no history"),
            expected_queue_seconds=absent("no history"),
            confidence=absent("nothing was estimated"),
        )
        assert rec.abstained

    def test_the_kernel_sets_no_confidence_threshold(self) -> None:
        """What is too low to act on is domain policy and differs by rail."""
        assert recommendation(confidence=Recorded[Decimal](value=Decimal("0"))).confidence


class TestTheDistributionIsWellFormed:
    def test_probabilities_must_sum_to_one(self) -> None:
        with pytest.raises(ValidationError, match="not 1"):
            distribution(("will_queue", "0.7"), ("funded", "0.2"))

    def test_the_missing_mass_is_named_as_an_unnamed_outcome(self) -> None:
        with pytest.raises(ValidationError, match="outcome nobody named"):
            distribution(("will_queue", "0.5"))

    def test_an_outcome_cannot_appear_twice(self) -> None:
        """How a distribution sums to one while describing something incoherent."""
        with pytest.raises(ValidationError, match="appears more than once"):
            distribution(("will_queue", "0.5"), ("will_queue", "0.5"))

    def test_an_empty_distribution_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            ProbabilityDistribution(outcomes=())

    def test_a_probability_outside_zero_to_one_is_refused(self) -> None:
        for bad in ("-0.1", "1.5"):
            with pytest.raises(ValidationError):
                OutcomeProbability(outcome="x", probability=Decimal(bad))

    def test_rounding_within_tolerance_is_accepted(self) -> None:
        """Three thirds to four places is arithmetic, not a malformed claim."""
        d = distribution(("a", "0.3333"), ("b", "0.3333"), ("c", "0.3334"))
        assert len(d.outcomes) == 3
        assert DISTRIBUTION_TOLERANCE == Decimal("0.0001")

    def test_an_unnamed_outcome_returns_none_not_zero(self) -> None:
        """An outcome the model did not consider and one it assigned zero are
        different statements."""
        d = distribution(("will_queue", "1.0"))
        assert d.probability_of("will_queue") == Decimal("1.0")
        assert d.probability_of("will_fail") is None

    def test_the_kernel_does_not_validate_the_outcome_vocabulary(self) -> None:
        """It could not tell `will_queue` from a typo, so it does not pretend to.
        Atreides owns FundingDisposition; this carries the name."""
        assert distribution(("a-domain-the-kernel-never-heard-of", "1.0"))


class TestTheLiquidityPeakCarriesItsWindow:
    def test_a_peak_needs_an_interval_that_is_one(self) -> None:
        with pytest.raises(ValidationError, match="end after it starts"):
            LiquidityPeak(amount=Decimal("1"), currency="USD", interval_start=T0, interval_end=T0)

    def test_a_reversed_interval_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="end after it starts"):
            LiquidityPeak(
                amount=Decimal("1"),
                currency="USD",
                interval_start=T0,
                interval_end=T0 - timedelta(seconds=1),
            )

    def test_a_well_formed_peak_is_accepted(self) -> None:
        peak = LiquidityPeak(
            amount=Decimal("750000.00"),
            currency="USD",
            interval_start=T0,
            interval_end=T0 + timedelta(seconds=5400),
        )
        assert peak.amount == Decimal("750000.00")


class TestTheContractCrossesAWire:
    def test_it_round_trips_with_its_absences_intact(self) -> None:
        rec = recommendation()
        replayed = Recommendation.model_validate_json(rec.model_dump_json())
        assert replayed == rec
        assert isinstance(replayed.regime, Absent)
        assert replayed.regime.reason == "regime classification needs a time series"

    def test_the_schema_version_is_fixed(self) -> None:
        assert recommendation().schema_version == "cannae.recommendation/1.0"
        with pytest.raises(ValidationError):
            recommendation(schema_version="cannae.recommendation/2.0")

    def test_probabilities_are_decimals_not_floats(self) -> None:
        """A float has lost the exact value by the time it is serialized."""
        with pytest.raises(ValidationError):
            OutcomeProbability(outcome="x", probability=0.5)  # type: ignore[arg-type]
