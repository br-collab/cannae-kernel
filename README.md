# cannae-kernel

The shared kernel of Project Cannae Legion. It is one small package that Aureon (pre-trade intent), Legiones Cannenses (L.C., the synthetic middle layer) and Atreides (post-trade settlement) all import for the shapes they must agree on.

**It contains no domain logic.** There are no rail rules, no netting, no policy thresholds and no agents. The kernel reads no clock, stores nothing and makes no network calls. Its only runtime dependency is Pydantic.

## Status

Version `0.1.0`, untagged. Built in Wave 1 of the joint upgrade map (CL-JUM-001). The three domain repositories adopt it in Waves 2 and 4.

## Modules

| Module | What it gives you |
|---|---|
| `ids` | Typed identifiers: a type prefix plus a ULID (Universally Unique Lexicographically Sortable Identifier), such as `obl_01M2P20SY00000000000000001`. The wrong prefix is rejected at construction. `new_*` factories take an injected clock and entropy source. |
| `canonical` | `canonical_bytes(model)` gives deterministic JSON (JavaScript Object Notation) bytes. `digest(model)` gives `sha256:<hex>`. |
| `provenance` | `Provenance`: `FACT_EXTERNAL`, `FACT_SYNTHETIC`, `FORECAST`, `RECOMMENDATION`, `HUMAN_JUDGMENT`, `POLICY_RESULT`. |
| `disposition` | `Disposition`: `PASS`, `HOLD`, `BLOCK`, `INDETERMINATE`. `coerce_disposition` accepts exact values only; anything else becomes `INDETERMINATE`, never `PASS`. |
| `domains` | `Domain`: `AUREON`, `LC`, `ATREIDES`, `C2`, `EMULATOR`. |
| `clocks` | `EventTimes`: event, observation, processing and optional decision time, all UTC, in non-decreasing order. |
| `actor` | `ActorRef` and `ActorKind`. |
| `authority` | `AuthorityRecord`. Only an authenticated `HUMAN` or `DETERMINISTIC_SERVICE` may authorize. |
| `halt` | `HaltContext` and `gate_under_halt(ctx, domain)`, which returns `BLOCK` for an active in-scope halt and `PASS` otherwise. |
| `finality` | `FinalityType` and `FinalityAssertion`. A fact carries no confidence; a forecast must carry one. |
| `delivery` | `DeliveryPattern` (`DVP`, `PVP`, `FOP`, `PAYMENT_ONLY`, `OTHER_CONTINGENT`) and `ClearingMethod`. |
| `events` | `EventEnvelope[T]`, the hash-chained journal entry, with `seal` to build one and `verify` to check one. |
| `journal` | `verify_chain(envelopes)`, which reports tampering, broken links, reordering, duplicate idempotency keys and event IDs, and mixed lifecycles. |

## Canonical serialization

The rule set is part of the contract (full text in `cannae_kernel/canonical.py`):

- **Encoding:** UTF-8, keys sorted, no insignificant whitespace.
- **Decimal:** a plain-notation string that keeps its scale (`"1000000.00"`).
- **Datetime:** UTC ISO-8601 with microseconds and `Z` (`"2026-09-16T21:30:00.000000Z"`).
- **Enums:** their values.
- **Floats:** rejected everywhere.

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
