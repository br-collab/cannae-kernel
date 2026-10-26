"""Required tests 1 and 2: round-trip for every model, and golden vectors byte for byte.

The golden files are the cross-language contract. If a test here fails because a field,
enum member or serialization rule changed, that is a breaking change: bump the version,
record it in CHANGELOG.md and run tools/regenerate_golden.py. Do not edit the files by hand.
"""

from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path

import pytest
from pydantic import BaseModel

import cannae_kernel
from cannae_kernel.canonical import canonical_bytes, digest
from tests.factories import golden_instances

ROOT = Path(__file__).resolve().parent.parent
GOLDEN_ROOT = ROOT / "tests" / "golden"
GOLDEN = GOLDEN_ROOT / cannae_kernel.__version__
MANIFEST = json.loads((GOLDEN / "MANIFEST.json").read_text())
INSTANCES = golden_instances()


def test_every_kernel_model_has_a_golden_vector() -> None:
    kernel_models = {
        cls.__name__
        for module in (
            "absence",
            "actor",
            "authority",
            "clocks",
            "effects",
            "envelopes",
            "events",
            "finality",
            "halt",
            "journal",
            "measurement",
            "recommendation",
            "session",
        )
        for cls in vars(__import__(f"cannae_kernel.{module}", fromlist=["_"])).values()
        if isinstance(cls, type)
        and issubclass(cls, BaseModel)
        and cls.__module__.startswith("cannae_kernel.")
        and cls.__name__ != "KernelModel"
        and "[" not in cls.__name__
    }
    covered = {type(m).__name__.split("[")[0] for m in INSTANCES.values()}
    assert kernel_models == covered
    assert set(MANIFEST["vectors"]) == set(INSTANCES)


def test_manifest_version_is_the_package_version() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert MANIFEST["version"] == pyproject["project"]["version"] == cannae_kernel.__version__


def test_published_1_x_vectors_remain_available_under_their_version() -> None:
    """A v2 release must not erase the byte contract published by v1.1.2."""
    old = GOLDEN_ROOT / "1.1.2"
    manifest = json.loads((old / "MANIFEST.json").read_text())
    assert manifest["version"] == "1.1.2"
    for entry in manifest["vectors"].values():
        payload = (old / entry["file"]).read_bytes()
        assert entry["digest"] == "sha256:" + hashlib.sha256(payload).hexdigest()


@pytest.mark.parametrize("name", sorted(INSTANCES))
def test_round_trip(name: str) -> None:
    model = INSTANCES[name]
    assert type(model).model_validate_json(canonical_bytes(model)) == model


@pytest.mark.parametrize("name", sorted(INSTANCES))
def test_golden_bytes_and_digest(name: str) -> None:
    model = INSTANCES[name]
    entry = MANIFEST["vectors"][name]
    on_disk = (GOLDEN / entry["file"]).read_bytes()
    assert canonical_bytes(model) == on_disk
    assert digest(model) == entry["digest"]
    # Independent of the kernel's own hashing code.
    assert entry["digest"] == "sha256:" + hashlib.sha256(on_disk).hexdigest()


@pytest.mark.parametrize("name", sorted(INSTANCES))
def test_golden_file_parses_back_to_the_instance(name: str) -> None:
    model = INSTANCES[name]
    on_disk = (GOLDEN / MANIFEST["vectors"][name]["file"]).read_bytes()
    assert type(model).model_validate_json(on_disk) == model
