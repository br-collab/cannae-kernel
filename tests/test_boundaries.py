"""Required test 10, and the library rules in CLAUDE.md that a reviewer cannot see by eye.

- ``cannae_kernel`` imports nothing from ``aureon``, ``atreides`` or ``lc``.
- Library code reads no system clock or entropy, and touches no storage or network.
- The only third-party runtime dependency is Pydantic.
"""

from __future__ import annotations

import ast
import json
import pkgutil
import subprocess
import sys
from pathlib import Path

import cannae_kernel

PACKAGE_DIR = Path(cannae_kernel.__file__).parent
SOURCES = sorted(PACKAGE_DIR.rglob("*.py"))

DOMAIN_PACKAGES = {"aureon", "atreides", "lc"}
# Clocks, entropy, storage and network. None belongs in the kernel.
FORBIDDEN_MODULES = {
    "time",
    "random",
    "secrets",
    "uuid",
    "os",
    "io",
    "pathlib",
    "shutil",
    "sqlite3",
    "socket",
    "ssl",
    "http",
    "urllib",
    "requests",
    "subprocess",
    "threading",
    "asyncio",
}
FORBIDDEN_CALLS = {"now", "utcnow", "today", "open", "urandom", "getrandbits"}
ALLOWED_THIRD_PARTY = {"pydantic", "pydantic_core", "typing_extensions"}


def _imports(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [(node.lineno, alias.name) for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.append((node.lineno, node.module))
    return found


def test_importing_the_kernel_loads_no_domain_package() -> None:
    probe = (
        "import importlib, json, pkgutil, sys\n"
        "import cannae_kernel\n"
        "for m in pkgutil.walk_packages(cannae_kernel.__path__, 'cannae_kernel.'):\n"
        "    importlib.import_module(m.name)\n"
        "print(json.dumps(sorted(sys.modules)))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, check=True
    )
    loaded = json.loads(result.stdout)
    assert [m for m in loaded if m.split(".")[0] in DOMAIN_PACKAGES] == []


def test_source_names_no_domain_package() -> None:
    offenders = [
        f"{p.name}:{line} {name}"
        for p in SOURCES
        for line, name in _imports(p)
        if name.split(".")[0] in DOMAIN_PACKAGES
    ]
    assert offenders == []


def test_source_reads_no_clock_entropy_storage_or_network() -> None:
    offenders = [
        f"{p.name}:{line} import {name}"
        for p in SOURCES
        for line, name in _imports(p)
        if name.split(".")[0] in FORBIDDEN_MODULES
    ]
    for p in SOURCES:
        for node in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "attr", getattr(node.func, "id", None))
                if name in FORBIDDEN_CALLS:
                    offenders.append(f"{p.name}:{node.lineno} call {name}()")
    assert offenders == []


def test_only_pydantic_is_imported_from_outside_the_standard_library() -> None:
    third_party = {
        name.split(".")[0]
        for p in SOURCES
        for _, name in _imports(p)
        if name.split(".")[0] not in sys.stdlib_module_names
        and name.split(".")[0] != "cannae_kernel"
    }
    assert third_party <= ALLOWED_THIRD_PARTY


def test_every_module_is_reachable() -> None:
    walked = {m.name for m in pkgutil.walk_packages(cannae_kernel.__path__, "cannae_kernel.")}
    on_disk = {
        "cannae_kernel." + p.relative_to(PACKAGE_DIR).with_suffix("").as_posix().replace("/", ".")
        for p in SOURCES
        if p.name != "__init__.py"
    }
    assert on_disk <= walked
