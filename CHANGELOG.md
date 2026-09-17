# Changelog

Every change to a field, an enum member or a canonical-serialization rule is breaking and bumps the minor version while below 1.0 (see CLAUDE.md).

## 0.1.0 — unreleased (not tagged)

Initial kernel, Wave 1 of CL-JUM-001.

- `ids`: prefixed ULID (Universally Unique Lexicographically Sortable Identifier) types `lc_`, `scn_`, `int_`, `ord_`, `exe_`, `alc_`, `obl_`, `evt_`, `act_`, `hlt_`, with injected-clock factories.
- `canonical`: canonical JSON bytes and `sha256:` digests.
- `provenance`, `disposition`, `domains`, `delivery`: vocabulary enums; `coerce_disposition` fails safe to `INDETERMINATE`.
- `clocks.EventTimes`, `actor.ActorRef`, `authority.AuthorityRecord`, `halt.HaltContext` with `gate_under_halt`, `finality.FinalityAssertion`.
- `events.EventEnvelope` with `seal` and `verify`; `journal.verify_chain`.
- Golden vectors for all eight models in `tests/golden/`.
