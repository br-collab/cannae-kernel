"""R2: absence carries a reason, and it never reads as a pass.

The four Wave 2 defects this generalises, each represented by a test below:

- W2B7-V-01 — the DSOR phase marked "recorded" on a quorum hold, which persists
  nothing *because no instruction was issued*;
- the ledger segment printing `DSOR ` with an empty identifier;
- #36 — the `na` state rendering brighter than "not reached", because an absence
  with nothing to show has nothing to style;
- eight read-path catches where an exception became an empty value that read as
  fine.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import TypeAdapter, ValidationError

from cannae_kernel.absence import (
    AbsenceKind,
    Absent,
    MissingValueError,
    Recorded,
    disposition_of,
    require_recorded,
)
from cannae_kernel.disposition import Disposition

QUORUM_HOLD = Absent(
    kind=AbsenceKind.NOTHING_RECORDED,
    reason="no instruction was issued",
)


# --- the rule the module exists for --------------------------------------------


@pytest.mark.parametrize("kind", list(AbsenceKind))
def test_absence_is_never_a_pass(kind: AbsenceKind) -> None:
    """Whatever kind of nothing it is, it is not permission."""
    absent = Absent(kind=kind, reason="the publisher was unreachable")
    assert absent.disposition is Disposition.INDETERMINATE
    assert disposition_of(absent) is Disposition.INDETERMINATE
    assert disposition_of(absent) is not Disposition.PASS


def test_the_quorum_hold_says_why_it_recorded_nothing() -> None:
    """W2B7-V-01. The surface claimed a record; the reason existed nowhere."""
    assert disposition_of(QUORUM_HOLD) is Disposition.INDETERMINATE
    assert "no instruction was issued" in QUORUM_HOLD.label


def test_an_absence_must_carry_a_reason() -> None:
    """An absence with no reason leaves the reader guessing, which is the defect."""
    with pytest.raises(ValidationError):
        Absent(kind=AbsenceKind.NOTHING_RECORDED)  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        Absent(kind=AbsenceKind.NOTHING_RECORDED, reason="")


# --- absence is not None, and not zero -----------------------------------------


@pytest.mark.parametrize("value", [None, 0, Decimal("0.00"), "", False])
def test_a_recorded_nothing_is_still_a_record(value: object) -> None:
    """A recorded absence of quantity is not the same as no record of quantity."""
    recorded: Recorded[object] = Recorded(value=value)
    assert recorded.disposition is Disposition.PASS
    assert require_recorded(recorded) == value
    assert not isinstance(recorded, Absent)


def test_demanding_an_absent_value_raises_with_the_reason() -> None:
    with pytest.raises(MissingValueError) as missing:
        require_recorded(QUORUM_HOLD)
    assert "no instruction was issued" in str(missing.value)
    assert "nothing recorded" in str(missing.value)


# --- the three kinds are not interchangeable -----------------------------------


def test_the_three_kinds_are_distinguishable() -> None:
    """Settled, in flight and category error are different facts about the world."""
    assert len(set(AbsenceKind)) == 3
    labels = {Absent(kind=kind, reason="r").label for kind in AbsenceKind}
    assert len(labels) == 3, "two kinds render identically, so a reader cannot tell them apart"


def test_nothing_recorded_is_not_the_same_as_not_yet_known() -> None:
    settled = Absent(kind=AbsenceKind.NOTHING_RECORDED, reason="no instruction was issued")
    pending = Absent(kind=AbsenceKind.NOT_YET_KNOWN, reason="the rail has not acknowledged")
    assert settled != pending
    assert settled.label != pending.label


# --- presentation: #36 -----------------------------------------------------------


@pytest.mark.parametrize("kind", list(AbsenceKind))
def test_an_absence_always_has_something_to_show(kind: AbsenceKind) -> None:
    """#36: an absence with nothing to render is what rendered as a pass."""
    label = Absent(kind=kind, reason="the publisher was unreachable").label
    assert label.strip(), "the absence renders as nothing at all"


@pytest.mark.parametrize("kind", list(AbsenceKind))
def test_no_absence_renders_as_a_word_that_reads_like_a_result(kind: AbsenceKind) -> None:
    label = Absent(kind=kind, reason="the publisher was unreachable").label.lower()
    # "nothing recorded" contains "recorded", and that is fine: what matters is
    # that the label *leads* with the negation, so no reader — and no surface
    # truncating it — can take the first word for a result.
    assert label.split()[0] in ("nothing", "not"), (
        f"an absence renders as {label!r}, which does not lead with the negation"
    )
    for forbidden in ("pass", "clear", "satisfied", "complete"):
        assert forbidden not in label, f"an absence renders as {label!r}, which reads as a result"


# --- the boundary ---------------------------------------------------------------


def test_a_serialized_absence_cannot_be_read_back_as_a_record() -> None:
    """No explicit discriminator: the literals plus extra="forbid" already do it."""
    adapter: TypeAdapter[Recorded[str] | Absent] = TypeAdapter(Recorded[str] | Absent)

    for value in (Recorded[str](value="rec_1"), QUORUM_HOLD):
        assert adapter.validate_json(adapter.dump_json(value)) == value

    disguised = adapter.dump_json(QUORUM_HOLD).replace(b'"absent"', b'"recorded"')
    with pytest.raises(ValidationError):
        adapter.validate_json(disguised)


def test_the_reason_survives_the_boundary() -> None:
    """A reason dropped in transit leaves the far side with a bare absence."""
    adapter: TypeAdapter[Recorded[str] | Absent] = TypeAdapter(Recorded[str] | Absent)
    round_tripped = adapter.validate_json(adapter.dump_json(QUORUM_HOLD))
    assert isinstance(round_tripped, Absent)
    assert round_tripped.reason == "no instruction was issued"
