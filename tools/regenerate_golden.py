"""Regenerate tests/golden/. Only for a version bump.

The golden vectors are the cross-language contract. They change only together with the
package version (see CLAUDE.md), so this refuses to overwrite vectors recorded for the
version already in pyproject.toml.

    python tools/regenerate_golden.py            # first generation, or after a version bump
"""

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cannae_kernel.canonical import canonical_bytes, digest  # noqa: E402
from tests.factories import golden_instances  # noqa: E402

GOLDEN = ROOT / "tests" / "golden"
MANIFEST = GOLDEN / "MANIFEST.json"


def main() -> int:
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    if MANIFEST.exists() and json.loads(MANIFEST.read_text())["version"] == version:
        print(
            f"Golden vectors for {version} already exist. Bump the version and record the "
            "change in CHANGELOG.md first.",
            file=sys.stderr,
        )
        return 1
    GOLDEN.mkdir(parents=True, exist_ok=True)
    vectors = {}
    for name, model in sorted(golden_instances().items()):
        path = GOLDEN / f"{name}.json"
        path.write_bytes(canonical_bytes(model))
        vectors[name] = {"file": path.name, "digest": digest(model)}
    MANIFEST.write_text(json.dumps({"version": version, "vectors": vectors}, indent=2) + "\n")
    print(f"Wrote {len(vectors)} golden vectors for {version}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
