"""The event envelope every domain journal appends (CL-JUM-001 §6; JUM-D-12).

Each domain keeps its own append-only journal. Every entry is an ``EventEnvelope`` whose
``prior_event_digest`` is the ``envelope_digest`` of the entry before it, so a journal is a
hash chain that anyone can verify without trusting the domain that wrote it.

Digests:

- ``payload_digest`` is ``digest(payload)``.
- ``envelope_digest`` is the digest of the canonical bytes of every envelope field except
  ``envelope_digest`` itself. It therefore covers the payload digest and the prior link.

Construction does not check the digests, so a tampered envelope can still be loaded and
reported on. Use ``seal`` to build an envelope and ``verify`` (or
``journal.verify_chain``) to check one.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar, cast

from pydantic import BaseModel

from cannae_kernel._model import KernelModel, NonEmptyStr
from cannae_kernel.actor import ActorRef
from cannae_kernel.canonical import Digest, canonical_bytes_of, digest, digest_bytes
from cannae_kernel.clocks import EventTimes
from cannae_kernel.domains import Domain
from cannae_kernel.ids import EventId, LifecycleId
from cannae_kernel.provenance import Provenance

__all__ = ["EventEnvelope", "envelope_digest", "seal", "verify"]

PayloadT = TypeVar("PayloadT", bound=BaseModel)


class EventEnvelope(KernelModel, Generic[PayloadT]):
    event_id: EventId
    lifecycle_id: LifecycleId
    parent_ids: tuple[EventId, ...]
    """The events this one was caused by or derived from. Empty for a root event."""
    producer_domain: Domain
    event_type: NonEmptyStr
    schema_version: NonEmptyStr
    rule_version: NonEmptyStr
    times: EventTimes
    provenance: Provenance
    actor: ActorRef
    idempotency_key: NonEmptyStr
    payload: PayloadT
    payload_digest: Digest
    prior_event_digest: Digest | None
    """``None`` only for the first event of a journal."""
    envelope_digest: Digest


def envelope_digest(envelope: EventEnvelope[Any]) -> str:
    """Recompute the digest over every field of ``envelope`` except ``envelope_digest``."""
    return digest_bytes(
        canonical_bytes_of(envelope.model_dump(mode="python", exclude={"envelope_digest"}))
    )


def seal(
    *,
    event_id: EventId,
    lifecycle_id: LifecycleId,
    parent_ids: tuple[EventId, ...],
    producer_domain: Domain,
    event_type: str,
    schema_version: str,
    rule_version: str,
    times: EventTimes,
    provenance: Provenance,
    actor: ActorRef,
    idempotency_key: str,
    payload: PayloadT,
    prior_event_digest: str | None,
) -> EventEnvelope[PayloadT]:
    """Build an envelope with both digests computed."""
    # Parametrize by the runtime payload type so the payload serializes with its own fields.
    model = cast(Any, EventEnvelope)[type(payload)]
    fields: dict[str, Any] = {
        "event_id": event_id,
        "lifecycle_id": lifecycle_id,
        "parent_ids": parent_ids,
        "producer_domain": producer_domain,
        "event_type": event_type,
        "schema_version": schema_version,
        "rule_version": rule_version,
        "times": times,
        "provenance": provenance,
        "actor": actor,
        "idempotency_key": idempotency_key,
        "payload": payload,
        "payload_digest": digest(payload),
        "prior_event_digest": prior_event_digest,
    }
    unsealed = model(**fields, envelope_digest="sha256:" + "0" * 64)
    return cast(
        "EventEnvelope[PayloadT]",
        model(**fields, envelope_digest=envelope_digest(unsealed)),
    )


def verify(envelope: EventEnvelope[Any]) -> bool:
    """True when both digests match the envelope's current contents."""
    return envelope.payload_digest == digest(envelope.payload) and (
        envelope.envelope_digest == envelope_digest(envelope)
    )
