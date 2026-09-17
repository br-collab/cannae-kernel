"""The record of an authorizing decision (Research Charter §7, §8; JUM-D-07, JUM-D-15).

Only a human or a deterministic service may authorize, and only once authenticated. No agent
class authorizes; the adaptive Thifur-H class in particular may only recommend.
"""

from __future__ import annotations

from typing import Self

from pydantic import model_validator

from cannae_kernel._model import KernelModel, NonEmptyStr, UtcDatetime
from cannae_kernel.actor import ActorKind, ActorRef

__all__ = ["AUTHORIZING_KINDS", "AuthorityRecord"]

AUTHORIZING_KINDS: frozenset[ActorKind] = frozenset(
    {ActorKind.HUMAN, ActorKind.DETERMINISTIC_SERVICE}
)


class AuthorityRecord(KernelModel):
    decision_type: NonEmptyStr
    authorizing_actor: ActorRef
    timestamp: UtcDatetime
    rationale: NonEmptyStr
    quorum_refs: tuple[NonEmptyStr, ...]
    """References to the other authority records that make up a quorum. Empty when none."""
    independence_asserted: bool
    """True when the record claims its quorum members are independent actors (JUM-D-15)."""

    @model_validator(mode="after")
    def _authorizer_is_entitled(self) -> Self:
        kind = self.authorizing_actor.actor_kind
        if kind not in AUTHORIZING_KINDS:
            raise ValueError(
                f"{kind.value} may not authorize; only HUMAN or DETERMINISTIC_SERVICE may"
            )
        if not self.authorizing_actor.authenticated:
            raise ValueError("the authorizing actor must be authenticated")
        return self
