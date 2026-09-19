# Changelog

Every change to a field, an enum member or a canonical-serialization rule is breaking and bumps the minor version while below 1.0 (see CLAUDE.md).

## 0.8.0 — 19 Sep 2026

Wave 3, the third of the five contracts. Additive: the nineteen existing golden vectors are byte-identical.

### `ClearingTransformation`, frozen at `cannae.clearing_transformation/1.0`

Within Legiones Cannenses. JUM-D-01 has this one "carried by reference", and that phrase is the design: a transformation is a claim that *these* inputs produced *that* output under *these* rules, not a second copy of economics that already have an owner.

`input_digests`, `output_digest`, `rule_set_version`, and `provenance`, which must be `POLICY_RESULT` — it is computed, not observed and not judged.

Three validators:

- **No inputs is not an empty transformation; it is an invented output.** The fabrication shape again: a well-formed record asserting a result nothing produced, which cannot be reproduced, reviewed or disputed.
- **The same execution cannot be cleared twice.** Double-counting is a netting error that otherwise validates perfectly.
- **Input order is part of the claim.** Netting is not commutative once rounding enters, so two orderings are two different transformations and carry two digests.

One new golden vector: `clearing_transformation`.

## 0.7.0 — 19 Sep 2026

Wave 3, the second of the five contracts. Additive: the eighteen existing golden vectors are byte-identical.

### `ExecutionEvent`, frozen at `cannae.execution_event/1.0`

The venue emulator to Legiones Cannenses: a fill, as reported. A **venue fact** (CL-JUM-001 §5).

`provenance` is required and must be `FACT_EXTERNAL` (a venue reported it) or `FACT_SYNTHETIC` (an emulator standing in for one did). **A forecast of a fill is not a fill**, so nothing else validates.

That distinction is the contract rather than a detail of it. CL-JUM-001 §2 records execution events as today "fabricated in Aureon C2", with "delete fabrication (A4)" against them: a fabricated fill and a reported one were the same shape, so nothing downstream could tell them apart. They are no longer the same shape, and the two differ in the serialized bytes, so a consumer that never asks the question still cannot round-trip one as the other.

It carries `intent_id` **and** `intent_digest` — which intent, and which revision of it. Different questions, and a break investigation needs the second.

`session` is included although R3 names only the approved-intent and settlement-obligation envelopes. The session is a fact about the fill rather than a property of the gate that reads it: Overnight bands are 20% against 5% in the regular session, so the same price is ordinary in one and remarkable in the other. Recorded as an addition in `_reports/W3-report.md`.

One new golden vector: `execution_event`.

## 0.6.0 — 19 Sep 2026

Wave 3, `W3-contract-freeze.md`, the first of the five contracts. Additive: the seventeen existing golden vectors are byte-identical.

### New module `envelopes` — `ApprovedIntentEnvelope`, frozen at `cannae.approved_intent/1.0`

Aureon → Legiones Cannenses. It carries identity (`envelope_id`, `lifecycle_id`), lineage (`revision`, `prior_digest`), the session (R3), the approver, the provenance (R1), the external effects (R4), and a **`payload_digest`**.

**It is a skeleton, and that is a decision.** `aureon.contracts.approved_intent.ApprovedIntentEnvelope` already exists with four live consumers, and its `IntentTerms` validates `asset_class` through a quantity model. This repository's hard rule is that a type needing domain knowledge to validate does not belong here, so the terms stay in aureon and are referenced by digest. JUM-D-01 already says `ObligationAcceptanceRecord` "references its digest rather than copying its economics"; this applies the same reasoning upstream.

Two validators, each holding something that would otherwise validate while being wrong:

- **A lineage cannot have a hole in it.** Revision 1 must supersede nothing; a later revision must name the digest it supersedes. Without this, revision 4 with no `prior_digest` validates, and the hole is invisible because every field present is well-formed.
- **An approved intent is `HUMAN_JUDGMENT`.** CAOM-001 requires explicit operator action at every approval gate, so an envelope claiming approval with `POLICY_RESULT` provenance is a gate approving itself.

### New: the freeze mechanism, `tests/test_envelope_freeze.py`

The order defines frozen as a version, a canonical form, a digest, a golden vector **and a test that fails if the shape changes without the version moving**. The vectors give the first three; this gives the fourth, and it is what makes the others mean anything.

A golden vector pins *one instance*. A field added with a default disturbs no existing instance, and a widened type often serializes identically — both are breaking changes for anyone parsing the envelope across a boundary, and neither shows up in a vector. So the declared shape is hashed from the JSON schema and recorded per version. One test proves the mechanism catches exactly those two cases rather than trusting that it does.

One new golden vector: `approved_intent_envelope`.

## 0.5.0 — 19 Sep 2026

Wave 3, tasking order `W3-contract-freeze.md` § R4. Additive: no existing field, enum member or serialization rule changed, and the sixteen existing golden vectors are byte-identical.

