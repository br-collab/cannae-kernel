"""What kind of claim a value is (Research Charter §17.6, §19.9 invariant 11)."""

from __future__ import annotations

from enum import StrEnum

__all__ = ["Provenance"]


class Provenance(StrEnum):
    FACT_EXTERNAL = "FACT_EXTERNAL"
    """Reported by an external authority: a venue, clearing house or rail."""

    FACT_SYNTHETIC = "FACT_SYNTHETIC"
    """Reported by a synthetic emulator standing in for an external authority."""

    FORECAST = "FORECAST"
    """Produced by a model about something not yet observed."""

    RECOMMENDATION = "RECOMMENDATION"
    """Advice from a model or agent. It authorizes nothing."""

    HUMAN_JUDGMENT = "HUMAN_JUDGMENT"
    """A decision or assessment made by a person."""

    POLICY_RESULT = "POLICY_RESULT"
    """The output of a deterministic policy or gate."""
