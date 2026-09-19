"""Deterministic builders shared by the tests and by tools/regenerate_golden.py.

Nothing here reads the system clock or an entropy source: every identifier and time comes from
a fixed seed, so the golden vectors are reproducible byte for byte.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from datetime import date as dt_date
from decimal import Decimal
from typing import Any, TypeVar

from pydantic import BaseModel

from cannae_kernel.absence import AbsenceKind, Absent, Recorded
from cannae_kernel.actor import ActorKind, ActorRef
from cannae_kernel.authority import AuthorityRecord
from cannae_kernel.clocks import EventTimes
from cannae_kernel.domains import Domain
from cannae_kernel.effects import ExternalEffect, OperationEffects
from cannae_kernel.envelopes import ApprovedIntentEnvelope, ExecutionEvent
from cannae_kernel.events import EventEnvelope, seal
from cannae_kernel.finality import (
    ConditionalityStatus,
    FinalityAssertion,
    FinalityType,
    RevocabilityStatus,
)
from cannae_kernel.halt import HaltContext
from cannae_kernel.ids import (
    ActorId,
    CheckpointId,
    EventId,
    HaltId,
    IntentId,
    LifecycleId,
    encode_ulid,
)
from cannae_kernel.journal import (
    ChainIssue,
    ChainIssueCode,
    ChainReport,
    JournalCheckpoint,
    verify_chain,
)
from cannae_kernel.measurement import Constant, Measurement
from cannae_kernel.provenance import Provenance
from cannae_kernel.session import BusinessDate, MarketSession, SessionContext

T0 = datetime(2026, 9, 16, 21, 30, tzinfo=UTC)

M = TypeVar("M", bound=BaseModel)


def fixed_clock(at: datetime = T0) -> Callable[[], datetime]:
    return lambda: at


def seeded_entropy(seed: str) -> Callable[[int], bytes]:
    counter = 0

    def entropy(n: int) -> bytes:
        nonlocal counter
        counter += 1
        return hashlib.sha256(f"{seed}:{counter}".encode()).digest()[:n]

    return entropy


def ulid(n: int) -> str:
    """A canonical ULID for small integer ``n``: timestamp T0, randomness ``n``."""
    ms = (T0 - datetime(1970, 1, 1, tzinfo=UTC)) // timedelta(milliseconds=1)
    return encode_ulid(ms, n.to_bytes(10, "big"))


def replace(model: M, **changes: Any) -> M:
    """A validated copy of ``model`` with ``changes`` applied."""
    return type(model).model_validate({**model.model_dump(), **changes})


def human(n: int = 1, *, authenticated: bool = True) -> ActorRef:
    return ActorRef(
        actor_id=ActorId("act_" + ulid(n)),
        actor_kind=ActorKind.HUMAN,
        role="operator",
        entitlement_refs=("ent:approve-intent",),
        authenticated=authenticated,
    )


def service(n: int = 2) -> ActorRef:
    return ActorRef(
        actor_id=ActorId("act_" + ulid(n)),
        actor_kind=ActorKind.DETERMINISTIC_SERVICE,
        role="rail-emulator",
        entitlement_refs=(),
        authenticated=True,
    )


def times(offset_s: int = 0) -> EventTimes:
    base = T0 + timedelta(seconds=offset_s)
    return EventTimes(
        event_time=base,
        observation_time=base + timedelta(milliseconds=250),
        processing_time=base + timedelta(milliseconds=500),
        decision_time=None,
    )


def halt_context() -> HaltContext:
    return HaltContext(
        halt_id=HaltId("hlt_" + ulid(10)),
        version=1,
        active=True,
        scope=(Domain.LC, Domain.ATREIDES),
        declared_by=human(),
        declared_at=T0,
        reason="Tier 0 halt: rail emulator unavailable",
    )


def authority_record() -> AuthorityRecord:
    return AuthorityRecord(
        decision_type="APPROVE_INTENT",
        authorizing_actor=human(),
        timestamp=T0,
        rationale="Within mandate; policy manifest PASS",
        quorum_refs=(),
        independence_asserted=False,
    )


def finality_assertion() -> FinalityAssertion:
    return FinalityAssertion(
        finality_type=FinalityType.CASH_FINAL,
        governing_rule_set="synthetic-fedwire-funds/v0.1",
        authoritative_actor=service(),
        authoritative_event_id=EventId("evt_" + ulid(20)),
        effective_time=T0 + timedelta(minutes=5),
        observation_time=T0 + timedelta(minutes=4),
        evidence_reference="forecast:liquidity-model/run-7",
        conditionality_status=ConditionalityStatus.UNCONDITIONAL,
        revocability_status=RevocabilityStatus.IRREVOCABLE,
        provenance=Provenance.FORECAST,
        confidence=Decimal("0.85"),
    )


LIFECYCLE = LifecycleId("lif_" + ulid(100))


def envelope(
    n: int,
    *,
    prior: str | None,
    lifecycle: LifecycleId = LIFECYCLE,
    idempotency_key: str | None = None,
    payload: BaseModel | None = None,
) -> EventEnvelope[Any]:
    """The ``n``-th event of a chain: processing times increase with ``n``."""
    return seal(
        event_id=EventId("evt_" + ulid(1000 + n)),
        lifecycle_id=lifecycle,
        parent_ids=() if n == 0 else (EventId("evt_" + ulid(1000 + n - 1)),),
        producer_domain=Domain.C2,
        event_type="HaltDeclared",
        schema_version="0.1.0",
        rule_version="halt-rules/v1",
        times=times(offset_s=n),
        provenance=Provenance.HUMAN_JUDGMENT,
        actor=human(),
        idempotency_key=idempotency_key or f"halt-{n}",
        payload=payload if payload is not None else halt_context(),
        prior_event_digest=prior,
    )


def chain(length: int) -> list[EventEnvelope[Any]]:
    out: list[EventEnvelope[Any]] = []
    prior: str | None = None
    for n in range(length):
        env = envelope(n, prior=prior)
        out.append(env)
        prior = env.envelope_digest
    return out


def chain_issue() -> ChainIssue:
    return ChainIssue(
        index=1,
        event_id=EventId("evt_" + ulid(1001)),
        code=ChainIssueCode.BROKEN_PRIOR_LINK,
        detail="prior_event_digest does not match",
    )


def chain_report() -> ChainReport:
    return verify_chain(chain(2))


def checkpoint_of(envelopes: list[EventEnvelope[Any]]) -> JournalCheckpoint:
    """What the C2 harness would record for ``envelopes`` as they stand now."""
    head = envelopes[-1]
    return JournalCheckpoint(
        checkpoint_id=CheckpointId("ckp_" + ulid(2000 + len(envelopes))),
        lifecycle_id=head.lifecycle_id,
        domain=Domain.C2,
        head_event_id=head.event_id,
        head_digest=head.envelope_digest,
        event_count=len(envelopes),
        taken_at=head.times.processing_time,
        recorded_by=service(),
    )


def absent() -> Absent:
    """The quorum hold: nothing was written, because no instruction was issued."""
    return Absent(kind=AbsenceKind.NOTHING_RECORDED, reason="no instruction was issued")


def recorded() -> Recorded[str]:
    """The other side of the same union: a value that was recorded."""
    return Recorded[str](value="dsor_01M2P20SY00000000000000001")


def measurement() -> Measurement:
    """An external reading, with the publisher and the time it was seen."""
    return Measurement(
        value=Decimal("0.3800"),
        provenance=Provenance.FACT_EXTERNAL,
        source="OFR Financial Stress Index",
        observed_at=T0,
    )


def constant() -> Constant:
    """A fallback default: no observation, and the reason there was none."""
    return Constant(
        value=Decimal("0.3800"),
        source="fallback_macro_snapshot",
        reason="the publisher was unreachable",
    )


def business_date() -> BusinessDate:
    """Monday 7 December 2026 on the Fedwire Funds calendar, fixed by the rail."""
    return BusinessDate(
        value=dt_date(2026, 12, 7),
        calendar="Fedwire Funds",
        established_by="the rail's published calendar",
    )


def session_context() -> SessionContext:
    """The Overnight session: 20% bands, and a business date nothing derived."""
    return SessionContext(session=MarketSession.OVERNIGHT, business_date=business_date())


def operation_effects() -> OperationEffects:
    """aureon #34: sends real email, changes no application state."""
    return OperationEffects(
        operation="POST /api/email/test",
        effects=(ExternalEffect.SENDS,),
        note="sends real email from the operator's account; nothing in-process changes",
    )


