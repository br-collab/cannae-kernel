# cannae-kernel

The shared kernel of Project Cannae Legion. It is one small package that Aureon (pre-trade intent), Legiones Cannenses (L.C., the synthetic middle layer) and Atreides (post-trade settlement) all import for the shapes they must agree on.

**It contains no domain logic.** There are no rail rules, no netting, no policy thresholds and no agents. The kernel reads no clock, stores nothing and makes no network calls. Its only runtime dependency is Pydantic.

## Status

Version `0.1.0`, untagged. Built in Wave 1 of the joint upgrade map (CL-JUM-001). The three domain repositories adopt it in Waves 2 and 4.

## Modules

| Module | What it gives you |
|---|---|
| `ids` | Typed identifiers: a type prefix plus a ULID (Universally Unique Lexicographically Sortable Identifier), such as `obl_01M2P20SY00000000000000001`. Prefixes: `lif_` lifecycle, `scn_` scenario, `int_` intent, `ord_` order, `exe_` execution, `alc_` allocation, `obl_` obligation, `evt_` event, `act_` actor, `hlt_` halt, `ckp_` checkpoint. The wrong prefix is rejected at construction. `new_*` factories take an injected clock and entropy source. |
| `canonical` | `canonical_bytes(model)` gives deterministic JSON (JavaScript Object Notation) bytes. `digest(model)` gives `sha256:<hex>`. |
| `provenance` | `Provenance`: `FACT_EXTERNAL`, `FACT_SYNTHETIC`, `FORECAST`, `RECOMMENDATION`, `HUMAN_JUDGMENT`, `POLICY_RESULT`. |
| `disposition` | `Disposition`: `PASS`, `HOLD`, `BLOCK`, `INDETERMINATE`. `coerce_disposition` accepts exact values only; anything else becomes `INDETERMINATE`, never `PASS`. |
| `absence` | `Absent` (kind and reason), `Recorded[T]`, ; `Recorded[T] | Absent` is the shape that crosses a boundary. `AbsenceKind` separates `NOTHING_RECORDED` (settled) from `NOT_YET_KNOWN` (in flight) and `NOT_APPLICABLE`. Any absence disposes to `INDETERMINATE`, never `PASS`. `Absent.label` is what a surface shows: never empty, always leading with the negation. |
| `measurement` | `Measurement` (value, provenance, source, `observed_at`), `Constant` (a value with no observation, and the reason there is none) and `ObservedFact`, which is what a gate that requires an observation accepts. `require_observation` is the consumer's refusal; a gate widens what it admits explicitly, at its own call site. A constant has no path to an `ObservedFact`. |
| `domains` | `Domain`: `AUREON`, `LC`, `ATREIDES`, `C2`, `EMULATOR`. |
| `clocks` | `EventTimes`: event, observation, processing and optional decision time, all UTC, in non-decreasing order. |
| `actor` | `ActorRef` and `ActorKind`. The kernel does not know who an `ActorId` is: the actor registry (identifier to person or service, role and entitlements) belongs to the Cannae C2 harness. |
| `authority` | `AuthorityRecord`. Only an authenticated `HUMAN` or `DETERMINISTIC_SERVICE` may authorize. |
| `halt` | `HaltContext` and `gate_under_halt(ctx, domain)`, which returns `BLOCK` for an active in-scope halt and `PASS` otherwise. Any authenticated actor may declare a halt; only an authenticated human may clear one. |
| `finality` | `FinalityType` and `FinalityAssertion`. A forecast or recommendation must carry a confidence. A fact or policy result must not; a human judgment may. A fact cannot be observed before it takes effect. |
| `envelopes` | The frozen cross-domain contracts. `ApprovedIntentEnvelope` (Aureon → L.C.) `ExecutionEvent` (venue emulator → L.C.) and `ClearingTransformation` (within L.C., carried by reference) and `SettlementObligationEnvelope` (L.C. → Atreides) and `ObligationAcceptanceRecord` (Atreides out) are **all five**, each frozen at 1.0. Each carries identity, lineage, session and a **`payload_digest`** — the domain payload stays with the domain that can validate it, per JUM-D-01. `tests/test_envelope_freeze.py` fails if a shape changes without its version moving. |
| `effects` | `ExternalEffect` (`SENDS`, `PAYS`, `SUBMITS`, `PUBLISHES`, `WRITES_FOREIGN_STORE`, `CONSUMES_CREDENTIALED_QUOTA`) and `OperationEffects`. The question is "is anything irreversible outside this process", not "does application state change". No default: an operation nobody has classified cannot be constructed. |
| `session` | `MarketSession` (`REGULAR`, `CLOSING_PERIOD`, `OVERNIGHT`), `BusinessDate` (the date, the calendar that fixed it, and what established it) and `SessionContext`. There is deliberately **no** way to derive either from a timestamp: from 6 Dec 2026 Monday's trading day begins Sunday 9:00pm ET, so an instant establishes neither. |
| `delivery` | `DeliveryPattern` (`DVP`, `PVP`, `FOP`, `PAYMENT_ONLY`, `OTHER_CONTINGENT`) and `ClearingMethod`. |
| `events` | `EventEnvelope[T]`, the hash-chained journal entry, with `seal` to build one and `verify` to check one. `parent_ids` holds event IDs only; cross-domain identifiers (intent, order, obligation) go in the payload. |
| `journal` | `verify_chain(envelopes)`, which reports tampering, broken links, reordering, duplicate idempotency keys and event IDs, and mixed lifecycles. `JournalCheckpoint` records a journal's head outside the journal, and `verify_chain(..., expected_head=checkpoint)` reports `HEAD_MISMATCH`, which makes a rewritten tail detectable. |

## Canonical serialization

The rule set is part of the contract (full text in `cannae_kernel/canonical.py`):

- **Encoding:** UTF-8, keys sorted, no insignificant whitespace.
- **Keys:** ASCII only; a non-ASCII key raises. The kernel deliberately does not implement full RFC 8785 (JSON Canonicalization Scheme). ASCII keys and safe integers remove its two differences that matter across languages: key ordering and large-number formatting.
- **Integers:** within ±(2^53 − 1); anything larger raises. Quantities and money are decimals.
- **Decimal:** a plain-notation string that keeps its scale (`"1000000.00"`). Scale is significant: `"1.0"` and `"1.00"` digest differently. **Every domain contract must therefore declare the scale of each decimal field** (a Wave 3 freeze rule).
- **Datetime:** UTC ISO-8601 with microseconds and `Z` (`"2026-09-16T21:30:00.000000Z"`).
- **Enums:** their values.
- **Floats:** rejected everywhere.

Journal order is defined by prior-digest links, not by identifier order: identifiers minted in the same millisecond may sort either way.

The canonical bytes and digest of one instance of every model are in `tests/golden/`. Those files are what another language implementation must reproduce byte for byte.

## Example

```python
import os
from datetime import UTC, datetime

from cannae_kernel.ids import new_lifecycle_id

lifecycle_id = new_lifecycle_id(clock=lambda: datetime.now(UTC), entropy=os.urandom)
```

The caller supplies the clock and randomness. In tests, pass fixed ones to get reproducible identifiers.

## Development

```bash
uv sync --locked --extra dev
ruff check . && ruff format --check .
mypy cannae_kernel tests tools
pytest                      # coverage gate: 95%
```

See `CLAUDE.md` for the versioning rule: any change to a field, enum member or serialization rule is breaking.

## License

MIT (see `LICENSE`).
