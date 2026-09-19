"""The cross-domain envelopes, frozen (W3 § "the five contracts").

Five envelopes cross the three domains. Today each is implied by the code that
happens to produce it. Freezing them makes them declared, versioned and
enforced, so that a change to one is a change someone has to make on purpose.

What "frozen" means here: a contract has a version, a canonical JSON form, a
digest, a golden vector, and **a test that fails if the shape changes without
the version moving** (`tests/test_envelope_freeze.py`).

Why these are skeletons, not the whole envelope
-----------------------------------------------
The tasking order says the five live here, because all three domains already
depend on the kernel and nothing else is common to all three. It does not
follow that their *contents* live here.

`aureon.contracts.approved_intent.ApprovedIntentEnvelope` already exists, is
sealed and verified, and has four live consumers. Its `IntentTerms` validates
`asset_class` through a quantity model; `ExecutionConstraints` knows about
venues and time-in-force. By this repository's hard rule — *"if a type needs
domain knowledge to validate, it does not belong here"* — none of that can move.

So each envelope here carries the part that genuinely crosses a boundary: the
identity, the lineage, the session, and a **digest of the domain payload**. The
payload stays with the domain that can validate it, and the envelope references
it rather than copying it.

That is not a new idea; it is JUM-D-01 applied to all five rather than to one.
The map already says `ObligationAcceptanceRecord` "*references its digest rather
than copying its economics*", for the reason that one owner per field is what
stops two domains disagreeing about the same number. The same reasoning applies
upstream.

What a skeleton therefore guarantees, and what it does not
----------------------------------------------------------
It guarantees that two domains agree about *which* thing they are discussing,
which revision of it, in which session, and that neither has altered the payload
since it was sealed. It does not guarantee that they agree about what is *in*
the payload — that is the domain's own contract test, and it stays there.
"""

from __future__ import annotations

from typing import Final, Literal, Self

from pydantic import model_validator

from cannae_kernel._model import KernelModel, NonEmptyStr, PositiveSafeInt
from cannae_kernel.actor import ActorRef
from cannae_kernel.clocks import EventTimes
from cannae_kernel.effects import OperationEffects
from cannae_kernel.ids import EventId, IntentId, LifecycleId
from cannae_kernel.provenance import Provenance
from cannae_kernel.session import SessionContext

__all__ = [
    "APPROVED_INTENT_VERSION",
    "CLEARING_TRANSFORMATION_VERSION",
    "EXECUTION_EVENT_VERSION",
    "OBSERVED_EXECUTION",
    "ApprovedIntentEnvelope",
    "ClearingTransformation",
    "Digest",
    "ExecutionEvent",
]

#: `sha256:<64 hex>`, as `canonical.digest` produces it.
Digest = NonEmptyStr

APPROVED_INTENT_VERSION: Final = "cannae.approved_intent/1.0"
EXECUTION_EVENT_VERSION: Final = "cannae.execution_event/1.0"
CLEARING_TRANSFORMATION_VERSION: Final = "cannae.clearing_transformation/1.0"

OBSERVED_EXECUTION: Final = frozenset({Provenance.FACT_EXTERNAL, Provenance.FACT_SYNTHETIC})
"""An execution is something that happened: a venue reported it, or an emulator
standing in for one did. Nothing else can be an execution."""


class ApprovedIntentEnvelope(KernelModel):
    """Aureon to Legiones Cannenses: an intent a human has approved for release.

    The skeleton only. The approved terms themselves — instrument, side,
    quantity, venues, the policy and authority manifests — stay in
    ``aureon.contracts.approved_intent``, which is the domain that can validate
    them, and are referenced here by ``payload_digest``.
    """

    schema_version: Literal["cannae.approved_intent/1.0"] = APPROVED_INTENT_VERSION

    envelope_id: IntentId
    lifecycle_id: LifecycleId
    """The identity that survives the whole lifecycle, across all three domains."""

    revision: PositiveSafeInt
    prior_digest: Digest | None
    """The digest of the revision this one supersedes, or ``None`` for revision 1.

    Not a `Recorded`/`Absent` pair: the absence here carries no reason worth
    recording, because "this is the first revision" is fully stated by
    ``revision == 1``, and the validator below requires the two to agree.
    """

    session: SessionContext
    """R3: which session, and which settlement business date. Both stated
    upstream, because neither can be derived downstream from a timestamp."""

    approved_by: ActorRef
    provenance: Provenance
    """R1: what kind of claim this is. An approval is ``HUMAN_JUDGMENT``."""

    effects: OperationEffects
    """R4: what acting on this envelope does outside the process."""

    payload_digest: Digest
    """``digest`` of the domain envelope this one refers to.

    The receiving domain recomputes it over the payload it was given. If the two
    disagree, the payload changed after approval, and that is the only question
    the kernel is able to answer about it.
    """

    @model_validator(mode="after")
    def _revision_and_prior_agree(self) -> Self:
        """A first revision supersedes nothing; a later one must say what it supersedes.

        Without this, revision 4 with no prior digest is a lineage with a hole in
        it that still validates — and the hole is invisible, because every field
        present is well-formed.
        """
        if self.revision == 1 and self.prior_digest is not None:
            raise ValueError("revision 1 supersedes nothing, so prior_digest must be None")
        if self.revision > 1 and self.prior_digest is None:
            raise ValueError(f"revision {self.revision} must name the digest it supersedes")
        return self

    @model_validator(mode="after")
    def _an_approval_is_a_human_judgment(self) -> Self:
        """The one thing the kernel does know about an *approved* intent.

        A forecast or a policy result is not an approval. CAOM-001 requires
        explicit operator action at every approval gate, so an envelope that
        claims to be approved and carries any other provenance is making a claim
        the authority model forbids.
        """
        if self.provenance is not Provenance.HUMAN_JUDGMENT:
            raise ValueError(
                f"an approved intent is HUMAN_JUDGMENT, not {self.provenance.value}: "
                "every approval gate requires explicit operator action (CAOM-001)"
            )
        return self


