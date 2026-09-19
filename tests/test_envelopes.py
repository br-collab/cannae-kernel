"""Contract 1 of 5: `ApprovedIntentEnvelope` — Aureon to Legiones Cannenses.

The skeleton that crosses the boundary. The approved terms stay in
`aureon.contracts.approved_intent`, which is the domain that can validate them,
and are referenced here by `payload_digest` — JUM-D-01's rule for
`ObligationAcceptanceRecord` ("references its digest rather than copying its
economics") applied upstream.

These tests cover what the envelope *does*: the lineage cannot have a hole in it,
an approval cannot claim to be anything but a human judgment, and the payload
reference is a reference rather than a copy. The freeze itself — version and
shape — is `test_envelope_freeze.py`.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from pydantic import ValidationError

from cannae_kernel.actor import ActorKind, ActorRef
from cannae_kernel.canonical import digest
from cannae_kernel.clocks import EventTimes
from cannae_kernel.effects import ExternalEffect, OperationEffects
from cannae_kernel.envelopes import (
    APPROVED_INTENT_VERSION,
    EXECUTION_EVENT_VERSION,
    ApprovedIntentEnvelope,
    ExecutionEvent,
)
from cannae_kernel.ids import ActorId, EventId, IntentId, LifecycleId
from cannae_kernel.provenance import Provenance
from cannae_kernel.session import BusinessDate, MarketSession, SessionContext

INTENT = IntentId("int_01M2P20SY00000000000000001")
LIFECYCLE = LifecycleId("lif_01M2P20SY00000000000000001")
PAYLOAD = "sha256:" + "a" * 64
PRIOR = "sha256:" + "b" * 64
T0 = datetime(2026, 12, 7, 14, 30, tzinfo=UTC)


def _session() -> SessionContext:
    return SessionContext(
        session=MarketSession.OVERNIGHT,
        business_date=BusinessDate(
            value=date(2026, 12, 7),
            calendar="Fedwire Funds",
            established_by="the rail's published calendar",
        ),
    )


def _envelope(**overrides: object) -> ApprovedIntentEnvelope:
    fields: dict[str, object] = {
        "envelope_id": INTENT,
        "lifecycle_id": LIFECYCLE,
        "revision": 1,
        "prior_digest": None,
        "session": _session(),
        "approved_by": ActorRef(
            actor_id=ActorId("act_01M2P20SY00000000000000001"),
            actor_kind=ActorKind.HUMAN,
            role="Chief Investment Officer",
            entitlement_refs=("approve_intent",),
            authenticated=True,
        ),
        "provenance": Provenance.HUMAN_JUDGMENT,
        "effects": OperationEffects(
            operation="release approved intent to L.C.",
            effects=(ExternalEffect.PUBLISHES,),
            note="hands the approved intent to the middle layer; it leaves this process",
        ),
        "payload_digest": PAYLOAD,
    }
    fields.update(overrides)
    return ApprovedIntentEnvelope(**fields)  # type: ignore[arg-type]


# --- the lineage cannot have a hole in it ---------------------------------------


def test_a_first_revision_supersedes_nothing() -> None:
    assert _envelope().prior_digest is None


def test_a_later_revision_must_name_what_it_supersedes() -> None:
    """Otherwise revision 4 with no prior digest validates, and the hole is invisible."""
    with pytest.raises(ValidationError, match="must name the digest it supersedes"):
        _envelope(revision=4, prior_digest=None)
    assert _envelope(revision=4, prior_digest=PRIOR).prior_digest == PRIOR


def test_a_first_revision_cannot_claim_a_predecessor() -> None:
    with pytest.raises(ValidationError, match="supersedes nothing"):
        _envelope(revision=1, prior_digest=PRIOR)


def test_a_revision_starts_at_one() -> None:
    for bad in (0, -1):
        with pytest.raises(ValidationError):
            _envelope(revision=bad)


# --- an approval is a human judgment ---------------------------------------------


@pytest.mark.parametrize(
    "provenance",
    [p for p in Provenance if p is not Provenance.HUMAN_JUDGMENT],
    ids=lambda p: p.value,
)
def test_an_approved_intent_cannot_claim_any_other_provenance(provenance: Provenance) -> None:
    """CAOM-001: every approval gate requires explicit operator action.

    A POLICY_RESULT approval is a gate approving itself, which is the authority
    model inverted. The envelope refuses to carry the claim.
    """
    with pytest.raises(ValidationError, match="explicit operator action"):
        _envelope(provenance=provenance)


# --- the payload is referenced, not copied ---------------------------------------


def test_the_envelope_carries_a_digest_and_not_the_terms() -> None:
    """The kernel cannot validate an asset class, so it must not hold one."""
    fields = set(ApprovedIntentEnvelope.model_fields)
    for domain_field in (
        "intent",
        "quantity",
        "asset_class",
        "side",
        "ownership",
        "execution_constraints",
        "policy_manifest",
    ):
        assert domain_field not in fields, (
            f"{domain_field} needs domain knowledge to validate and does not belong here"
        )
    assert "payload_digest" in fields


def test_a_changed_payload_gives_a_different_reference() -> None:
    """The only question the kernel can answer about a payload it cannot read."""
    sealed = _envelope(payload_digest=PAYLOAD)
    assert sealed.payload_digest != _envelope(payload_digest=PRIOR).payload_digest


def test_the_payload_reference_is_required_and_not_blank() -> None:
    with pytest.raises(ValidationError):
        _envelope(payload_digest="")


# --- R3: the session travels with the envelope ------------------------------------


def test_the_session_and_business_date_cross_the_boundary() -> None:
    """R3: neither is derived downstream from a timestamp, so both are carried."""
    envelope = _envelope()
    assert envelope.session.session is MarketSession.OVERNIGHT
    assert envelope.session.business_date.calendar == "Fedwire Funds"

    with pytest.raises(ValidationError):
        _envelope(session=None)


# --- it crosses a boundary ---------------------------------------------------------


def test_the_envelope_round_trips_and_has_a_stable_digest() -> None:
    envelope = _envelope()
    assert ApprovedIntentEnvelope.model_validate_json(envelope.model_dump_json()) == envelope
    assert digest(envelope) == digest(_envelope())
    assert digest(envelope) != digest(_envelope(revision=4, prior_digest=PRIOR))


def test_the_version_travels_with_the_instance() -> None:
    assert _envelope().schema_version == APPROVED_INTENT_VERSION
    assert APPROVED_INTENT_VERSION in _envelope().model_dump_json()


def test_an_unknown_field_is_refused() -> None:
    """A consumer adding a field on the wire is a contract change, not a message."""
    with pytest.raises(ValidationError):
        _envelope(urgency="HIGH")


# =================================================================================
# Contract 2 of 5: `ExecutionEvent` — the venue emulator to Legiones Cannenses
# =================================================================================
#
# A venue fact. CL-JUM-001 §2 records that execution events are today "fabricated
# in Aureon C2", with "delete fabrication (A4)" against them — a fabricated fill
# and a reported one were the same shape, so nothing downstream could tell them
# apart. These tests are mostly about making that impossible.


def _execution(**overrides: object) -> ExecutionEvent:
    fields: dict[str, object] = {
        "event_id": EventId("evt_01M2P20SY00000000000000001"),
        "lifecycle_id": LIFECYCLE,
        "intent_id": INTENT,
        "intent_digest": PAYLOAD,
        "times": EventTimes(
            event_time=T0,
            observation_time=T0,
            processing_time=T0,
        ),
        "session": _session(),
        "provenance": Provenance.FACT_SYNTHETIC,
        "payload_digest": PRIOR,
    }
    fields.update(overrides)
    return ExecutionEvent(**fields)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "provenance",
    [Provenance.FACT_EXTERNAL, Provenance.FACT_SYNTHETIC],
    ids=lambda p: p.value,
)
def test_an_execution_may_be_reported_or_emulated(provenance: Provenance) -> None:
    """Both cross this boundary. R1 decides separately what satisfies a gate."""
    assert _execution(provenance=provenance).provenance is provenance


@pytest.mark.parametrize(
    "provenance",
    [p for p in Provenance if p not in (Provenance.FACT_EXTERNAL, Provenance.FACT_SYNTHETIC)],
    ids=lambda p: p.value,
)
def test_an_execution_is_something_that_happened(provenance: Provenance) -> None:
    """A forecast of a fill is not a fill.

    Without this the model's expected execution and the venue's report are the
    same type, and the only thing keeping them apart is that nobody has yet made
    the mistake.
    """
    with pytest.raises(ValidationError, match="something that happened"):
        _execution(provenance=provenance)


def test_an_emulated_fill_is_distinguishable_from_a_reported_one() -> None:
    """The fabrication defect (A4), made structurally impossible.

    The two differ in the serialized bytes, so a consumer that never asks the
    question still cannot round-trip one as the other.
    """
    emulated = _execution(provenance=Provenance.FACT_SYNTHETIC)
    reported = _execution(provenance=Provenance.FACT_EXTERNAL)
    assert emulated != reported
    assert digest(emulated) != digest(reported)
    assert "FACT_SYNTHETIC" in emulated.model_dump_json()


def test_provenance_is_required_rather_than_defaulted() -> None:
    """A default would decide the question for whoever forgot to answer it."""
    assert ExecutionEvent.model_fields["provenance"].is_required()


def test_an_execution_names_both_the_intent_and_the_revision() -> None:
    """Different questions: which intent, and which version of it."""
    event = _execution()
    assert event.intent_id == INTENT
    assert event.intent_digest == PAYLOAD
    assert digest(event) != digest(_execution(intent_digest=PAYLOAD.replace("a", "c")))


def test_the_four_clocks_keep_their_ordering() -> None:
    """EventTimes already enforces it; this asserts the envelope does not bypass it."""
    with pytest.raises(ValidationError):
        _execution(
            times=EventTimes(
                event_time=T0,
                observation_time=T0 - timedelta(seconds=1),
                processing_time=T0,
            )
        )


def test_the_execution_event_round_trips() -> None:
    event = _execution()
    assert ExecutionEvent.model_validate_json(event.model_dump_json()) == event
    assert event.schema_version == EXECUTION_EVENT_VERSION
