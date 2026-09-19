"""Absence is a value, with a reason, and it never reads as a pass (W3 § R2).

Earned by four defects in Wave 2, all the same shape:

- **W2B7-V-01** — the settlement dashboard marked the DSOR (Decision System of
  Record) phase "recorded" on a quorum hold. Atreides writes nothing there,
  *because no instruction was issued* — and that reason existed nowhere, so the
  surface had nothing truthful to show and showed a pass.
- **The ledger segment** — `DSOR ${rid}` printed with an empty identifier beside
  the claim.
- **#36, the `na` state** — once the absence had a name, it still had no styling,
  so a phase that recorded nothing rendered *brighter* than one not yet reached.
- **Eight silent read-path catches** — an exception became an empty value that
  read as "fine".

The common failure is that absence was represented by `None`, by an empty string
or by omission, and every one of those is indistinguishable from a value that
simply has not arrived yet. So the consumer picked the cheerful reading.

Three absences, and they are not the same
-----------------------------------------
The order requires "nothing was written, and here is why" to be distinct from
null, from zero **and from 'not yet known'**. :class:`AbsenceKind` is that
distinction:

- ``NOTHING_RECORDED`` — a write could have happened and did not. The quorum hold
  is this: no instruction was issued, so no record exists, and none ever will for
  this operation.
- ``NOT_YET_KNOWN`` — it may still arrive. A pending acknowledgement.
- ``NOT_APPLICABLE`` — it cannot apply here at all.

A consumer that treats the three alike is making a claim it has not checked: the
first is settled, the second is in flight, the third is a category error.

Why `None` is not enough
------------------------
`Recorded[T]` may legitimately hold `None` or zero — a recorded absence of
quantity is not the same as no record of quantity. Keeping the two apart is the
whole point, so :class:`Recorded` and :class:`Absent` are separate types behind a
separate types rather than one optional field.

``Recorded[T] | Absent`` is the shape that crosses a boundary. No explicit
discriminator is needed: the two carry different ``state`` literals and the kernel
base model forbids unknown fields, so an absence relabelled as a record is refused
for want of a ``value``. ``tests/test_absence.py`` proves that rather than assuming
it.

Presentation
------------
R2 says the rule reaches the surface, and #36 is why it has to: a contract that
can express absence and a surface that cannot display it is still a surface that
lies. :attr:`Absent.label` is what an absence renders as. It is never empty and
never a word a reader could mistake for a result, and
``tests/test_absence.py`` asserts both.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Generic, Literal, TypeVar

from cannae_kernel._model import KernelModel, NonEmptyStr
from cannae_kernel.disposition import Disposition

__all__ = [
    "AbsenceKind",
    "Absent",
    "MissingValueError",
    "Recorded",
    "disposition_of",
    "require_recorded",
]

ValueT = TypeVar("ValueT")


class AbsenceKind(StrEnum):
    NOTHING_RECORDED = "NOTHING_RECORDED"
    """A write could have happened and did not. Settled: none will arrive."""

    NOT_YET_KNOWN = "NOT_YET_KNOWN"
    """It may still arrive. In flight, not settled."""

    NOT_APPLICABLE = "NOT_APPLICABLE"
    """It cannot apply in this case at all."""


#: What each kind renders as. Deliberately none of them is empty, and none is a
#: word that could be read as a result: #36 was caused by an absence with nothing
#: to show, which the surface rendered louder than "not reached".
_LABELS = {
    AbsenceKind.NOTHING_RECORDED: "nothing recorded",
    AbsenceKind.NOT_YET_KNOWN: "not yet known",
    AbsenceKind.NOT_APPLICABLE: "not applicable",
}


class MissingValueError(LookupError):
    """Raised when a caller demands a value that was never recorded."""


class Absent(KernelModel):
    """Nothing was recorded, which kind of nothing it is, and why."""

    state: Literal["absent"] = "absent"
    kind: AbsenceKind
    reason: NonEmptyStr
    """Why there is no value. Part of the record, not a comment.

    "no instruction was issued" is the reason a quorum hold persists nothing. A
    reader who is told only that the field is empty has to guess; a reader who is
    told the reason does not.
    """

    @property
    def label(self) -> str:
        """What a surface shows. Never empty, never mistakable for a result."""
        return f"{_LABELS[self.kind]} · {self.reason}"

    @property
    def disposition(self) -> Disposition:
        """Absent evidence is INDETERMINATE. It is never PASS (AUR-I-10, ATR-I-05)."""
        return Disposition.INDETERMINATE


class Recorded(KernelModel, Generic[ValueT]):
    """A value that was recorded — including a recorded ``None`` or zero.

    A recorded absence of quantity is not the same as no record of quantity, so
    this stays distinct from :class:`Absent` even when it holds nothing much.
    """

    state: Literal["recorded"] = "recorded"
    value: ValueT

    @property
    def disposition(self) -> Disposition:
        """A record exists. What it *means* is the domain's gate to decide."""
        return Disposition.PASS


def require_recorded(maybe: Recorded[ValueT] | Absent) -> ValueT:
    """The recorded value, or raise carrying the reason there is none."""
    if isinstance(maybe, Absent):
        raise MissingValueError(f"{_LABELS[maybe.kind]}: {maybe.reason}")
    return maybe.value


def disposition_of(maybe: Recorded[ValueT] | Absent) -> Disposition:
    """``INDETERMINATE`` for any absence, whatever kind it is.

    The one rule this module exists to make unavoidable: missing evidence never
    reads as a pass. Written as a function as well as a property so a caller
    holding either type gets the same answer without asking which it has.
    """
    return maybe.disposition
