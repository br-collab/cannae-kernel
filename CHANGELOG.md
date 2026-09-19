# Changelog

Every change to a field, an enum member or a canonical-serialization rule is breaking and bumps the minor version while below 1.0 (see CLAUDE.md).

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
