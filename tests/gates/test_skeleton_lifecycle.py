# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""TEST-python-TT01-02 (static part; RV-17(a)): the skeleton's gate register and coverage subject.

The run part (``green`` locally and on every CI cell runs exactly this set) is
evidenced by the cell reports ``results/<os>-<python>.json``.
"""

from __future__ import annotations

import configparser
from pathlib import Path

from tools.gates import gate_set, toml_tables

TU01_SET = {
    "lint", "complexity", "structure", "imports", "typecheck", "tests", "coverage", "security",
    "licenses", "workflows", "public_api", "gate_set", "acceptance_inventory", "sonar", "codacy",
}  # fmt: skip


def test_register_holds_exactly_the_tu01_set_active() -> None:
    """TU-01's gate set is active; only evidence (TU-02) and docs (TU-19) are pending."""
    rows = gate_set.register_rows(Path(gate_set.REGISTER).read_text(encoding="utf-8"))
    assert {s for s, (_, state) in rows.items() if state == "active"} == TU01_SET
    assert {s: owner for s, (owner, state) in rows.items() if state == "pending"} == {
        "evidence": "TU-02",
        "docs": "TU-19",
    }


def test_coverage_measures_the_package() -> None:
    """Coverage measures the package, whose root ``__init__`` holds statements."""
    config = configparser.ConfigParser()
    config.read(".coveragerc", encoding="utf-8")
    assert config["run"]["source"] == "generic_ml_executor"
    assert config["run"].getboolean("branch")


def test_required_case_set_binds_the_target() -> None:
    """The required-case set names the bound specification and its 47 TCs and 67 TESTs."""
    target = toml_tables.load(Path("acceptance/target-cases.toml"))
    header = toml_tables.table(target, "target")
    assert header["sha256"] == "bc61ce46812153bd44ba67c7c586999faab06afce364d100830af3cb9d581bb7"
    assert len(toml_tables.strings(target, "tc")) == 47
    assert len(toml_tables.strings(target, "test")) == 67
