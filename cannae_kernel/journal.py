"""Verify a domain journal's hash chain (JUM-D-12; Research Charter §19.9 invariants 9-10).

``verify_chain`` is a pure function over envelopes already in memory. It reads nothing and
stores nothing. It reports every problem it finds rather than stopping at the first, so the
Cannae C2 view can show exactly where a journal went wrong.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from typing import Any

from cannae_kernel._model import KernelModel, NonEmptyStr
from cannae_kernel.canonical import Digest, digest
from cannae_kernel.events import EventEnvelope, envelope_digest
from cannae_kernel.ids import EventId

__all__ = ["ChainIssue", "ChainIssueCode", "ChainReport", "verify_chain"]


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


class ChainIssue(KernelModel):
    index: int
    """Position in the sequence passed to ``verify_chain``; ``-1`` for chain-level issues."""
    event_id: EventId | None
    code: ChainIssueCode
    detail: NonEmptyStr


class ChainReport(KernelModel):
    ok: bool
    event_count: int
    head_digest: Digest | None
    """The last envelope's recorded ``envelope_digest``: where the next append must link."""
    issues: tuple[ChainIssue, ...]


def verify_chain(
    envelopes: Sequence[EventEnvelope[Any]],
    *,
    expected_prior_digest: str | None = None,
    multi_lifecycle: bool = False,
) -> ChainReport:
    """Check a journal, or a segment of one, and report every problem found.

    ``expected_prior_digest`` is what the first envelope must link to: ``None`` for the start
    of a journal, or the head digest of the segment that precedes this one.
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

    return ChainReport(
        ok=not issues,
        event_count=len(envelopes),
        head_digest=envelopes[-1].envelope_digest if envelopes else None,
        issues=tuple(issues),
    )
