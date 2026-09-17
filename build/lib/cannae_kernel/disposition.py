"""The one shared vocabulary for gate outcomes (CL-JUM-001 §5.3).

Domain words (PROCEED, FUNDED, ACCEPT) map onto ``Disposition`` in their own domain; the
kernel knows none of them. ``coerce_disposition`` is for parsing values that arrive from
outside a type system. It fails safe: only an exact member value is accepted, and anything
else becomes ``INDETERMINATE``, never ``PASS`` (AUR-I-10, ATR-I-05).
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["Disposition", "coerce_disposition"]


class Disposition(StrEnum):
    PASS = "PASS"
    HOLD = "HOLD"
    BLOCK = "BLOCK"
    INDETERMINATE = "INDETERMINATE"


def coerce_disposition(value: object) -> Disposition:
    """Return the ``Disposition`` that ``value`` names exactly, or ``INDETERMINATE``.

    Accepted: a ``Disposition`` member, or a plain ``str`` equal to a member value. Case
    variants (``"pass"``), domain words (``"PROCEED"``), members of other enums, the empty
    string, ``None`` and every other type return ``INDETERMINATE``.
    """
    if isinstance(value, Disposition):
        return value
    if type(value) is str and value in Disposition.__members__.values():
        return Disposition(value)
    return Disposition.INDETERMINATE