class ExecutionEvent(KernelModel):
    """The venue emulator to Legiones Cannenses: a fill, as reported.

    A **venue fact** (CL-JUM-001 §5). Either a venue reported it
    (``FACT_EXTERNAL``) or a synthetic emulator standing in for one did
    (``FACT_SYNTHETIC``). Both may cross this boundary; R1 decides separately
    what may satisfy a gate, and a synthetic fill never satisfies one that
    requires an observation.

    That distinction is the point of this contract rather than a detail of it.
    CL-JUM-001 §2 records that execution events are today "fabricated in Aureon
    C2", with "delete fabrication (A4)" against them. A fabricated fill and a
    reported one were the same shape, so nothing downstream could tell them
    apart. Here they cannot be the same shape: the provenance is required, and
    the emulator cannot label its output as a venue's report without saying so.
    """

    schema_version: Literal["cannae.execution_event/1.0"] = EXECUTION_EVENT_VERSION

    event_id: EventId
    lifecycle_id: LifecycleId
    intent_id: IntentId
    """Which approved intent this executes against. The identity, not the digest:
    a fill refers to the intent as a thing, and a re-revised intent does not make
    an earlier fill stop having happened."""

    intent_digest: Digest
    """*And* the digest of the revision it was executed against, which does move.
    Both, because "which intent" and "which version of it" are different
    questions and a break investigation needs the second one."""

    times: EventTimes
    """The four clocks (charter §17.9). Keeping them apart is what prevents
    future-information leakage; `EventTimes` already enforces their ordering."""

    session: SessionContext
    """Which session the fill occurred in, stated by whoever reported it.

    Beyond the order's literal list — R3 names only the approved-intent and
    settlement-obligation envelopes. Included because the session is a *fact
    about this fill*, not a property of the gate that reads it: Overnight bands
    are 20% against 5% in the regular session, so the same price is ordinary in
    one and remarkable in the other. Deriving it downstream from ``event_time``
    is the error R3 exists to prevent, and by 6 December 2026 an instant does not
    determine a session. Reported in `_reports/W3-report.md` as an addition.
    """

    provenance: Provenance
    payload_digest: Digest
    """``digest`` of the domain's own execution report — price, quantity, venue,
    fees. Those need domain knowledge to validate, so they stay in L.C."""

    @model_validator(mode="after")
    def _an_execution_is_something_that_happened(self) -> Self:
        """A forecast of a fill is not a fill.

        Without this, a model's expected execution and a venue's report are the
        same type, and the only thing separating them is that nobody has yet
        made the mistake.
        """
        if self.provenance not in OBSERVED_EXECUTION:
            raise ValueError(
                f"an execution event is FACT_EXTERNAL or FACT_SYNTHETIC, not "
                f"{self.provenance.value}: an execution is something that happened"
            )
        return self


class ClearingTransformation(KernelModel):
    """Within Legiones Cannenses: what clearing did to a set of executions.

    JUM-D-01 has this one "carried by reference", and that phrase is the whole
    design. A transformation is not a new set of economics; it is a statement
    that *these* inputs produced *that* output, deterministically, under a named
    rule set. The economics belong to the inputs and the output, each of which
    already has an owner.

    So the envelope names what went in, what came out, and which rules were
    applied — and carries none of the numbers itself.
    """

    schema_version: Literal["cannae.clearing_transformation/1.0"] = CLEARING_TRANSFORMATION_VERSION

    lifecycle_id: LifecycleId
    input_digests: tuple[Digest, ...]
    """The executions this transformation consumed, by digest, in the order it
    consumed them. Order is part of the claim: netting is not commutative once
    rounding enters, so two orderings are two different transformations."""

    output_digest: Digest
    """What it produced. A digest, because the output's economics have their own
    owner and restating them here would create a second one."""

    rule_set_version: NonEmptyStr
    """Which rules were applied. A deterministic result is only reproducible
    against the rules that produced it, and those change."""

    provenance: Provenance
    """R1: a clearing transformation is a ``POLICY_RESULT`` — the output of a
    deterministic policy. It is not an observation and not a judgment."""

    @model_validator(mode="after")
    def _a_transformation_transforms_something(self) -> Self:
        """No inputs is not an empty transformation; it is an invented output.

        This is the fabrication shape again: a well-formed record asserting a
        result that nothing produced. An output with no inputs cannot be
        reproduced, reviewed or disputed.
        """
        if not self.input_digests:
            raise ValueError(
                "a clearing transformation with no inputs did not transform anything: "
                "its output was invented rather than derived"
            )
        return self

    @model_validator(mode="after")
    def _the_same_input_is_not_consumed_twice(self) -> Self:
        """Double-counting an execution is a netting error that still validates."""
        if len(set(self.input_digests)) != len(self.input_digests):
            raise ValueError(
                "the same execution appears twice in input_digests: an execution "
                "cannot be cleared twice"
            )
        return self

    @model_validator(mode="after")
    def _a_transformation_is_a_policy_result(self) -> Self:
        if self.provenance is not Provenance.POLICY_RESULT:
            raise ValueError(
                f"a clearing transformation is a POLICY_RESULT, not "
                f"{self.provenance.value}: it is computed, not observed or judged"
            )
        return self