### New module `effects` — every operation declares what it does outside the process

Earned by aureon #34: a route inventory asked *"does this mutate application state"*, answered no for two endpoints that send real email from a named person's account, and left both open to anonymous callers. The answer was right; the question was wrong.

- **`ExternalEffect`** — `SENDS`, `PAYS`, `SUBMITS`, `PUBLISHES`, `WRITES_FOREIGN_STORE`, and `CONSUMES_CREDENTIALED_QUOTA`. The first five are the order's list. The sixth came out of the aureon sweep and the order did not anticipate it: an unauthenticated caller driving metered third-party calls under the operator's credentials. Nothing is written anywhere we can see, the traffic lands in a third party's logs attributed to us, and the caller chose the volume.
- **`OperationEffects`** — `operation`, `effects` and `note`, all required. **There is no default**, so an operation nobody has classified cannot be constructed, and `note` is required because #34's inventory recorded a verdict without the reasoning, which is the kind nobody can disagree with.
- `is_contained` / `is_irreversible_outside` — the question R4 says to ask, by name.

`effects` is sorted and deduplicated before validation, so the same operation declared in two orders carries one digest rather than two.

Whether an uncontained operation requires an authenticated operator, a second approver or a halt check is domain policy and stays in the domains.

One new golden vector: `operation_effects`.

## 0.4.0 — 19 Sep 2026

Wave 3, tasking order `W3-contract-freeze.md` § R3. Additive, but it **extends the canonical serialization rules** — see below. The fourteen existing golden vectors are byte-identical.

### New module `session` — which session, and which business date, both stated

From 6 December 2026 the Securities Information Processors run 23/5: an Overnight session 9:00pm-4:00am ET, and Monday's trading day beginning Sunday at 9:00pm. Overnight Limit Up-Limit Down bands are 20% against 5% in the regular session for a Tier 1 NMS stock above $3 — the same instrument with four times the room to move and no halt.

- **`MarketSession`** — `REGULAR`, `CLOSING_PERIOD`, `OVERNIGHT`. The three the order evidences; not a complete map of a trading day, deliberately (see the module docstring).
- **`BusinessDate`** — `value`, `calendar` and `established_by`, all required. Two calendars disagree about the same instant routinely, so a date with no calendar beside it is not an answer.
- **`SessionContext`** — what a gate is told rather than works out.
- **`BusinessDateNotEstablishedError`** — the kernel's name for what Atreides reports as `PROCESSING_DATE_NOT_ESTABLISHED`.

**There is no function anywhere in the module that takes a `datetime`,** and a test asserts that there is not. Deriving a business date from a timestamp is the error Atreides already refuses to make, and after 6 December a timestamp is not close to sufficient.

### `canonical` now serializes `datetime.date`

A bare `date` canonicalizes as the calendar day it is (`"2026-12-07"`). This is an extension, not a change: nothing previously serialized a `date` — it raised `CanonicalizationError` — so no existing vector moves.

The branch sits **after** the `datetime` branch, because `datetime` subclasses `date`. Had it come first, every instant in every envelope would have silently lost its time and zone while the digests still agreed with each other. `tests/test_canonical.py::test_a_datetime_does_not_degrade_to_a_date` holds the ordering.

Two new golden vectors: `business_date`, `session_context`.

## 0.3.0 — 19 Sep 2026

Wave 3, tasking order `W3-contract-freeze.md` § R2. Additive: no existing field, enum member or serialization rule changed, and the twelve existing golden vectors are byte-identical.

### New module `absence` — absence is a value, with a reason, and never a pass

- **`Absent`** — `kind` and `reason`. The reason is part of the record, not a comment: "no instruction was issued" is why a quorum hold persists nothing, and before this it existed nowhere.
- **`AbsenceKind`** — `NOTHING_RECORDED` (a write could have happened and did not; settled), `NOT_YET_KNOWN` (may still arrive) and `NOT_APPLICABLE`. The order requires "nothing was written" to be distinct from null, from zero **and from "not yet known"**; a consumer treating the three alike is making a claim it has not checked.
- **`Recorded[T]`** — a value that was recorded, **including a recorded `None` or zero**. A recorded absence of quantity is not the same as no record of quantity, which is why this is a separate type rather than an optional field.
- **`Recorded[T] | Absent`** is the shape that crosses a boundary. No explicit discriminator: the differing `state` literals plus the kernel base model's `extra="forbid"` already refuse an absence relabelled as a record, and the test proves it rather than assuming it.
- **`disposition_of`** — `INDETERMINATE` for any absence, whatever kind. `require_recorded` raises `MissingValueError` carrying the reason.
- **`Absent.label`** — what a surface renders. Never empty, and always leading with the negation, so a truncating surface cannot show a first word that reads as a result. #36 is why this belongs in the contract: a contract that can express absence and a surface that cannot display it is still a surface that lies.

