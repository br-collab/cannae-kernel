"""Required test 9: ``verify_chain`` detects tampering, broken links, reordering and replays."""

from __future__ import annotations

from cannae_kernel.domains import Domain
from cannae_kernel.events import envelope_digest, verify
from cannae_kernel.ids import LifecycleId
from cannae_kernel.journal import ChainIssue, ChainIssueCode, verify_chain
from tests.factories import chain, envelope, halt_context, replace, ulid


def _codes(issues: tuple[ChainIssue, ...]) -> set[ChainIssueCode]:
    return {issue.code for issue in issues}


def test_sealed_chain_verifies() -> None:
    envs = chain(4)
    report = verify_chain(envs)
    assert report.ok
    assert report.issues == ()
    assert report.event_count == 4
    assert report.head_digest == envs[-1].envelope_digest
    assert all(verify(e) for e in envs)


def test_tampered_payload_is_detected() -> None:
    envs = chain(3)
    tampered = envs[1].model_copy(update={"payload": replace(halt_context(), active=False)})
    assert not verify(tampered)
    report = verify_chain([envs[0], tampered, envs[2]])
    assert not report.ok
    assert _codes(report.issues) == {
        ChainIssueCode.PAYLOAD_DIGEST_MISMATCH,
        ChainIssueCode.ENVELOPE_DIGEST_MISMATCH,
    }
    assert {i.index for i in report.issues} == {1}


def test_resealed_tampered_event_breaks_the_next_link() -> None:
    envs = chain(3)
    forged = envelope(
        1, prior=envs[0].envelope_digest, payload=replace(halt_context(), active=False)
    )
    report = verify_chain([envs[0], forged, envs[2]])
    assert [(i.index, i.code) for i in report.issues] == [(2, ChainIssueCode.BROKEN_PRIOR_LINK)]


def test_tampered_envelope_field_is_detected() -> None:
    envs = chain(2)
    tampered = envs[1].model_copy(update={"producer_domain": Domain.AUREON})
    report = verify_chain([envs[0], tampered])
    assert _codes(report.issues) == {ChainIssueCode.ENVELOPE_DIGEST_MISMATCH}


def test_broken_prior_link_is_detected_once() -> None:
    envs = chain(4)
    broken = envelope(2, prior=envs[0].envelope_digest)
    report = verify_chain([envs[0], envs[1], broken, envelope(3, prior=broken.envelope_digest)])
    assert [(i.index, i.code) for i in report.issues] == [(2, ChainIssueCode.BROKEN_PRIOR_LINK)]


def test_reordered_events_are_detected() -> None:
    envs = chain(3)
    report = verify_chain([envs[0], envs[2], envs[1]])
    codes = [(i.index, i.code) for i in report.issues]
    assert (1, ChainIssueCode.BROKEN_PRIOR_LINK) in codes
    assert (2, ChainIssueCode.BROKEN_PRIOR_LINK) in codes
    assert (2, ChainIssueCode.OUT_OF_ORDER) in codes


def test_duplicate_idempotency_key_is_detected() -> None:
    envs = chain(2)
    replay = envelope(2, prior=envs[1].envelope_digest, idempotency_key="halt-0")
    report = verify_chain([*envs, replay])
    assert [(i.index, i.code) for i in report.issues] == [
        (2, ChainIssueCode.DUPLICATE_IDEMPOTENCY_KEY)
    ]


def test_duplicate_event_id_is_detected() -> None:
    envs = chain(2)
    again = envs[1].model_copy(update={"prior_event_digest": envs[1].envelope_digest})
    again = again.model_copy(update={"envelope_digest": envelope_digest(again)})
    report = verify_chain([*envs, again])
    assert _codes(report.issues) == {
        ChainIssueCode.DUPLICATE_EVENT_ID,
        ChainIssueCode.DUPLICATE_IDEMPOTENCY_KEY,
    }


def test_second_lifecycle_is_detected_unless_declared() -> None:
    envs = chain(1)
    other = envelope(1, prior=envs[0].envelope_digest, lifecycle=LifecycleId("lc_" + ulid(7)))
    report = verify_chain([envs[0], other])
    assert _codes(report.issues) == {ChainIssueCode.LIFECYCLE_MISMATCH}
    assert verify_chain([envs[0], other], multi_lifecycle=True).ok


def test_empty_chain_does_not_pass() -> None:
    report = verify_chain([])
    assert not report.ok
    assert report.head_digest is None
    assert [(i.index, i.event_id, i.code) for i in report.issues] == [
        (-1, None, ChainIssueCode.EMPTY_CHAIN)
    ]


def test_segment_verifies_against_the_preceding_head() -> None:
    envs = chain(4)
    head = verify_chain(envs[:2]).head_digest
    assert verify_chain(envs[2:], expected_prior_digest=head).ok
    assert _codes(verify_chain(envs[2:]).issues) == {ChainIssueCode.BROKEN_PRIOR_LINK}


def test_first_event_must_not_claim_a_prior() -> None:
    envs = chain(2)
    report = verify_chain([envs[1]])
    assert _codes(report.issues) == {ChainIssueCode.BROKEN_PRIOR_LINK}
