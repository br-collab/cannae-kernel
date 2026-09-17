"""Finality as a vector of typed assertions (Research Charter §19.5; JUM-D-13).

The kernel carries the shape only. Which rail reaches which finality type, and when, is
Atreides' knowledge and stays there.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import model_validator

from cannae_kernel._model import KernelDecimal, KernelModel, NonEmptyStr, UtcDatetime
from cannae_kernel.actor import ActorRef
from cannae_kernel.ids import EventId
from cannae_kernel.provenance import Provenance

__all__ = [
    "CONFIDENCE_FORBIDDEN",
    "CONFIDENCE_REQUIRED",
    "ConditionalityStatus",
    "FinalityAssertion",
    "FinalityType",
    "RevocabilityStatus",
]


class FinalityType(StrEnum):
    ECONOMIC_AGREEMENT = "ECONOMIC_AGREEMENT"
    CLEARING_ACCEPTANCE = "CLEARING_ACCEPTANCE"
    NOVATION_POINT = "NOVATION_POINT"
    INSTRUCTION_ACCEPTANCE = "INSTRUCTION_ACCEPTANCE"
    ASSET_FINAL = "ASSET_FINAL"
    CASH_FINAL = "CASH_FINAL"
    CONDITIONAL_LINKAGE = "CONDITIONAL_LINKAGE"
    OPERATIONAL_RECONCILIATION = "OPERATIONAL_RECONCILIATION"
    LIFECYCLE_CLOSURE = "LIFECYCLE_CLOSURE"


class ConditionalityStatus(StrEnum):
    UNCONDITIONAL = "UNCONDITIONAL"
    CONDITIONAL = "CONDITIONAL"
    UNKNOWN = "UNKNOWN"


class RevocabilityStatus(StrEnum):
    IRREVOCABLE = "IRREVOCABLE"
    REVOCABLE = "REVOCABLE"
    UNKNOWN = "UNKNOWN"


_FACTS = frozenset({Provenance.FACT_EXTERNAL, Provenance.FACT_SYNTHETIC})

CONFIDENCE_REQUIRED = frozenset({Provenance.FORECAST, Provenance.RECOMMENDATION})
"""Inferred states: a confidence must be stated (JUM-D-21)."""

CONFIDENCE_FORBIDDEN = frozenset(
    {Provenance.FACT_EXTERNAL, Provenance.FACT_SYNTHETIC, Provenance.POLICY_RESULT}
)
"""Authoritative or deterministic states: a confidence would make them look inferred.
``HUMAN_JUDGMENT`` may carry one or not."""


class FinalityAssertion(KernelModel):
    finality_type: FinalityType
    governing_rule_set: NonEmptyStr
    authoritative_actor: ActorRef
    authoritative_event_id: EventId
    effective_time: UtcDatetime
    observation_time: UtcDatetime
    evidence_reference: NonEmptyStr
    conditionality_status: ConditionalityStatus
    revocability_status: RevocabilityStatus
    provenance: Provenance
    """Not in the charter §19.5 field list; required so ``confidence`` can be checked."""
    confidence: KernelDecimal | None = None
    """Required for FORECAST and RECOMMENDATION; forbidden for facts and policy results;
    optional for HUMAN_JUDGMENT. Between 0 and 1 inclusive."""

    @model_validator(mode="after")
    def _inferred_never_looks_authoritative(self) -> Self:
        if self.provenance in CONFIDENCE_FORBIDDEN and self.confidence is not None:
            raise ValueError(
                f"a {self.provenance.value} assertion is authoritative or deterministic and "
                "must not carry a confidence"
            )
        if self.provenance in CONFIDENCE_REQUIRED and self.confidence is None:
            raise ValueError(
                f"a {self.provenance.value} assertion is inferred and must carry a confidence"
            )
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1 inclusive")
        return self

    @model_validator(mode="after")
    def _fact_not_observed_before_effect(self) -> Self:
        # Forecasts and recommendations may describe a future effective time (JUM-D-22).
        if self.provenance in _FACTS and self.observation_time < self.effective_time:
            raise ValueError(
                f"a {self.provenance.value} assertion cannot be observed before it takes effect"
            )
        return self
