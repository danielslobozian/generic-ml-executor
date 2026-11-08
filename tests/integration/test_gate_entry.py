# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""TEST-TU01-01 (TC-60): the same gate set and tool versions locally and on every CI cell.

Static part, on every cell: CI runs the very entry point used locally, with the
locked tools, on the full OS x Python matrix. The run part is each cell's
report ``results/<os>-<python>.json`` and the ``ci`` roll-up.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.gates import yaml_reader

OSES = {"ubuntu-latest", "macos-latest", "windows-latest"}
PYTHONS = {"3.11", "3.12", "3.13", "3.14", "3.15"}


@pytest.mark.case("TC-60")
def test_same_gate_set() -> None:
    """Every CI cell runs ``uv run --frozen nox -s green`` with the pinned uv and locked tools."""
    workflow = yaml_reader.mapping(yaml_reader.load(Path(".github/workflows/ci.yml")))
    cell = yaml_reader.mapping(yaml_reader.mapping(workflow.get("jobs")).get("cell"))
    matrix = yaml_reader.mapping(yaml_reader.mapping(cell.get("strategy")).get("matrix"))
    assert {str(o) for o in yaml_reader.sequence(matrix.get("os"))} == OSES
    assert {str(p) for p in yaml_reader.sequence(matrix.get("python"))} == PYTHONS
    commands = [
        yaml_reader.mapping(step).get("run") for step in yaml_reader.sequence(cell.get("steps"))
    ]
    assert "uv run --frozen nox -s green" in commands
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    assert 'required-version = "==0.12.5"' in pyproject
    setup = next(
        yaml_reader.mapping(yaml_reader.mapping(step).get("with"))
        for step in yaml_reader.sequence(cell.get("steps"))
        if str(yaml_reader.mapping(step).get("uses", "")).startswith("astral-sh/setup-uv@")
    )
    assert setup.get("version") == "0.12.5"
    assert Path("uv.lock").is_file()
