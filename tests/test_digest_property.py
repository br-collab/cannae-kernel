"""Required test 2 (property part): changing any single field changes the digest.

For every model, Hypothesis builds varied valid instances, and every field has a mutation
that yields a different valid value. The digest must change for every one. A field missing
from the canonical form, or two distinct values collapsing to one form, fails here.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import BaseModel

from cannae_kernel.actor import ActorKind, ActorRef
from cannae_kernel.authority import AuthorityRecord
from cannae_kernel.canonical import digest
from cannae_kernel.clocks import EventTimes
from cannae_kernel.domains import Domain
from cannae_kernel.events import EventEnvelope, envelope_digest, seal
from cannae_kernel.finality import (
    ConditionalityStatus,
    FinalityAssertion,
    FinalityType,
    RevocabilityStatus,
)
from cannae_kernel.halt import HaltContext
from cannae_kernel.ids import ActorId, EventId, HaltId, LifecycleId, encode_ulid
from cannae_kernel.journal import ChainIssue, ChainIssueCode, ChainReport
from cannae_kernel.provenance import Provenance
from tests.factories import replace

# codec="utf-8" already excludes lone surrogates, which have no UTF-8 encoding.
text = st.text(st.characters(codec="utf-8"), min_size=1, max_size=12)
instants = st.datetimes(
    min_value=datetime(2000, 1, 1), max_value=datetime(2100, 1, 1), timezones=st.just(UTC)
)
ulids = st.builds(
    encode_ulid,
    st.integers(0, (1 << 48) - 1),
    st.binary(min_size=10, max_size=10),
)


def _typed(cls: type[str]) -> st.SearchStrategy[Any]:
    return ulids.map(lambda u: cls(cls.prefix + u))  # type: ignore[attr-defined]


def _other_id(value: str) -> str:
    """A different id of the same type: flip the last ULID character."""
    last = "1" if value[-1] != "1" else "2"
    return type(value)(value[:-1] + last)


def _other_enum(value: Any) -> Any:
    members: list[Any] = list(type(value).__members__.values())
    return members[(members.index(value) + 1) % len(members)]


actors = st.builds(
    ActorRef,
    actor_id=_typed(ActorId),
    actor_kind=st.sampled_from(ActorKind),
    role=text,
    entitlement_refs=st.lists(text, max_size=3).map(tuple),
    authenticated=st.booleans(),
)
authorizers = actors.map(lambda a: replace(a, actor_kind=ActorKind.HUMAN, authenticated=True))


@st.composite
def event_times(draw: st.DrawFn) -> EventTimes:
    start = draw(instants)
    gaps = [timedelta(seconds=draw(st.integers(1, 3600))) for _ in range(3)]
    decision = draw(st.booleans())
    return EventTimes(
        event_time=start,
        observation_time=start + gaps[0],
        processing_time=start + gaps[0] + gaps[1],
        decision_time=start + sum(gaps, timedelta()) if decision else None,
    )


authorities = st.builds(
    AuthorityRecord,
    decision_type=text,
    authorizing_actor=authorizers,
    timestamp=instants,
    rationale=text,
    quorum_refs=st.lists(text, max_size=3).map(tuple),
    independence_asserted=st.booleans(),
)

halts = st.builds(
    HaltContext,
    halt_id=_typed(HaltId),
    version=st.integers(1, 1000),
    active=st.booleans(),
    scope=st.one_of(
        st.just("ALL"),
        st.lists(st.sampled_from(Domain), min_size=1, max_size=5, unique=True).map(tuple),
    ),
    declared_by=actors,
    declared_at=instants,
    reason=text,
)

finalities = st.builds(
    FinalityAssertion,
    finality_type=st.sampled_from(FinalityType),
    governing_rule_set=text,
    authoritative_actor=actors,
    authoritative_event_id=_typed(EventId),
    effective_time=instants,
    observation_time=instants,
    evidence_reference=text,
    conditionality_status=st.sampled_from(ConditionalityStatus),
    revocability_status=st.sampled_from(RevocabilityStatus),
    provenance=st.just(Provenance.FORECAST),
    confidence=st.decimals(min_value=0, max_value=Decimal("0.99"), places=2),
)

issues = st.builds(
    ChainIssue,
    index=st.integers(-1, 10_000),
    event_id=st.one_of(st.none(), _typed(EventId)),
    code=st.sampled_from(ChainIssueCode),
    detail=text,
)

reports = st.builds(
    ChainReport,
    ok=st.booleans(),
    event_count=st.integers(0, 10_000),
    head_digest=st.one_of(
        st.none(), st.binary(min_size=32, max_size=32).map(lambda b: "sha256:" + b.hex())
    ),
    issues=st.lists(issues, max_size=3).map(tuple),
)


@st.composite
def envelopes(draw: st.DrawFn) -> Any:
    return seal(
        event_id=draw(_typed(EventId)),
        lifecycle_id=draw(_typed(LifecycleId)),
        parent_ids=tuple(draw(st.lists(_typed(EventId), max_size=2))),
        producer_domain=draw(st.sampled_from(Domain)),
        event_type=draw(text),
        schema_version=draw(text),
        rule_version=draw(text),
        times=draw(event_times()),
        provenance=draw(st.sampled_from(Provenance)),
        actor=draw(actors),
        idempotency_key=draw(text),
        payload=draw(halts),
        prior_event_digest=draw(
            st.one_of(
                st.none(),
                st.binary(min_size=32, max_size=32).map(lambda b: "sha256:" + b.hex()),
            )
        ),
    )


def _flip_digest(value: str | None) -> str:
    if value is None:
        return "sha256:" + "0" * 64
    return value[:-1] + ("0" if value[-1] != "0" else "1")


Mutation = Callable[[Any], Any]
MICRO = timedelta(microseconds=1)

MUTATIONS: dict[str, tuple[st.SearchStrategy[Any], dict[str, Mutation]]] = {
    "ActorRef": (
        actors,
        {
            "actor_id": lambda m: _other_id(m.actor_id),
            "actor_kind": lambda m: _other_enum(m.actor_kind),
            "role": lambda m: m.role + "x",
            "entitlement_refs": lambda m: (*m.entitlement_refs, "x"),
            "authenticated": lambda m: not m.authenticated,
        },
    ),
    "EventTimes": (
        event_times(),
        {
            "event_time": lambda m: m.event_time - MICRO,
            "observation_time": lambda m: m.observation_time + MICRO,
            "processing_time": lambda m: m.processing_time + MICRO,
            "decision_time": lambda m: (
                m.processing_time if m.decision_time is None else m.decision_time + MICRO
            ),
        },
    ),
    "AuthorityRecord": (
        authorities,
        {
            "decision_type": lambda m: m.decision_type + "x",
            "authorizing_actor": lambda m: replace(
                m.authorizing_actor, role=m.authorizing_actor.role + "x"
            ),
            "timestamp": lambda m: m.timestamp + MICRO,
            "rationale": lambda m: m.rationale + "x",
            "quorum_refs": lambda m: (*m.quorum_refs, "x"),
            "independence_asserted": lambda m: not m.independence_asserted,
        },
    ),
    "HaltContext": (
        halts,
        {
            "halt_id": lambda m: _other_id(m.halt_id),
            "version": lambda m: m.version + 1,
            "active": lambda m: not m.active,
            "scope": lambda m: (Domain.C2,) if m.scope != (Domain.C2,) else "ALL",
            "declared_by": lambda m: replace(m.declared_by, role=m.declared_by.role + "x"),
            "declared_at": lambda m: m.declared_at + MICRO,
            "reason": lambda m: m.reason + "x",
        },
    ),
    "FinalityAssertion": (
        finalities,
        {
            "finality_type": lambda m: _other_enum(m.finality_type),
            "governing_rule_set": lambda m: m.governing_rule_set + "x",
            "authoritative_actor": lambda m: replace(
                m.authoritative_actor, role=m.authoritative_actor.role + "x"
            ),
            "authoritative_event_id": lambda m: _other_id(m.authoritative_event_id),
            "effective_time": lambda m: m.effective_time + MICRO,
            "observation_time": lambda m: m.observation_time + MICRO,
            "evidence_reference": lambda m: m.evidence_reference + "x",
            "conditionality_status": lambda m: _other_enum(m.conditionality_status),
            "revocability_status": lambda m: _other_enum(m.revocability_status),
            "provenance": lambda m: Provenance.RECOMMENDATION,
            # Same number at a different scale is a different canonical form, by design.
            "confidence": lambda m: m.confidence + Decimal("0.01"),
        },
    ),
    "ChainIssue": (
        issues,
        {
            "index": lambda m: m.index + 1,
            "event_id": lambda m: None if m.event_id is not None else EventId("evt_" + "0" * 26),
            "code": lambda m: _other_enum(m.code),
            "detail": lambda m: m.detail + "x",
        },
    ),
    "ChainReport": (
        reports,
        {
            "ok": lambda m: not m.ok,
            "event_count": lambda m: m.event_count + 1,
            "head_digest": lambda m: _flip_digest(m.head_digest),
            "issues": lambda m: (
                *m.issues,
                ChainIssue(index=0, event_id=None, code=ChainIssueCode.EMPTY_CHAIN, detail="x"),
            ),
        },
    ),
    "EventEnvelope": (
        envelopes(),
        {
            "event_id": lambda m: _other_id(m.event_id),
            "lifecycle_id": lambda m: _other_id(m.lifecycle_id),
            "parent_ids": lambda m: (*m.parent_ids, EventId("evt_" + "0" * 26)),
            "producer_domain": lambda m: _other_enum(m.producer_domain),
            "event_type": lambda m: m.event_type + "x",
            "schema_version": lambda m: m.schema_version + "x",
            "rule_version": lambda m: m.rule_version + "x",
            "times": lambda m: replace(m.times, event_time=m.times.event_time - MICRO),
            "provenance": lambda m: _other_enum(m.provenance),
            "actor": lambda m: replace(m.actor, role=m.actor.role + "x"),
            "idempotency_key": lambda m: m.idempotency_key + "x",
            "payload": lambda m: replace(m.payload, active=not m.payload.active),
            "payload_digest": lambda m: _flip_digest(m.payload_digest),
            "prior_event_digest": lambda m: _flip_digest(m.prior_event_digest),
            "envelope_digest": lambda m: _flip_digest(m.envelope_digest),
        },
    ),
}

CASES = [(model, field) for model, (_, fields) in MUTATIONS.items() for field in fields]


def test_every_field_of_every_model_has_a_mutation() -> None:
    fields_by_model: dict[str, set[str]] = {}
    for model_name, (_, mutations) in MUTATIONS.items():
        fields_by_model[model_name] = set(mutations)
    declared: dict[str, type[BaseModel]] = {
        "ActorRef": ActorRef,
        "EventTimes": EventTimes,
        "AuthorityRecord": AuthorityRecord,
        "HaltContext": HaltContext,
        "FinalityAssertion": FinalityAssertion,
        "ChainIssue": ChainIssue,
        "ChainReport": ChainReport,
        "EventEnvelope": EventEnvelope,
    }
    assert set(fields_by_model) == set(declared)
    for name, fields in fields_by_model.items():
        assert fields == set(declared[name].model_fields), name


@pytest.mark.parametrize(("model_name", "field"), CASES)
@given(data=st.data())
def test_changing_one_field_changes_the_digest(
    model_name: str, field: str, data: st.DataObject
) -> None:
    strategy, mutations = MUTATIONS[model_name]
    model = data.draw(strategy)
    changed = model.model_copy(update={field: mutations[field](model)})
    # The copy is revalidated so every mutation is a value the model really accepts.
    changed = type(model).model_validate(changed.model_dump())
    assert getattr(changed, field) != getattr(model, field)
    assert digest(changed) != digest(model)
    if model_name == "EventEnvelope" and field != "envelope_digest":
        assert envelope_digest(changed) != envelope_digest(model)
