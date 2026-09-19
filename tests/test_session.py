"""R3: the session and the business date are stated, and cannot be derived.

The defect this prevents has not happened here yet — it is dated. From 6 December
2026 the Securities Information Processors run 23/5, Monday's trading day begins
on Sunday at 9:00pm Eastern, and Overnight Limit Up-Limit Down bands are 20%
against 5% in the regular session.

From that date, two things that look like arithmetic stop being arithmetic:
which session an instant belongs to, and which business date it falls on.

The load-bearing test is `test_no_one_can_derive_a_business_date_from_a_timestamp`.
The others are about the shape; that one is about the shape staying that way,
because the easiest way to reintroduce the defect is for somebody to add the
convenience helper that everyone will then use.
"""

from __future__ import annotations

import inspect
from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from cannae_kernel import session as session_module
from cannae_kernel.session import (
    BusinessDate,
    BusinessDateNotEstablishedError,
    MarketSession,
    SessionContext,
)

SUNDAY_2200_ET = datetime(2026, 12, 6, 3, 0, tzinfo=UTC)
"""10:00pm Eastern on Sunday 6 December 2026 — which is Monday's trading day."""


def _business_date() -> BusinessDate:
    return BusinessDate(
        value=date(2026, 12, 7),
        calendar="Fedwire Funds",
        established_by="the rail's published calendar",
    )


# --- the invariant ---------------------------------------------------------------


def test_no_one_can_derive_a_business_date_from_a_timestamp() -> None:
    """The helper must not exist. If it exists, everyone calls it.

    Atreides reports deriving a settlement offset from a timestamp as
    PROCESSING_DATE_NOT_ESTABLISHED. This is that refusal made structural: there
    is nothing in this module that takes a datetime.
    """
    for name, member in inspect.getmembers(session_module):
        if name.startswith("_") or not callable(member):
            continue
        if getattr(member, "__module__", None) != session_module.__name__:
            continue
        try:
            signature = inspect.signature(member)
        except ValueError:
            continue  # a builtin or exception type has no introspectable signature
        for parameter in signature.parameters.values():
            assert parameter.annotation is not datetime, (
                f"{name} takes a datetime, so a business date can be derived from one"
            )

    for forbidden in ("from_datetime", "from_timestamp", "of_instant", "for_datetime"):
        assert not hasattr(BusinessDate, forbidden), (
            f"BusinessDate.{forbidden} exists; a wall-clock instant does not "
            f"establish a business date"
        )


def test_a_business_date_must_say_who_established_it() -> None:
    """A date with no authority behind it is a guess with a type annotation."""
    with pytest.raises(ValidationError):
        BusinessDate(value=date(2026, 12, 7), calendar="Fedwire Funds")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        BusinessDate(value=date(2026, 12, 7), calendar="Fedwire Funds", established_by="")


def test_a_business_date_must_say_which_calendar_fixed_it() -> None:
    """Two calendars disagree about the same instant, so the date alone is not an answer."""
    with pytest.raises(ValidationError):
        BusinessDate(value=date(2026, 12, 7), established_by="the rail")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        BusinessDate(value=date(2026, 12, 7), calendar="", established_by="the rail")


def test_the_same_instant_is_a_different_business_date_on_a_different_calendar() -> None:
    """Why `calendar` is required rather than assumed: this is the ordinary case."""
    fedwire = BusinessDate(
        value=date(2026, 12, 7),
        calendar="Fedwire Funds",
        established_by="the rail's published calendar",
    )
    market = BusinessDate(
        value=date(2026, 12, 6),
        calendar="NMS trading day",
        established_by="the session-closure message",
    )
    assert fedwire != market, "two calendars' answers are being treated as one"


# --- the session -----------------------------------------------------------------


def test_the_three_sessions_the_order_evidences_are_present() -> None:
    assert {s.value for s in MarketSession} == {"REGULAR", "CLOSING_PERIOD", "OVERNIGHT"}


def test_a_gate_is_told_the_session_rather_than_working_it_out() -> None:
    """A gate that does not know its session asserts a risk posture it has not checked."""
    context = SessionContext(session=MarketSession.OVERNIGHT, business_date=_business_date())
    assert context.session is MarketSession.OVERNIGHT

    with pytest.raises(ValidationError):
        SessionContext(business_date=_business_date())  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        SessionContext(session=MarketSession.OVERNIGHT)  # type: ignore[call-arg]


def test_the_session_cannot_be_inferred_from_the_context_it_is_given() -> None:
    """The 23/5 case, concretely: the same instant, two sessions, and the type
    refuses to choose. Sunday 10pm Eastern is Monday's trading day; nothing in
    the kernel turns that instant into either a session or a date."""
    for session in (MarketSession.OVERNIGHT, MarketSession.REGULAR):
        context = SessionContext(session=session, business_date=_business_date())
        assert context.session is session
    assert not hasattr(SessionContext, "for_instant")
    assert SUNDAY_2200_ET.tzinfo is UTC  # the instant exists; it decides nothing


# --- the refusal -----------------------------------------------------------------


def test_the_refusal_has_a_name_a_domain_can_raise() -> None:
    """Atreides' PROCESSING_DATE_NOT_ESTABLISHED, available to every domain."""
    assert issubclass(BusinessDateNotEstablishedError, LookupError)
    with pytest.raises(BusinessDateNotEstablishedError):
        raise BusinessDateNotEstablishedError(
            "market XNYS fixes its processing date by a session-closure message "
            "and has reported none"
        )
