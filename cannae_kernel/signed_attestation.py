"""Producer-bound Ed25519 attestations for cross-domain evidence."""

from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Literal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from cannae_kernel._model import KernelModel, NonEmptyStr


class SignedAttestation(KernelModel):
    """Wire envelope whose signature covers producer, key identifier and payload."""

    schema_version: Literal["cannae.signed_attestation/1"] = "cannae.signed_attestation/1"
    producer: NonEmptyStr
    key_id: NonEmptyStr
    payload_b64: NonEmptyStr
    signature_b64: NonEmptyStr


@dataclass(frozen=True)
class PublicKeyRecord:
    """A public key pinned to the producer authorized to use it."""

    producer: str
    public_key: Ed25519PublicKey


PublicKeyRegistry = Mapping[str, PublicKeyRecord]


class AttestationRefusal(StrEnum):
    UNKNOWN_KEY = "ATTESTATION_SIGNING_KEY_UNKNOWN"
    WRONG_PRODUCER = "ATTESTATION_PRODUCER_MISMATCH"
    INVALID_SIGNATURE = "ATTESTATION_SIGNATURE_INVALID"
    MALFORMED = "ATTESTATION_MALFORMED"


class AttestationVerificationError(ValueError):
    """Named verification refusal safe for mapping into domain refusal enums."""

    def __init__(self, refusal: AttestationRefusal) -> None:
        self.refusal = refusal
        super().__init__(refusal.value)


def pinned_public_key_registry(
    records: Mapping[str, PublicKeyRecord],
) -> PublicKeyRegistry:
    """Return an immutable snapshot so callers cannot replace keys after injection."""

    return MappingProxyType(dict(records))


def _signed_bytes(*, producer: str, key_id: str, payload: bytes) -> bytes:
    body = {
        "key_id": key_id,
        "payload_b64": base64.b64encode(payload).decode("ascii"),
        "producer": producer,
        "schema_version": "cannae.signed_attestation/1",
    }
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_attestation(
    payload: bytes,
    *,
    producer: str,
    key_id: str,
    private_key: Ed25519PrivateKey,
) -> bytes:
    """Sign a payload with an Ed25519 private key and return the wire envelope."""

    signed_bytes = _signed_bytes(producer=producer, key_id=key_id, payload=payload)
    envelope = SignedAttestation(
        producer=producer,
        key_id=key_id,
        payload_b64=base64.b64encode(payload).decode("ascii"),
        signature_b64=base64.b64encode(private_key.sign(signed_bytes)).decode("ascii"),
    )
    return envelope.model_dump_json().encode("utf-8")


def verify_attestation(
    wire: bytes,
    *,
    expected_producer: str,
    registry: PublicKeyRegistry,
) -> bytes:
    """Verify a producer-bound Ed25519 envelope and return its payload."""

    try:
        envelope = SignedAttestation.model_validate_json(wire)
        payload = base64.b64decode(envelope.payload_b64, validate=True)
        signature = base64.b64decode(envelope.signature_b64, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise AttestationVerificationError(AttestationRefusal.MALFORMED) from exc

    record = registry.get(envelope.key_id)
    if record is None:
        raise AttestationVerificationError(AttestationRefusal.UNKNOWN_KEY)
    if envelope.producer != expected_producer or record.producer != expected_producer:
        raise AttestationVerificationError(AttestationRefusal.WRONG_PRODUCER)

    signed_bytes = _signed_bytes(
        producer=envelope.producer,
        key_id=envelope.key_id,
        payload=payload,
    )
    try:
        record.public_key.verify(signature, signed_bytes)
    except InvalidSignature as exc:
        raise AttestationVerificationError(AttestationRefusal.INVALID_SIGNATURE) from exc
    return payload
