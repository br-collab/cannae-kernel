"""Verify a domain journal's hash chain (JUM-D-12; Research Charter §19.9 invariants 9-10).

``verify_chain`` is a pure function over envelopes already in memory. It reads nothing and
stores nothing. It reports every problem it finds rather than stopping at the first, so the
Cannae C2 view can show exactly where a journal went wrong.

A hash chain alone cannot reveal a rewritten *tail*: whoever rewrites the last event can
reseal it. A ``JournalCheckpoint`` records a journal's head outside that journal. The Cannae C2
harness records other domains' checkpoints in its own chain (JUM-D-25), and ``verify_chain``
checks a journal against one with ``expected_head``.

Journal order is defined by the prior-digest links, not by identifier order. Identifiers
minted in the same millisecond may sort either way, and that is acceptable.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from typing import Any

from cannae_kernel._model import (
    KernelModel,
    NonEmptyStr,
    NonNegativeSafeInt,
    PositiveSafeInt,
    SafeInt,
    UtcDatetime,
)
from cannae_kernel.actor import ActorRef
from cannae_kernel.canonical import Digest, digest
from cannae_kernel.domains import Domain
from cannae_kernel.events import EventEnvelope, envelope_digest
from cannae_kernel.ids import CheckpointId, EventId, LifecycleId

__all__ = ["ChainIssue", "ChainIssueCode", "ChainReport", "JournalCheckpoint", "verify_chain"]


class ChainIssueCode(StrEnum):
    EMPTY_CHAIN = "EMPTY_CHAIN"
    """Nothing to verify. An empty chain is not evidence of anything, so it does not pass."""
    PAYLOAD_DIGEST_MISMATCH = "PAYLOAD_DIGEST_MISMATCH"
    ENVELOPE_DIGEST_MISMATCH = "ENVELOPE_DIGEST_MISMATCH"
    BROKEN_PRIOR_LINK = "BROKEN_PRIOR_LINK"
    """``prior_event_digest`` is not the previous envelope's ``envelope_digest``."""
    OUT_OF_ORDER = "OUT_OF_ORDER"
    """``times.processing_time`` goes backwards. A journal is appended in processing order."""
    DUPLICATE_IDEMPOTENCY_KEY = "DUPLICATE_IDEMPOTENCY_KEY"
    DUPLICATE_EVENT_ID = "DUPLICATE_EVENT_ID"
    LIFECYCLE_MISMATCH = "LIFECYCLE_MISMATCH"
    """A second ``lifecycle_id`` in a chain not declared multi-lifecycle."""
    HEAD_MISMATCH = "HEAD_MISMATCH"
    """The chain's head digest, head event or event count differs from ``expected_head``."""


class JournalCheckpoint(KernelModel):
    """A domain journal's head, recorded outside that journal (JUM-D-25)."""

    checkpoint_id: CheckpointId
    lifecycle_id: LifecycleId
    domain: Domain
    """The domain whose journal this checkpoint describes."""
    head_event_id: EventId
    head_digest: Digest
    """The ``envelope_digest`` of the head event."""
    event_count: PositiveSafeInt
    """Events in the journal up to and including the head."""
    taken_at: UtcDatetime
    recorded_by: ActorRef


class ChainIssue(KernelModel):
    index: SafeInt
    """Position in the sequence passed to ``verify_chain``; ``-1`` for chain-level issues."""
    event_id: EventId | None
    code: ChainIssueCode
    detail: NonEmptyStr


class ChainReport(KernelModel):
    ok: bool
    event_count: NonNegativeSafeInt
    head_digest: Digest | None
    """The last envelope's recorded ``envelope_digest``: where the next append must link."""
    issues: tuple[ChainIssue, ...]


