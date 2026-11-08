# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""TEST-python-TT01-01 (inventory part): RV-16(f) fixtures for the `acceptance_inventory` gate."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from tools.gates import acceptance_inventory, toml_tables

TARGET = toml_tables.load(Path("acceptance/target-cases.toml"))
INVENTORY = toml_tables.load(Path("acceptance/required-cases.toml"))
SKELETON_MARKERS = {"tests/integration/test_gate_entry.py::test_same_gate_set": ["TC-60"]}
NO_WORKFLOW = Path("no-such-release.yml")


def _with(ident: str, **fields: object) -> dict[str, object]:
    inventory = copy.deepcopy(INVENTORY)
    for entry in toml_tables.tables(inventory, "case"):
        if entry["id"] == ident:
            entry.update(fields)
    return inventory


def _check(
    inventory: dict[str, object], markers: dict[str, list[str]], workflow: Path = NO_WORKFLOW
) -> list[str]:
    return acceptance_inventory.check(TARGET, inventory, markers, workflow)


def test_skeleton_inventory_passes() -> None:
    """The committed inventory with the skeleton's single marked test passes."""
    assert _check(INVENTORY, SKELETON_MARKERS) == []


def test_skeleton_inventory_is_complete() -> None:
    """116 entries: TC-60 implemented, the product pair not-applicable, the rest planned."""
    entries = toml_tables.tables(INVENTORY, "case")
    statuses = {str(e["id"]): str(e["status"]) for e in entries}
    assert len(entries) == 116
    assert {i for i, s in statuses.items() if s == "implemented"} == {"TC-60"}
    assert {i for i, s in statuses.items() if s == "not-applicable"} == {
        "TEST-TU13-07",
        "TEST-TU14-12",
    }
    assert sum(s == "planned" for s in statuses.values()) == 113


@pytest.mark.parametrize(
    ("inventory", "markers", "expected"),
    [
        (
            _with("TC-01", status="implemented"),
            SKELETON_MARKERS,
            "TC-01: implemented without a collected test",
        ),
        (
            INVENTORY,
            {**SKELETON_MARKERS, "t.py::x": ["TC-02"]},
            "TC-02: marked test t.py::x maps to a planned entry",
        ),
        (
            INVENTORY,
            {**SKELETON_MARKERS, "t.py::x": ["TC-99"]},
            "TC-99: marked test t.py::x maps to no inventory entry",
        ),
        (
            _with("TC-03", status="not-applicable"),
            SKELETON_MARKERS,
            "TC-03: not-applicable but outside",
        ),
        (_with("TC-04", venue="validator"), SKELETON_MARKERS, "TC-04: venue 'validator'"),
        (
            INVENTORY,
            {**SKELETON_MARKERS, "t.py::y": ["TEST-TU13-07"]},
            "maps to a not-applicable entry",
        ),
        (_with("TC-05", status="done"), SKELETON_MARKERS, "TC-05: unknown status 'done'"),
    ],
)
def test_failing_fixture_is_named(
    inventory: dict[str, object], markers: dict[str, list[str]], expected: str
) -> None:
    """Each RV-16(f) fixture fails, naming the case."""
    problems = _check(inventory, markers)
    assert any(expected in problem for problem in problems), problems


def test_identity_set_difference_fails() -> None:
    """An inventory lacking an identity or holding an extra one fails, naming it."""
    inventory = copy.deepcopy(INVENTORY)
    cases = toml_tables.tables(inventory, "case")
    inventory["case"] = [e for e in cases if e["id"] != "TC-33"] + [dict(cases[0], id="TC-99")]
    problems = _check(inventory, SKELETON_MARKERS)
    assert "TC-33: required but missing from the inventory" in problems
    assert "TC-99: in the inventory but not required" in problems


def test_target_header_difference_fails() -> None:
    """A target header different from target-cases.toml fails."""
    inventory = copy.deepcopy(INVENTORY)
    inventory["target"] = dict(toml_tables.table(inventory, "target"), sha256="0" * 64)
    assert any(p.startswith("target:") for p in _check(inventory, SKELETON_MARKERS))


RELEASE = """
on: {release: {types: [published]}}
jobs:
  build: {runs-on: x}
  verify: {runs-on: x, needs: build}
  other: {runs-on: x, if: "github.event_name == 'workflow_dispatch'"}
  side: {runs-on: x}
  publish: {runs-on: x, needs: [verify, other]}
"""


@pytest.mark.parametrize(
    ("jobs", "expected"),
    [
        (["verify"], None),
        ([], "names no job"),
        (["missing"], "job 'missing' is not defined"),
        (["side"], "job 'side' is not on publish's needs chain"),
        (["other"], "job 'other' excludes the release event"),
    ],
)
def test_release_pipeline_entries(tmp_path: Path, jobs: list[str], expected: str | None) -> None:
    """An implemented release-pipeline entry needs jobs on publish's chain run on release."""
    workflow = tmp_path / "release.yml"
    workflow.write_text(RELEASE, encoding="utf-8")
    problems = _check(
        _with("TC-61", status="implemented", realized_by=jobs), SKELETON_MARKERS, workflow
    )
    if expected is None:
        assert problems == []
    else:
        assert any(expected in p for p in problems), problems


def test_command_line(tmp_path: Path) -> None:
    """The command line reads the marker file."""
    markers = tmp_path / "markers.json"
    markers.write_text('{"a.py::b": ["TC-60"]}', encoding="utf-8")
    assert acceptance_inventory.main([f"--markers={markers}"]) == 0
