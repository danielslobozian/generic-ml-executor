# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""TEST-python-TT01-04: declared imports (realization RV-09(b)), on every cell.

The imports of every module under ``src/`` (top-level name, or the full dotted
name inside the ``backports`` namespace), less the package itself and the
standard library of any supported version, map through the committed table to
distribution names, which must equal the requirement names of
``[project] dependencies`` (PEP 508 name, PEP 503 normalisation, markers
ignored). Standard library only: ``packaging`` is not imported.
"""

from __future__ import annotations

import ast
import re
import sys
import tomllib
from pathlib import Path

import pytest

PACKAGE = "generic_ml_executor"
STDLIB_EXTRA = frozenset({"compression"})  # standard library from Python 3.14 (PEP 784)
DISTRIBUTIONS = {  # committed import-to-distribution table
    "h11": "h11",
    "wsproto": "wsproto",
    "truststore": "truststore",
    "psutil": "psutil",
    "brotli": "Brotli",
    "backports.zstd": "backports.zstd",
}
PEP508_NAME = re.compile(r"^\s*([A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)")


def normalise(name: str) -> str:
    """Return the PEP 503 normalised form of a distribution name.

    Args:
        name: A distribution name.

    Returns:
        Lower case, with runs of ``-``, ``_`` and ``.`` replaced by ``-``.
    """
    return re.sub(r"[-_.]+", "-", name).lower()


def _from_names(node: ast.ImportFrom) -> set[str]:
    if node.level or not node.module:
        return set()
    if node.module == "backports":  # namespace package: the module is the imported name
        return {f"backports.{alias.name}" for alias in node.names}
    return {node.module}


def _import_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names |= _from_names(node)
    return names


def _key(name: str) -> str:
    parts = name.split(".")
    return ".".join(parts[:2]) if parts[0] == "backports" and len(parts) > 1 else parts[0]


def inspect(src: Path, pyproject: Path) -> list[str]:
    """Compare the third-party imports under ``src`` with the declared requirements.

    Args:
        src: The source root.
        pyproject: The project metadata file.

    Returns:
        One message per difference, naming the module or the requirement.
    """
    problems: list[str] = []
    used: set[str] = set()
    for module in sorted(src.rglob("*.py")):
        for name in sorted(_import_names(ast.parse(module.read_text(encoding="utf-8")))):
            key = _key(name)
            if key == PACKAGE or key.split(".")[0] in sys.stdlib_module_names | STDLIB_EXTRA:
                continue
            if key not in DISTRIBUTIONS:
                problems.append(f"{module.as_posix()}: unmapped third-party import '{key}'")
                continue
            used.add(normalise(DISTRIBUTIONS[key]))
    project = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]
    declared: set[str] = set()
    for requirement in project.get("dependencies", []):
        match = PEP508_NAME.match(requirement)
        if match:
            declared.add(normalise(match.group(1)))
    problems += [f"imported but not declared: {name}" for name in sorted(used - declared)]
    problems += [f"declared but imported by no module: {name}" for name in sorted(declared - used)]
    return problems


def _fixture(tmp_path: Path, imports: str, dependencies: list[str]) -> list[str]:
    src = tmp_path / "src" / PACKAGE
    src.mkdir(parents=True)
    (src / "__init__.py").write_text(imports, encoding="utf-8")
    pyproject = tmp_path / "pyproject.toml"
    listed = ", ".join(f"'{d}'" for d in dependencies)
    pyproject.write_text(f"[project]\nname = 'x'\ndependencies = [{listed}]\n", encoding="utf-8")
    return inspect(tmp_path / "src", pyproject)


def test_skeleton_has_both_sets_empty() -> None:
    """The committed tree declares no requirement and imports no third-party package."""
    assert inspect(Path("src"), Path("pyproject.toml")) == []


@pytest.mark.parametrize(
    ("imports", "dependencies"),
    [
        ("import brotli\n", ["Brotli"]),
        (
            "from backports import zstd\nimport backports.zstd\n",
            ['backports.zstd; python_version < "3.14"'],
        ),
        ("import compression.zstd\nimport asyncio\nfrom generic_ml_executor import api\n", []),
        ("import psutil\nimport h11\n", ["psutil>=7", "h11 == 0.16"]),
    ],
)
def test_controls_pass(tmp_path: Path, imports: str, dependencies: list[str]) -> None:
    """Declared and imported sets that agree pass, markers and versions ignored."""
    assert _fixture(tmp_path, imports, dependencies) == []


@pytest.mark.parametrize(
    ("imports", "dependencies", "expected"),
    [
        ("import psutil\n", [], "imported but not declared: psutil"),
        ("", ["h11"], "declared but imported by no module: h11"),
        ("import requests\n", [], "unmapped third-party import 'requests'"),
        ("from wsproto.events import Ping\n", ["truststore"], "imported but not declared: wsproto"),
    ],
)
def test_must_fail_fixtures(
    tmp_path: Path, imports: str, dependencies: list[str], expected: str
) -> None:
    """Each must-fail fixture fails, naming the module or requirement."""
    problems = _fixture(tmp_path, imports, dependencies)
    assert any(expected in problem for problem in problems), problems
