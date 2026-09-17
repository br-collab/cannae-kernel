# Changelog

Every change to a field, an enum member or a canonical-serialization rule is breaking and bumps the minor version while below 1.0 (see CLAUDE.md).

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
