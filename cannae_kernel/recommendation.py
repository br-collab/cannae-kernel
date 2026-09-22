"""What the adaptive agent is allowed to say (Phase C.0, AMD2 § 2).

H = Thifur-H, the adaptive intelligence class. LNN = liquid neural network.

**Additive.** The five frozen envelopes are untouched. This is a sixth contract,
for a different kind of claim: not something that happened, and not the output
of a deterministic gate, but a **model's opinion about what is likely to
happen**.

Why a model needs a contract of its own
---------------------------------------
Every other contract in this kernel describes something that occurred or was
decided. A forecast is neither. It is the only claim in the programme that is
*expected* to be wrong some of the time, and that changes what the type has to
guarantee: not that the number is right, but that a reader can always tell how
much weight it carries and when the model declined to answer.

Three properties do that work, and each is a validator rather than a convention.

**Provenance is ``FORECAST``, always.** It cannot be constructed as any
``FACT_*`` or as ``POLICY_RESULT``. A model's output relabelled as an
observation is the Wave 2 defect in its most expensive form — the fabricated
0.38 that a gate read as PASS was exactly this, a number with no observation
behind it wearing an observation's clothes.

**Abstention is a first-class value with a reason** (W3 § R2). Every output is
``Recorded[T] | Absent``. A model that does not know says so, in the record,
with the reason — it never emits a low-confidence number dressed as an answer.
A recommendation in which every field is absent is a **complete abstention**,
and it is valid: "I have nothing useful to say about this" is a real answer and
the type lets a model give it.

**A number never travels without its confidence.** If any forecast field is
recorded, :attr:`Recommendation.confidence` must be recorded too. The kernel
does not set a confidence *threshold* — what counts as too low to act on is
domain policy and changes by rail — but it makes the pairing unavoidable, so a
consumer always has something to apply its threshold to.

What this type cannot express, by construction
-----------------------------------------------
**An instruction.** There is no field for an order, a settlement instruction, a
release, a submission or an approval, and there is no free-form field one could
be smuggled through: every string field is either an identifier or a label
drawn from the domain's own vocabulary. ``extra="forbid"`` means an attempt to
add one is a construction error, and ``tests/test_recommendation.py`` proves it
by trying.

That is the type-level statement of the charter's rule for this class: **H
recommends, and never authorizes or submits, under any condition** (JUM-D-07).
It is enforced here as well as at the agent because a rule that lives only in
the agent moves when the agent is rewritten.

Vocabulary stays with the domain that can validate it
------------------------------------------------------
The kernel's hard rule applies unchanged: *if a type needs domain knowledge to
validate, it does not belong here.* So a funding-outcome distribution carries
the outcome **names as strings** and the kernel validates only what it can know
without the domain — that the distribution is well formed. Atreides owns
``FundingDisposition``; this module could not tell ``will_queue`` from a typo,
so it does not pretend to.

What it can check, and does: that probabilities are in range, that no outcome
appears twice, and that the distribution sums to one. Those are structural and
need no outside knowledge — the same division the envelopes make when they carry
a ``payload_digest`` instead of the payload.

Consumption
-----------
Only through a recorded C2 (Command and Control) handoff — Stop 3, already
enforced at each agent's own type check. :attr:`Recommendation.c2_handoff`
carries the basis, and like every basis in this programme it is an identifier or
a stated absence, never a bare null. Thifur-J validates any ranked path against
the approved set before acting on it; ranking here is an opinion about order,
never a claim that a path is approved.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Final, Literal, Self

from pydantic import AfterValidator, Field, model_validator

from cannae_kernel._model import (
    KernelDecimal,
    KernelModel,
    NonEmptyStr,
    NonNegativeSafeInt,
    UtcDatetime,
)
from cannae_kernel.absence import Absent, Recorded
from cannae_kernel.ids import LifecycleId
from cannae_kernel.provenance import Provenance

__all__ = [
    "RECOMMENDATION_VERSION",
    "LiquidityPeak",
    "OutcomeProbability",
    "Probability",
    "ProbabilityDistribution",
    "Recommendation",
]

RECOMMENDATION_VERSION: Final = "cannae.recommendation/1.0"

def _in_the_unit_interval(value: Decimal) -> Decimal:
    """Bound a probability, as a validator rather than a ``Field`` constraint.

    ``KernelDecimal`` supplies its own core schema, which **replaces** the
    default one — so a ``Field(ge=0, le=1)`` beside it is silently discarded and
    every probability validates, including 1.5. That is the hazard ``_model.py``
    already records for ``SafeInt``: *"Pydantic keeps only one lower bound when
    the two are combined, and a dropped bound fails silently."*

    It is recorded again here because the first version of this module made
    exactly that mistake, and the only thing that caught it was a test that tried
    to construct a probability of 1.5.
    """
    if not Decimal(0) <= value <= Decimal(1):
        raise ValueError(f"a probability must lie in [0, 1]; got {value}")
    return value


#: A probability. A decimal rather than a float, for the reason every number in
#: this kernel is: a float has already lost the exact value by the time it is
#: serialized, and two domains comparing forecasts would disagree about a number
#: neither of them got wrong.
Probability = Annotated[KernelDecimal, AfterValidator(_in_the_unit_interval)]

#: How far a distribution may miss 1 and still be one. Floating summation is not
#: the concern — these are decimals — but a model that produces 0.3333 three
#: times should not be refused for arithmetic that is correct to four places.
DISTRIBUTION_TOLERANCE: Final = Decimal("0.0001")


class OutcomeProbability(KernelModel):
    """One outcome and the probability the model assigns it.

    ``outcome`` is the **domain's** name for the outcome — Atreides'
    ``FundingDisposition`` values, for instance. The kernel carries it as a
    string because it cannot validate it: it has no way to tell ``will_queue``
    from a typo, and a type that pretended otherwise would be claiming a check
    it does not perform.
    """

    outcome: NonEmptyStr
    probability: Probability


class ProbabilityDistribution(KernelModel):
    """A well-formed distribution over outcomes the kernel does not interpret.

    Three structural rules, none of which needs domain knowledge: at least one
    outcome, no outcome twice, and the probabilities sum to one within
    :data:`DISTRIBUTION_TOLERANCE`.

    The second matters more than it looks. A duplicated outcome is how a
    distribution comes to sum to one while describing something incoherent, and
    every field in it is individually well formed.
    """

    outcomes: tuple[OutcomeProbability, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _no_outcome_twice(self) -> Self:
        names = [o.outcome for o in self.outcomes]
        if len(set(names)) != len(names):
            duplicated = sorted({n for n in names if names.count(n) > 1})
            raise ValueError(
                f"an outcome appears more than once: {duplicated}. A repeated outcome is "
                f"how a distribution sums to one while describing something incoherent"
            )
        return self

    @model_validator(mode="after")
    def _sums_to_one(self) -> Self:
        total = sum((o.probability for o in self.outcomes), start=Decimal(0))
        if abs(total - 1) > DISTRIBUTION_TOLERANCE:
            raise ValueError(
                f"the probabilities sum to {total}, not 1. A distribution that does not "
                f"sum to one is not a distribution, and the missing mass is an outcome "
                f"nobody named"
            )
        return self

    def probability_of(self, outcome: str) -> Decimal | None:
        """The probability assigned to ``outcome``, or ``None`` if it is not named.

        ``None`` rather than zero, deliberately. An outcome the model did not
        consider and an outcome it assigned zero are different statements, and a
        caller that wants to treat them alike should have to say so.
        """
        for entry in self.outcomes:
            if entry.outcome == outcome:
                return entry.probability
        return None


class LiquidityPeak(KernelModel):
    """The largest liquidity requirement the model expects, and when.

    The interval is part of the claim. A peak requirement with no window is not
    actionable: an operator cannot fund against it without knowing when it
    lands, and a number that cannot be acted on invites being acted on wrongly.
    """

    amount: KernelDecimal
    currency: NonEmptyStr
    interval_start: UtcDatetime
    interval_end: UtcDatetime

    @model_validator(mode="after")
    def _interval_is_an_interval(self) -> Self:
        if self.interval_end <= self.interval_start:
            raise ValueError(
                "a liquidity peak's interval must end after it starts; an instantaneous "
                "or reversed window cannot be funded against"
            )
        return self


class Recommendation(KernelModel):
    """What Thifur-H is allowed to say about one lifecycle.

    Every forecast field is ``Recorded[T] | Absent``. A model that does not know
    an answer records the absence and its reason rather than producing a number
    it does not believe.
    """

    schema_version: Literal["cannae.recommendation/1.0"] = RECOMMENDATION_VERSION

    recommendation_id: NonEmptyStr
    lifecycle_id: LifecycleId
    issued_at: UtcDatetime

    provenance: Provenance
    """Always ``FORECAST``. See :meth:`_a_model_output_is_a_forecast`."""

    c2_handoff: Recorded[NonEmptyStr] | Absent
    """The recorded C2 handoff this work arrived under, or the stated reason
    there is none (Stop 3). Never a bare null — the rule that produced A-T6."""

    model_ref: NonEmptyStr
    """Which model produced this, precisely enough to reproduce it. A forecast
    whose author cannot be identified cannot be scored, and an unscored model is
    indistinguishable from a good one."""

    # --- The charter's model outputs, each independently abstainable ----------

    funding_distribution: Recorded[ProbabilityDistribution] | Absent
    """Probability of each funding disposition. Outcome names are the domain's."""

    expected_queue_seconds: Recorded[NonNegativeSafeInt] | Absent
    """Expected queue duration. Seconds as an integer: a duration that survives
    JSON in every consumer, and one that cannot carry a unit ambiguity."""

    window_miss_probability: Recorded[Probability] | Absent
    """Probability of missing the settlement window."""

    peak_liquidity: Recorded[LiquidityPeak] | Absent
    """Peak liquidity requirement and the interval it falls in."""

    regime: Recorded[NonEmptyStr] | Absent
    """Regime classification. The label is the domain's vocabulary, carried as a
    string for the same reason outcome names are."""

    ranked_paths: tuple[NonEmptyStr, ...] = ()
    """Approved paths, in the model's preferred order. **Ranking is an opinion
    about order and never a claim that a path is approved** — Thifur-J validates
    every one against the approved set before acting on it. Empty means the
    model ranked nothing, which is not the same as ranking nothing first."""

    confidence: Recorded[Probability] | Absent
    """How much the model trusts this recommendation. Required whenever any
    forecast field is recorded: see :meth:`_a_number_travels_with_its_confidence`."""

    @model_validator(mode="after")
    def _a_model_output_is_a_forecast(self) -> Self:
        """``FORECAST`` and nothing else.

        A model's opinion relabelled as an observation is the Wave 2 defect in
        its most expensive form. ``POLICY_RESULT`` is refused for the same
        reason: a deterministic gate's output is reproducible and this is not,
        and a consumer that cannot tell them apart will treat a forecast as
        settled.
        """
        if self.provenance is not Provenance.FORECAST:
            raise ValueError(
                f"a recommendation is a FORECAST, not {self.provenance.value}: a model's "
                f"opinion is not an observation and not the output of a deterministic gate"
            )
        return self

    @model_validator(mode="after")
    def _a_number_travels_with_its_confidence(self) -> Self:
        """No forecast without a stated confidence.

        The kernel sets no threshold — what is too low to act on is domain
        policy and differs by rail — but it makes the pairing unavoidable, so a
        consumer always has something to apply its own threshold to. Without
        this, a model that abstained from confidence while answering everything
        else would look more certain than one that answered honestly.
        """
        answered = [
            name
            for name in (
                "funding_distribution",
                "expected_queue_seconds",
                "window_miss_probability",
                "peak_liquidity",
                "regime",
            )
            if isinstance(getattr(self, name), Recorded)
        ]
        if answered and isinstance(self.confidence, Absent):
            raise ValueError(
                f"{len(answered)} forecast field(s) are recorded ({', '.join(answered)}) "
                f"and confidence is absent ({self.confidence.reason}). A number without a "
                f"stated confidence is a low-confidence number dressed as an answer"
            )
        if self.ranked_paths and isinstance(self.confidence, Absent):
            raise ValueError(
                "paths are ranked and confidence is absent; a ranking is a forecast and "
                "carries its confidence like any other"
            )
        return self

    @property
    def abstained(self) -> bool:
        """True when the model declined to answer anything.

        A valid and useful state: *"I have nothing useful to say about this"* is
        a real answer, and one an operator can act on. It is not an error and
        the type does not treat it as one.
        """
        return not self.ranked_paths and all(
            isinstance(getattr(self, name), Absent)
            for name in (
                "funding_distribution",
                "expected_queue_seconds",
                "window_miss_probability",
                "peak_liquidity",
                "regime",
            )
        )