def _head_mismatch(envelopes: Sequence[EventEnvelope[Any]], expected: JournalCheckpoint) -> str:
    """Describe how the chain's head differs from ``expected``; empty when it matches."""
    head = envelopes[-1] if envelopes else None
    mismatches = []
    if len(envelopes) != expected.event_count:
        mismatches.append(f"event_count {len(envelopes)} != {expected.event_count}")
    if head is None or head.envelope_digest != expected.head_digest:
        mismatches.append("head digest differs from the checkpoint")
    if head is None or head.event_id != expected.head_event_id:
        mismatches.append("head event differs from the checkpoint")
    return "; ".join(mismatches)


def verify_chain(
    envelopes: Sequence[EventEnvelope[Any]],
    *,
    expected_prior_digest: str | None = None,
    multi_lifecycle: bool = False,
    expected_head: JournalCheckpoint | None = None,
) -> ChainReport:
    """Check a journal, or a segment of one, and report every problem found.

    ``expected_prior_digest`` is what the first envelope must link to: ``None`` for the start
    of a journal, or the head digest of the segment that precedes this one.

    ``expected_head`` compares the last envelope passed, and the number of envelopes passed,
    with a checkpoint. To check a journal that has grown since the checkpoint was taken, pass
    the journal up to the checkpoint: ``envelopes[: checkpoint.event_count]``.
    """
    issues: list[ChainIssue] = []

    def add(index: int, env: EventEnvelope[Any] | None, code: ChainIssueCode, detail: str) -> None:
        issues.append(
            ChainIssue(
                index=index,
                event_id=env.event_id if env is not None else None,
                code=code,
                detail=detail,
            )
        )

    if not envelopes:
        add(-1, None, ChainIssueCode.EMPTY_CHAIN, "no envelopes to verify")

    seen_keys: dict[str, int] = {}
    seen_ids: dict[str, int] = {}
    expected_link = expected_prior_digest
    first_lifecycle = envelopes[0].lifecycle_id if envelopes else None

    for i, env in enumerate(envelopes):
        if env.payload_digest != digest(env.payload):
            add(i, env, ChainIssueCode.PAYLOAD_DIGEST_MISMATCH, "payload does not match digest")
        if env.envelope_digest != envelope_digest(env):
            add(i, env, ChainIssueCode.ENVELOPE_DIGEST_MISMATCH, "envelope does not match digest")
        if env.prior_event_digest != expected_link:
            add(
                i,
                env,
                ChainIssueCode.BROKEN_PRIOR_LINK,
                f"prior_event_digest is {env.prior_event_digest}; expected {expected_link}",
            )
        if i > 0 and env.times.processing_time < envelopes[i - 1].times.processing_time:
            add(i, env, ChainIssueCode.OUT_OF_ORDER, "processing_time precedes the prior event's")
        if env.idempotency_key in seen_keys:
            add(
                i,
                env,
                ChainIssueCode.DUPLICATE_IDEMPOTENCY_KEY,
                f"idempotency_key already used at index {seen_keys[env.idempotency_key]}",
            )
        else:
            seen_keys[env.idempotency_key] = i
        if env.event_id in seen_ids:
            add(
                i,
                env,
                ChainIssueCode.DUPLICATE_EVENT_ID,
                f"event_id already used at index {seen_ids[env.event_id]}",
            )
        else:
            seen_ids[env.event_id] = i
        if not multi_lifecycle and env.lifecycle_id != first_lifecycle:
            add(
                i,
                env,
                ChainIssueCode.LIFECYCLE_MISMATCH,
                f"lifecycle_id {env.lifecycle_id} differs from {first_lifecycle}",
            )
        # Link to what this envelope claims, so one broken link is reported once, not
        # cascaded through every later event.
        expected_link = env.envelope_digest

    head_mismatch = _head_mismatch(envelopes, expected_head) if expected_head else ""
    if head_mismatch:
        add(-1, envelopes[-1] if envelopes else None, ChainIssueCode.HEAD_MISMATCH, head_mismatch)

    return ChainReport(
        ok=not issues,
        event_count=len(envelopes),
        head_digest=envelopes[-1].envelope_digest if envelopes else None,
        issues=tuple(issues),
    )