Earned by W2B7-V-01 (a DSOR record claimed on a quorum hold), the empty ledger segment, #36 (the `na` state rendering brighter than "not reached") and eight silent read-path catches.

Two new golden vectors: `absent`, `recorded`.

## 0.2.0 — 19 Sep 2026

Wave 3, tasking order `W3-contract-freeze.md` § R1. Additive: no existing field, enum member or serialization rule changed, and the nine existing golden vectors are byte-identical.

### New module `measurement` — a reading carries its provenance, and the consumer refuses

- **`Measurement`** — `value`, `provenance`, `source`, `observed_at`. Any provenance may be carried, because a synthetic or forecast reading is allowed to cross a boundary.
- **`Constant`** — a value with no observation behind it. It has no `observed_at` field, so it cannot be given one, and it carries the `reason` there was no observation. A value without an observation time is not a measurement; this is how it says so.
- **`ObservedFact`** — what a gate requiring an observation accepts. A `Constant` has no path to one, and a `Measurement` is converted only if its provenance is admitted. A `FORECAST` or `RECOMMENDATION` can never become one, however widely a gate admits.
- **`require_observation(reading, *, admitting=OBSERVED)`** — the consumer's check. `OBSERVED` is `FACT_EXTERNAL` alone; `ADMISSIBLE_WITH_DERIVATION` adds `POLICY_RESULT` for a gate that acts on a value computed from live external inputs and says so at its call site.
- **`NotAnObservationError`**, and `Reading`, the tagged union of the two, so a serialized constant cannot be read back as a measurement.

Earned by F1 (a fabricated stress constant read as PASS), Cato-FICC-MCP #2 (a gate returning PROCEED on an absent reading) and W2-ADD-03. The check lives in the type rather than in a filter above it, because a filter survives only while every caller remembers it: see `tests/test_measurement.py::test_a_new_caller_cannot_reintroduce_the_class`.

Three new golden vectors: `measurement`, `measurement_constant`, `observed_fact`.

## 0.1.1 — 17 Sep 2026

Packaging only. No field, enum member or canonical-serialization rule changed, and the golden vectors are byte-identical (`tests/test_golden.py` proves it).

- PEP 561 `py.typed` marker, shipped as package data. A consumer's type checker now reads the kernel's annotations, so Aureon, Atreides and Legiones Cannenses can drop their `follow_untyped_imports` mypy overrides.

## 0.1.0 — 16 Sep 2026

Initial kernel, Wave 1 of CL-JUM-001, amended by W1.1 before the tag.

### W1.1 amendments (decisions JUM-D-17 to JUM-D-25)

Nothing had been published, so the version stays 0.1.0. **The golden vectors were deleted and regenerated once, in the W1.1 commit.** Any copy of the W1 vectors (commit aa83e8c) is void.

- JUM-D-17: `LifecycleId` prefix `lc_` became `lif_`, so it no longer reads as Legiones Cannenses.
- JUM-D-19: any authenticated actor may declare a halt; only an authenticated `HUMAN` may clear one.
- JUM-D-21: confidence is required for `FORECAST` and `RECOMMENDATION`, forbidden for `FACT_EXTERNAL`, `FACT_SYNTHETIC` and `POLICY_RESULT`, and optional for `HUMAN_JUDGMENT`.
- JUM-D-22: a `FACT_*` finality assertion cannot have `observation_time` before `effective_time`.
- JUM-D-24: `canonical_bytes` rejects non-ASCII mapping keys and integers outside ±(2^53 − 1). Kernel integer fields are bounded to match.
- JUM-D-25: new `JournalCheckpoint` model, new `CheckpointId` (`ckp_`), new `ChainIssueCode.HEAD_MISMATCH`, and `verify_chain(..., expected_head=...)`. Nine golden vectors.
- Documentation only: JUM-D-18 (the actor registry lives in the C2 harness), JUM-D-20 (status value sets unchanged), JUM-D-23 (`parent_ids` are event IDs only), and ordering within one millisecond.

### Initial contents

- `ids`: prefixed ULID (Universally Unique Lexicographically Sortable Identifier) types `lif_`, `scn_`, `int_`, `ord_`, `exe_`, `alc_`, `obl_`, `evt_`, `act_`, `hlt_`, `ckp_`, with injected-clock factories.
- `canonical`: canonical JSON bytes and `sha256:` digests.
- `provenance`, `disposition`, `domains`, `delivery`: vocabulary enums; `coerce_disposition` fails safe to `INDETERMINATE`.
- `clocks.EventTimes`, `actor.ActorRef`, `authority.AuthorityRecord`, `halt.HaltContext` with `gate_under_halt`, `finality.FinalityAssertion`.
- `events.EventEnvelope` with `seal` and `verify`; `journal.verify_chain` and `journal.JournalCheckpoint`.
- Golden vectors for all nine models in `tests/golden/`.
