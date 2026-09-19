"""The freeze itself: a shape cannot change without its version moving.

`W3-contract-freeze.md` defines frozen as — a version, a canonical JSON form, a
digest, a golden vector, **and a test that fails if the shape changes without
the version moving**. The golden vectors hold the first three. This file is the
fourth, and it is the one that makes the other three mean something.

The difference matters. A golden vector pins *one instance*: change a field's
type from `str` to `int` and the vector still passes as long as the example
happens to serialize the same. A field added with a default does not disturb any
existing instance at all. Both are breaking changes to anyone parsing the
envelope on the other side of a boundary, and neither is visible in a vector.

So the shape — every field name, its type, whether it is required — is hashed
into a digest and recorded in `SHAPES` below. Change the model and this test
fails. There are exactly two honest ways to make it pass: put the shape back, or
move the version and record the new digest as a deliberate act.
"""

from __future__ import annotations

import hashlib
import json

import pytest
from pydantic import BaseModel

from cannae_kernel.envelopes import APPROVED_INTENT_VERSION, ApprovedIntentEnvelope

#: version -> shape digest. One row per frozen contract version. Rows are added,
#: never edited: an edited row is the change this file exists to catch.
SHAPES: dict[str, str] = {
    "cannae.approved_intent/1.0": (
        "76931c93a11cd7e0721a7a556e1098048e71267338b863687830ad2db08fa775"
    ),
}

FROZEN: list[tuple[str, type[BaseModel]]] = [
    (APPROVED_INTENT_VERSION, ApprovedIntentEnvelope),
]


def shape_of(model: type[BaseModel]) -> str:
    """A digest of the declared shape, independent of any instance.

    Built from the JSON schema rather than from `model_fields`, because the
    schema is what a consumer in another language actually reads, and it carries
    the things that break them: nested shapes, enum members, required-ness, and
    the literal values of discriminators.
    """
    schema = model.model_json_schema(mode="serialization")
    canonical = json.dumps(schema, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@pytest.mark.parametrize(("version", "model"), FROZEN, ids=[v for v, _ in FROZEN])
def test_the_shape_has_not_changed_without_the_version_moving(
    version: str, model: type[BaseModel]
) -> None:
    recorded = SHAPES.get(version)
    actual = shape_of(model)
    assert recorded is not None, (
        f"{model.__name__} declares {version}, which has no recorded shape. "
        f"If this is a new version, add:\n    {version!r}: {actual!r},"
    )
    assert actual == recorded, (
        f"{model.__name__} changed shape while still calling itself {version}.\n"
        f"Either put the shape back, or move the version and add:\n"
        f"    {model.__name__.lower()} new version: {actual!r}\n"
        f"Editing the recorded digest in place is the one thing this test exists "
        f"to prevent — a consumer parsing {version} on the other side of a "
        f"boundary has no way to learn that it moved."
    )


@pytest.mark.parametrize(("version", "model"), FROZEN, ids=[v for v, _ in FROZEN])
def test_the_declared_version_is_the_one_the_model_carries(
    version: str, model: type[BaseModel]
) -> None:
    """The version is a field, not a comment, so it travels with the instance."""
    field = model.model_fields["schema_version"]
    assert field.default == version
    assert field.annotation is not str, (
        "schema_version must be a Literal, so a mismatched version is refused at "
        "construction rather than carried"
    )


def test_every_frozen_contract_has_exactly_one_recorded_shape() -> None:
    """A version with no shape, or a shape with no contract, is a gap in the freeze."""
    declared = {version for version, _ in FROZEN}
    assert declared <= set(SHAPES), (
        f"frozen contracts with no recorded shape: {declared - set(SHAPES)}"
    )


def test_the_shape_digest_notices_a_change_this_file_would_otherwise_miss() -> None:
    """Proves the mechanism, rather than trusting it.

    Both of these pass every golden-vector test — the first because no existing
    instance carries the new field, the second because the example value happens
    to serialize identically either way.
    """
    base = shape_of(ApprovedIntentEnvelope)

    class WithAnAddedOptionalField(ApprovedIntentEnvelope):
        note: str | None = None

    class WithARelaxedType(ApprovedIntentEnvelope):
        revision: int  # was PositiveSafeInt

    assert shape_of(WithAnAddedOptionalField) != base, (
        "a field added with a default is invisible to the shape digest"
    )
    assert shape_of(WithARelaxedType) != base, (
        "a widened field type is invisible to the shape digest"
    )
