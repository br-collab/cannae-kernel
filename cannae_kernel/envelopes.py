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
from cannae_kernel.effects import OperationEffects
from cannae_kernel.ids import IntentId, LifecycleId
from cannae_kernel.provenance import Provenance
from cannae_kernel.session import SessionContext

__all__ = [
    "APPROVED_INTENT_VERSION",
    "ApprovedIntentEnvelope",
    "Digest",
]

#: `sha256:<64 hex>`, as `canonical.digest` produces it.
Digest = NonEmptyStr

APPROVED_INTENT_VERSION: Final = "cannae.approved_intent/1.0"


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
