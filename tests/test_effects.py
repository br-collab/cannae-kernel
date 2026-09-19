"""R4: the question is "is anything irreversible outside this process".

aureon #34 is the earned defect. A route inventory asked "does this mutate
application state", answered no for two endpoints that send real email from a
named person's account, and left both open to anonymous callers. Nothing in the
process changed and something in the world did, so the answer was right and the
question was wrong.

The tests below hold three things: the vocabulary covers what the order names,
a declaration cannot be omitted, and "contained" means what it says.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cannae_kernel.effects import ExternalEffect, OperationEffects

EMAIL_TEST = OperationEffects(
    operation="POST /api/email/test",
    effects=(ExternalEffect.SENDS,),
    note="sends real email from the operator's account; nothing in-process changes",
)


# --- the vocabulary --------------------------------------------------------------


def test_the_taxonomy_covers_what_the_order_names() -> None:
    """ "sends, pays, submits, publishes, or writes to anything the process does not own"."""
    named = {"SENDS", "PAYS", "SUBMITS", "PUBLISHES", "WRITES_FOREIGN_STORE"}
    assert named <= {effect.value for effect in ExternalEffect}


def test_the_taxonomy_carries_the_one_the_order_did_not_anticipate() -> None:
    """Found by the aureon sweep: metered third-party calls on our credentials.

    It reads as harmless — nothing is written anywhere we can see — and the
    traffic lands in someone else's logs attributed to us, the allowance does
    not come back, and the caller chose the volume.
    """
    assert ExternalEffect.CONSUMES_CREDENTIALED_QUOTA in ExternalEffect


# --- a declaration cannot be omitted ---------------------------------------------


def test_an_operation_cannot_be_left_unclassified() -> None:
    """No default. An operation nobody has thought about cannot be constructed."""
    with pytest.raises(ValidationError):
        OperationEffects(operation="POST /api/email/test", note="?")  # type: ignore[call-arg]


def test_a_declaration_must_carry_its_reasoning() -> None:
    """#34's inventory recorded a verdict and not the reasoning, so nobody could disagree."""
    with pytest.raises(ValidationError):
        OperationEffects(operation="POST /x", effects=())  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        OperationEffects(operation="POST /x", effects=(), note="")


def test_an_operation_must_be_named() -> None:
    with pytest.raises(ValidationError):
        OperationEffects(operation="", effects=(), note="pure computation")


# --- contained means contained ---------------------------------------------------


def test_the_email_route_is_not_contained_although_it_changes_no_state() -> None:
    """The exact case #34 got wrong, stated in the type."""
    assert EMAIL_TEST.is_irreversible_outside
    assert not EMAIL_TEST.is_contained


def test_an_empty_declaration_is_a_claim_of_containment() -> None:
    pure = OperationEffects(
        operation="POST /api/thesis/analyze",
        effects=(),
        note="parses the supplied text and returns an analysis; writes nothing",
    )
    assert pure.is_contained
    assert not pure.is_irreversible_outside


@pytest.mark.parametrize("effect", list(ExternalEffect))
def test_any_single_effect_makes_an_operation_uncontained(effect: ExternalEffect) -> None:
    declaration = OperationEffects(operation="POST /x", effects=(effect,), note="n")
    assert not declaration.is_contained


# --- the shape crosses a boundary -------------------------------------------------


def test_the_same_effects_declared_differently_are_the_same_declaration() -> None:
    """Otherwise two identical operations get two digests and the freeze is noise."""
    one = OperationEffects(
        operation="POST /x",
        effects=(ExternalEffect.SENDS, ExternalEffect.PAYS, ExternalEffect.SENDS),
        note="n",
    )
    two = OperationEffects(
        operation="POST /x",
        effects=(ExternalEffect.PAYS, ExternalEffect.SENDS),
        note="n",
    )
    assert one == two
    assert one.effects == (ExternalEffect.PAYS, ExternalEffect.SENDS)


def test_a_declaration_round_trips() -> None:
    assert OperationEffects.model_validate_json(EMAIL_TEST.model_dump_json()) == EMAIL_TEST


def test_a_non_sequence_is_left_for_the_field_to_refuse() -> None:
    """The normaliser must not swallow bad input and turn it into an empty tuple.

    Returning `()` here would make `effects="SENDS"` — a plausible typo — validate
    as *contained*, which is the one wrong answer this module exists to prevent.
    """
    with pytest.raises(ValidationError):
        OperationEffects(operation="POST /x", effects="SENDS", note="n")  # type: ignore[arg-type]
