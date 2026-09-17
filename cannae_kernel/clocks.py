"""The four times of an event (Research Charter §17.9).

Keeping them apart is what prevents future-information leakage: a model may act on an event
only after it was observable, and nothing may be decided before it was processed.
"""

from __future__ import annotations

from typing import Self

from pydantic import model_validator

from cannae_kernel._model import KernelModel, UtcDatetime

__all__ = ["EventTimes"]


class EventTimes(KernelModel):
    event_time: UtcDatetime
    """When the economic or operational event occurred."""

    observation_time: UtcDatetime
    """When the producing domain could first see it."""

    processing_time: UtcDatetime
    """When a model, gate or service acted on it."""

    decision_time: UtcDatetime | None = None
    """When human or system authority resolved it, if it needed resolving."""

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.observation_time < self.event_time:
            raise ValueError("observation_time must not precede event_time")
        if self.processing_time < self.observation_time:
            raise ValueError("processing_time must not precede observation_time")
        if self.decision_time is not None and self.decision_time < self.processing_time:
            raise ValueError("decision_time must not precede processing_time")
        return self
