# CLAUDE.md — cannae-kernel

Guidance for Claude Code in this repository. The workspace rules in `~/Code/cannae/CLAUDE.md` also apply.

## What this is
The shared kernel of Project Cannae Legion: the shapes that Aureon, Legiones Cannenses (L.C.) and Atreides must agree on. It is the dependency root for all three (decision JUM-D-05 in the joint upgrade map CL-JUM-001).

## Hard rule: no domain logic
- No rail rules, netting, policy thresholds, agents, storage, network or system clock.
- **If a type needs domain knowledge to validate, it does not belong here.** It belongs in the domain that has that knowledge.
- The kernel may hold vocabulary (enums) and structural rules that need no outside knowledge: clock ordering, which actor kinds may authorize, when a confidence is allowed.
- Library code never reads the system clock or an entropy source. Callers inject both (`ids.new_*`). `tests/test_boundaries.py` enforces this.
- The sole runtime dependency is `pydantic>=2.6,<3.0`. The kernel never imports `aureon`, `atreides` or `lc`.

## Model rules
- Every model subclasses `KernelModel`: `frozen=True`, `extra="forbid"`, `strict=True`.
- Every enum is a `StrEnum` whose member values equal their names. Unknown values are rejected at construction, never coerced.
- Datetimes are UTC-aware (`UtcDatetime`). Decimals are `KernelDecimal`: a decimal string in JSON, never a float.

## Versioning rule
- Current version: `0.1.0`. Git tag `v0.1.0` is created only after Bill approves.
- **Any change to a field, an enum member or a canonical-serialization rule is a breaking change.** While below 1.0:
  1. bump the minor version in `pyproject.toml` and `cannae_kernel/__init__.py`;
  2. record the change in `CHANGELOG.md`;
  3. run `python tools/regenerate_golden.py` and add or update the golden-vector test.
- `tests/golden/` holds the canonical bytes and digest of one instance of every model. These files are the cross-language contract. They change only with a version bump, and are never edited by hand. The regeneration tool refuses to overwrite vectors for a version that already has them.

## Working rules
- Python 3.11. `uv sync --locked --extra dev`, then `ruff check .`, `mypy cannae_kernel tests tools`, `pytest` (coverage gate 95%).
- One work package per commit, with its tests.
- Spell out acronyms on first use in docs.
