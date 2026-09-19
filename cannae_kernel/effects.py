"""Every operation declares what it does outside this process (W3 § R4).

Earned by aureon #34. A route inventory asked each endpoint *"does this mutate
application state"*, answered **no** for `/api/email/test` and `/api/test/email`,
and left both open to anonymous callers. Both send real email from a named
person's account using the operator's credentials. Nothing in the process
changed, and something in the world did.

The question is wrong, not the answer
-------------------------------------
"Does application state change" is a question about *this* process. The one that
matters is:

    **Is anything irreversible outside this process?**

A reply cannot be unsent. A payment cannot be unmade. A quota cannot be
un-spent, and the record of who spent it sits in somebody else's logs. None of
those touch application state, and all of them are effects.

The taxonomy
------------
:class:`ExternalEffect` names what an operation reaches. The list comes from the
tasking order — "sends, pays, submits, publishes, or writes to anything the
process does not own" — plus one more that the aureon sweep found and the order
did not anticipate: an unauthenticated caller driving metered third-party calls
under the operator's credentials.

An empty effect set means **contained**: everything this operation does can be
undone by this process. It is a claim, and it is made explicitly, because the
defect being prevented is a claim nobody made on purpose.

What the kernel decides, and what it does not
---------------------------------------------
The kernel says an operation with any external effect is **not contained**.
Whether an uncontained operation requires an authenticated operator, a second
approver or a halt check is domain policy, and stays in the domains. What the
kernel removes is the possibility of an operation having no declaration at all:
there is no default, so an operation that has never been classified cannot be
constructed.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import field_validator

from cannae_kernel._model import KernelModel, NonEmptyStr

__all__ = [
    "ExternalEffect",
    "OperationEffects",
]


class ExternalEffect(StrEnum):
    """What an operation reaches outside the process it runs in."""

    SENDS = "SENDS"
    """Email, message or notification to a person or system. Cannot be unsent."""

    PAYS = "PAYS"
    """Moves value. The one everybody already treats carefully."""

    SUBMITS = "SUBMITS"
    """Hands an instruction to a rail, venue or counterparty."""

    PUBLISHES = "PUBLISHES"
    """Makes something visible outside the process — a feed, a page, a repository."""

    WRITES_FOREIGN_STORE = "WRITES_FOREIGN_STORE"
    """Writes to storage this process does not own: a mounted volume, a database,
    another service's store. It outlives the process, so the process cannot undo it."""

    CONSUMES_CREDENTIALED_QUOTA = "CONSUMES_CREDENTIALED_QUOTA"
    """Spends a metered third-party allowance under our own credentials.

    Not in the tasking order's list; found by the aureon sweep. It reads as
    harmless because nothing is written anywhere we can see — and the traffic
    lands in a third party's logs attributed to us, the allowance does not come
    back, and the caller chose the volume.
    """


class OperationEffects(KernelModel):
    """One operation's declaration. There is no default: silence is not a claim."""

    operation: NonEmptyStr
    effects: tuple[ExternalEffect, ...]
    """Empty means contained. Order and duplicates are normalised so that two
    declarations of the same effects have the same canonical bytes."""
    note: NonEmptyStr
    """Why these and not others — the reasoning, so a later reader can disagree
    with it. A declaration with no reasoning is the unreviewable kind that
    produced #34."""

    @field_validator("effects", mode="before")
    @classmethod
    def _normalised(cls, effects: object) -> object:
        """Sort and deduplicate, so two declarations of the same effects are equal.

        Before validation rather than after: a model validator cannot return a
        different instance from ``__init__``, and without normalisation the same
        operation declared in two orders would carry two digests, which makes the
        freeze noisy for no reason.
        """
        if not isinstance(effects, (list, tuple)):
            return effects
        return tuple(sorted({ExternalEffect(e) for e in effects}, key=lambda e: e.value))

    @property
    def is_contained(self) -> bool:
        """True when everything this operation does can be undone by this process."""
        return not self.effects

    @property
    def is_irreversible_outside(self) -> bool:
        """The question R4 says to ask, by name."""
        return bool(self.effects)
