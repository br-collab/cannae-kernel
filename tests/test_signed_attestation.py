import json
from collections.abc import Mapping

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from cannae_kernel.signed_attestation import (
    AttestationRefusal,
    AttestationVerificationError,
    PublicKeyRecord,
    PublicKeyRegistry,
    pinned_public_key_registry,
    sign_attestation,
    verify_attestation,
)


@pytest.fixture
def synthetic_private_key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(bytes(range(32)))


def registry_for(key: Ed25519PrivateKey, producer: str = "atreides") -> PublicKeyRegistry:
    return pinned_public_key_registry(
        {"synthetic-key-1": PublicKeyRecord(producer, key.public_key())}
    )


def test_round_trip(synthetic_private_key: Ed25519PrivateKey) -> None:
    wire = sign_attestation(
        b'{"synthetic":true}',
        producer="atreides",
        key_id="synthetic-key-1",
        private_key=synthetic_private_key,
    )

    assert (
        verify_attestation(
            wire, expected_producer="atreides", registry=registry_for(synthetic_private_key)
        )
        == b'{"synthetic":true}'
    )


@pytest.mark.parametrize(
    ("registry", "expected_producer", "expected_refusal"),
    [
        ({}, "atreides", AttestationRefusal.UNKNOWN_KEY),
        (None, "lc", AttestationRefusal.WRONG_PRODUCER),
    ],
)
def test_identity_refusals(
    synthetic_private_key: Ed25519PrivateKey,
    registry: Mapping[str, PublicKeyRecord] | None,
    expected_producer: str,
    expected_refusal: AttestationRefusal,
) -> None:
    wire = sign_attestation(
        b"synthetic payload",
        producer="atreides",
        key_id="synthetic-key-1",
        private_key=synthetic_private_key,
    )
    pinned = (
        pinned_public_key_registry(registry)
        if registry is not None
        else registry_for(synthetic_private_key)
    )

    with pytest.raises(AttestationVerificationError) as exc_info:
        verify_attestation(wire, expected_producer=expected_producer, registry=pinned)
    assert exc_info.value.refusal is expected_refusal


def test_payload_tamper_is_refused(synthetic_private_key: Ed25519PrivateKey) -> None:
    wire = sign_attestation(
        b"synthetic payload",
        producer="atreides",
        key_id="synthetic-key-1",
        private_key=synthetic_private_key,
    )
    envelope = json.loads(wire)
    envelope["payload_b64"] = "dGFtcGVyZWQ="

    with pytest.raises(AttestationVerificationError) as exc_info:
        verify_attestation(
            json.dumps(envelope).encode(),
            expected_producer="atreides",
            registry=registry_for(synthetic_private_key),
        )
    assert exc_info.value.refusal is AttestationRefusal.INVALID_SIGNATURE
