"""A versioned halt that every gate consults (ATR-I-06).

A halt that only one component can see is not a halt. The context is a value that is passed
through every gate, and ``gate_under_halt`` is the single rule for reading it.
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from cannae_kernel._model import KernelModel, NonEmptyStr, UtcDatetime
from cannae_kernel.actor import ActorRef
from cannae_kernel.disposition import Disposition
from cannae_kernel.domains import Domain
from cannae_kernel.ids import HaltId

__all__ = ["ALL_DOMAINS", "HaltContext", "gate_under_halt"]

ALL_DOMAINS: Literal["ALL"] = "ALL"


class HaltContext(KernelModel):
    halt_id: HaltId
    version: int = Field(ge=1)
    """Increases each time the halt is declared, widened, narrowed or cleared."""
    active: bool
    scope: tuple[Domain, ...] | Literal["ALL"]
    declared_by: ActorRef
    declared_at: UtcDatetime
    reason: NonEmptyStr

    @model_validator(mode="after")
    def _scope_well_formed(self) -> Self:
        if isinstance(self.scope, tuple):
            if not self.scope:
                raise ValueError('scope must name at least one domain, or be "ALL"')
            if len(set(self.scope)) != len(self.scope):
                raise ValueError("scope must not repeat a domain")
        return self


def gate_under_halt(ctx: HaltContext, domain: Domain) -> Disposition:
    """``BLOCK`` when ``ctx`` is active and covers ``domain``; otherwise ``PASS``.

    ``domain`` must be a ``Domain`` member. A raw string raises ``TypeError`` rather than
    being compared, because a misspelt domain that silently fell outside the scope would pass
    a gate during a declared halt.
    """
    if not isinstance(ctx, HaltContext):
        raise TypeError("ctx must be a HaltContext")
    if not isinstance(domain, Domain):
        raise TypeError(f"domain must be a Domain member, not {type(domain).__name__}")
    if ctx.active and (ctx.scope == ALL_DOMAINS or domain in ctx.scope):
        return Disposition.BLOCK
    return Disposition.PASS