def approved_intent_envelope() -> ApprovedIntentEnvelope:
    """Contract 1 of 5. The skeleton only; the terms are referenced by digest."""
    return ApprovedIntentEnvelope(
        envelope_id=IntentId("int_01M2P20SY00000000000000001"),
        lifecycle_id=LifecycleId("lif_01M2P20SY00000000000000001"),
        revision=1,
        prior_digest=None,
        session=session_context(),
        approved_by=human(),
        provenance=Provenance.HUMAN_JUDGMENT,
        effects=OperationEffects(
            operation="release approved intent to L.C.",
            effects=(ExternalEffect.PUBLISHES,),
            note="hands the approved intent to the middle layer; it leaves this process",
        ),
        payload_digest="sha256:" + "a" * 64,
    )


def execution_event() -> ExecutionEvent:
    """Contract 2 of 5. An emulated fill, labelled as one."""
    return ExecutionEvent(
        event_id=EventId("evt_" + ulid(7)),
        lifecycle_id=LifecycleId("lif_01M2P20SY00000000000000001"),
        intent_id=IntentId("int_01M2P20SY00000000000000001"),
        intent_digest="sha256:" + "a" * 64,
        times=times(),
        session=session_context(),
        provenance=Provenance.FACT_SYNTHETIC,
        payload_digest="sha256:" + "b" * 64,
    )


def golden_instances() -> dict[str, BaseModel]:
    """One instance of every kernel model. Their canonical bytes are the golden vectors."""
    return {
        "absent": absent(),
        "actor_ref": human(),
        "approved_intent_envelope": approved_intent_envelope(),
        "business_date": business_date(),
        "authority_record": authority_record(),
        "chain_issue": chain_issue(),
        "chain_report": chain_report(),
        "event_envelope": envelope(0, prior=None),
        "execution_event": execution_event(),
        "event_times": replace(times(), decision_time=T0 + timedelta(seconds=1)),
        "finality_assertion": finality_assertion(),
        "halt_context": halt_context(),
        "journal_checkpoint": checkpoint_of(chain(2)),
        "measurement": measurement(),
        "measurement_constant": constant(),
        "observed_fact": measurement().observed(),
        "operation_effects": operation_effects(),
        "recorded": recorded(),
        "session_context": session_context(),
    }
