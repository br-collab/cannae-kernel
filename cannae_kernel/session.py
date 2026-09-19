"""Which session, and which business date — both stated, never derived (W3 § R3).

Earned by an external, dated change rather than by a defect: from **6 December
2026** the Securities Information Processors run 23 hours a day, five days a week.
An Overnight session runs 9:00pm-4:00am Eastern, and Monday's trading day begins
on Sunday at 9:00pm.

Two consequences the contracts have to carry.

**The risk regime differs by session.** Overnight Limit Up-Limit Down bands are
20%. A Tier 1 National Market System stock above $3 carries 5% in the regular
session and 10% in the closing period. Same instrument, four times the room to
move, no halt. A gate that does not know which session it is in is asserting a
risk posture it has not checked.

**The funding path differs by calendar.** Fedwire Funds runs from 9:00pm Eastern
on the preceding calendar day to 7:00pm Eastern, Monday to Friday, excluding
Reserve Bank holidays; expansion to 22x6 is targeted for 2028-2029. So the cash
leg behind an obligation raised at 2am on an ordinary Tuesday and one raised at
2am on a holiday are not the same path.

A business date is stated, never derived
----------------------------------------
Atreides already refuses to guess one. From ``atreides/rails/cns.py``, the
``PROCESSING_DATE_NOT_ESTABLISHED`` break:

    market {id} fixes its processing date by {session-closure message} and has
    reported none for this position. The {n}-day settlement offset carried here
    was derived from a timestamp, which on this market does not establish a
    business date

Once Monday's trading day begins on Sunday evening, a timestamp is not even
close to sufficient: 10pm on Sunday is Monday's business date, and the same wall
clock on a Reserve Bank holiday is neither. So :class:`BusinessDate` requires
``established_by`` — what fixed it — and **this module deliberately offers no
function that turns a datetime into one.** ``tests/test_session.py`` asserts that
absence, because the easiest way to reintroduce the defect is for someone to add
the convenience helper.

What the kernel does not know
-----------------------------
Band percentages, session opening times, which days are Reserve Bank holidays and
which calendar governs which rail are all domain knowledge, and they stay in
Aureon and Atreides (CLAUDE.md: the kernel carries shape only). The kernel carries
*which session* and *which business date on which calendar*, so that a gate can be
handed them and cannot quietly proceed without them.

The session vocabulary here is the three sessions the tasking order evidences.
It is not a complete map of a trading day — there is no pre-market or post-market
member — because inventing members the order does not evidence would be inventing
domain facts. Reported in `_reports/W3-report.md` rather than guessed at.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from cannae_kernel._model import KernelModel, NonEmptyStr

__all__ = [
    "BusinessDate",
    "BusinessDateNotEstablishedError",
    "MarketSession",
    "SessionContext",
]


class MarketSession(StrEnum):
    """Which session an operation belongs to. The risk regime differs by session."""

    REGULAR = "REGULAR"
    """The regular session."""

    CLOSING_PERIOD = "CLOSING_PERIOD"
    """The closing period, which carries wider Limit Up-Limit Down bands than REGULAR."""

    OVERNIGHT = "OVERNIGHT"
    """9:00pm-4:00am Eastern from 6 December 2026. Widest bands of the three."""


class BusinessDateNotEstablishedError(LookupError):
    """Raised when a business date is required and none has been established.

    The kernel's name for what Atreides reports as
    ``PROCESSING_DATE_NOT_ESTABLISHED``: not an error in the data, but a refusal
    to invent a date that no authority has fixed.
    """


class BusinessDate(KernelModel):
    """A business date that some authority fixed, on a named calendar.

    There is no constructor from a datetime, and that is the point. A wall-clock
    instant does not establish a business date: 10pm Eastern on a Sunday belongs
    to Monday's trading day, and the same instant on a Reserve Bank holiday
    belongs to no Fedwire Funds business date at all.
    """

    value: date
    calendar: NonEmptyStr
    """Which calendar fixed it — a settlement rail's or a market's, not "the" calendar.

    Two calendars disagree about the same instant all the time, so a date with no
    calendar beside it is not yet an answer.
    """
    established_by: NonEmptyStr
    """What fixed it: the session-closure message, the rail's published calendar,
    or the operator who entered it. Never "derived from the timestamp"."""


class SessionContext(KernelModel):
    """What a gate must be told rather than work out.

    Carried on ``ApprovedIntentEnvelope`` and ``SettlementObligationEnvelope``, so
    that neither the session nor the settlement business date is reconstructed
    downstream from a timestamp.
    """

    session: MarketSession
    business_date: BusinessDate
