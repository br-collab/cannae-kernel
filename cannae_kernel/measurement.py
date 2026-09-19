"""A reading carries its own provenance, and the consumer refuses (W3 § R1).

Earned by three defects in Wave 2, all the same shape:

- **F1** — with FRED and the OFR page both unreachable, a fallback constant
  (VIX 24.0, high-yield spread 4.25, curve -20) flowed into the stress proxy and
  produced a plausible 0.38, which gate 6 read as PASS. A missing reading became
  permission.
- **Cato-FICC-MCP #2** — `parseFloat(ofr_stress_index?.value ?? "0")` coalesced
  before the usability guard, so a failed fetch returned PROCEED, "All doctrine
  thresholds clear".
- **W2-ADD-03** — every fill recorded the same `price_source` regardless of where
  the price came from.

In each case the number was fine as a number. What was missing was the answer to
"where did this come from, and when was it seen".

Why a type and not a rule
-------------------------
The governing finding of Wave 2, in four independent places:

    An invariant enforced by a filter one layer up is fragile.
    An invariant enforced by the consumer's own type check is not.

The Python Cato gate accepts a bare float and trusts whoever passed it. It
survives only because one caller remembers to filter, and **a second caller added
later reintroduces the whole class silently**. So the check lives here, in the
type a gate asks for, where a new caller cannot route around it.

The three types
---------------
- :class:`Measurement` — a value that was **observed**: it has a `provenance`, a
  `source` and an `observed_at`. Any provenance may be carried, because a
  synthetic or forecast reading is allowed to cross a boundary.
- :class:`Constant` — a value with **no observation behind it**. It has no
  `observed_at`, because there was no observation, and it carries the `reason`
  there was none. A value without an observation time is not a measurement; it is
  a constant, and this is how it says so.
- :class:`ObservedFact` — what a gate that requires an observation accepts.
  It cannot be constructed from a :class:`Constant` at all, and not from a
  :class:`Measurement` whose provenance is outside the admitted set.

A gate writes ``def evaluate(stress: ObservedFact)``, and the fabricated 0.38
cannot reach it: `Constant` has no path to `ObservedFact`, and a synthetic
reading is refused unless the gate says, in its own signature, that it admits
synthetic input.

What the kernel does not decide
-------------------------------
Which provenances a particular gate admits is domain policy, so
:func:`require_observation` takes an ``admitting`` set. The default is the strict
one — an external authority's report and nothing else. A domain that wants to act
on a derived reading passes ``POLICY_RESULT`` explicitly, which makes the choice
visible at the call site and in review, rather than implicit in a missing filter.
"""

from __future__ import annotations

from collections.abc import Iterable, Set
from typing import Annotated, Literal, NoReturn, Self

from pydantic import Field, model_validator

from cannae_kernel._model import KernelDecimal, KernelModel, NonEmptyStr, UtcDatetime
from cannae_kernel.provenance import Provenance

__all__ = [
    "ADMISSIBLE_WITH_DERIVATION",
    "OBSERVED",
    "Constant",
    "Measurement",
    "NotAnObservationError",
    "ObservedFact",
    "Reading",
    "require_observation",
]


OBSERVED: Set[Provenance] = frozenset({Provenance.FACT_EXTERNAL})
"""What an observation is: reported by an external authority.

``FACT_SYNTHETIC`` is deliberately outside it. A synthetic reading may cross a
boundary and may be displayed, but it may never satisfy a gate that requires an
observation — the recommendation from P08 §4 on the simulated-price question: do
not block the input, type it, and make the consumer refuse.
"""

ADMISSIBLE_WITH_DERIVATION: Set[Provenance] = frozenset(
    {Provenance.FACT_EXTERNAL, Provenance.POLICY_RESULT}
)
"""For a gate that also acts on a value computed from live external inputs.

Offered as a named set so the decision is legible: the aureon stress proxy is a
real computation over real data, but it is not the official reading, and a gate
acting on it is making a choice that should be visible at its call site.
"""


class NotAnObservationError(ValueError):
    """Raised when a reading cannot satisfy a gate that requires an observation."""


class ObservedFact(KernelModel):
    """A reading a gate may act on. There is no way to build one from a constant.

    Constructed through :func:`require_observation` or :meth:`Measurement.observed`,
    never directly from untyped input, so every instance has an observation behind
    it by construction.
    """

    value: KernelDecimal
    provenance: Provenance
    source: NonEmptyStr
    observed_at: UtcDatetime

    @model_validator(mode="after")
    def _provenance_is_an_observation(self) -> Self:
        # The default set, checked again here: require_observation may widen it for
        # a caller, but nothing may construct an ObservedFact from a forecast or a
        # recommendation, which are not readings of anything.
        if self.provenance in (Provenance.FORECAST, Provenance.RECOMMENDATION):
            raise ValueError(
                f"a {self.provenance.value} is not an observation: it describes "
                "something that was not seen"
            )
        return self


class Measurement(KernelModel):
    """A value that was observed, with where it came from and when it was seen."""

    kind: Literal["measurement"] = "measurement"
    value: KernelDecimal
    provenance: Provenance
    source: NonEmptyStr
    """The publisher, series or emulator the value was read from."""
    observed_at: UtcDatetime

    def observed(self, *, admitting: Iterable[Provenance] = OBSERVED) -> ObservedFact:
        """This reading as something a gate may act on, or raise.

        ``admitting`` is the gate's own statement of what it will accept.
        """
        admitted = frozenset(admitting)
        if self.provenance not in admitted:
            raise NotAnObservationError(
                f"{self.source}: a {self.provenance.value} reading cannot satisfy a gate "
                f"that requires one of {sorted(p.value for p in admitted)}"
            )
        return ObservedFact(
            value=self.value,
            provenance=self.provenance,
            source=self.source,
            observed_at=self.observed_at,
        )


class Constant(KernelModel):
    """A value with no observation behind it, and the reason there is none.

    This is what a fallback default is. It has no ``observed_at`` field, so it
    cannot be given one, and no ``provenance``, because provenance answers where an
    observation came from and there was no observation.
    """

    kind: Literal["constant"] = "constant"
    value: KernelDecimal
    source: NonEmptyStr
    """What supplied the constant — the module or fixture, not a publisher."""
    reason: NonEmptyStr
    """Why there is no observation. Part of the record, not a comment."""

    def observed(self, *, admitting: Iterable[Provenance] = OBSERVED) -> NoReturn:
        """Always raises. A constant is evidence of nothing.

        Present so that a caller holding a :data:`Reading` can call ``observed()``
        without first asking which of the two it has: the refusal is the same
        refusal either way, and it cannot be forgotten.
        """
        raise NotAnObservationError(
            f"{self.source}: no observation was made ({self.reason}), so this value "
            "cannot satisfy a gate that requires one"
        )


Reading = Annotated[Measurement | Constant, Field(discriminator="kind")]
"""Either kind, tagged, so a serialized reading cannot be read back as the other."""


def require_observation(
    reading: Measurement | Constant, *, admitting: Iterable[Provenance] = OBSERVED
) -> ObservedFact:
    """The consumer's check, in one place.

    A gate that takes :class:`ObservedFact` has already refused everything else by
    its signature. This is for the boundary where a reading arrives untyped and
    something has to do the refusing.
    """
    return reading.observed(admitting=admitting)
