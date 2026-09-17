"""Who did something, and on what entitlement (AUR-I-03)."""

from __future__ import annotations

from enum import StrEnum

from cannae_kernel._model import KernelModel, NonEmptyStr
from cannae_kernel.ids import ActorId

__all__ = ["ActorKind", "ActorRef"]


class ActorKind(StrEnum):
    HUMAN = "HUMAN"
    DETERMINISTIC_SERVICE = "DETERMINISTIC_SERVICE"
    AGENT_R = "AGENT_R"
    """Thifur-R: deterministic, zero-variance agent."""
    AGENT_J = "AGENT_J"
    """Thifur-J: selects among pre-approved paths."""
    AGENT_H = "AGENT_H"
    """Thifur-H: adaptive. Recommends; never authorizes (JUM-D-07)."""
    EXTERNAL_EMULATOR = "EXTERNAL_EMULATOR"
    SYNTHETIC_MEMBER = "SYNTHETIC_MEMBER"


class ActorRef(KernelModel):
    """A reference to an actor. ``AuthorityRecord`` decides which kinds may authorize."""

    actor_id: ActorId
    actor_kind: ActorKind
    role: NonEmptyStr
    entitlement_refs: tuple[NonEmptyStr, ...]
    authenticated: bool
