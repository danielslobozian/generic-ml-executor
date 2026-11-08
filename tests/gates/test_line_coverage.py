# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""TEST-python-TT01-01 (coverage part) and RV-17(a): the line floor and zero statements."""

from __future__ import annotations

import json
from pathlib import Path

from tools.gates import line_coverage


def _report(covered: int, statements: int) -> dict[str, object]:
    return {"totals": {"covered_lines": covered, "num_statements": statements}}


def test_ratio_below_floor_fails() -> None:
    """A 0.899 line ratio fails and states the ratio."""
    passed, message = line_coverage.evaluate(_report(899, 1000))
    assert not passed
    assert "0.8990 is below" in message


def test_ratio_at_floor_passes() -> None:
    """A 0.90 line ratio passes."""
    assert line_coverage.evaluate(_report(900, 1000))[0]


def test_zero_statements_fail() -> None:
    """Zero measured statements fail as a misconfiguration (RV-17(a))."""
    passed, message = line_coverage.evaluate(_report(0, 0))
    assert not passed
    assert "zero measured statements" in message


def test_malformed_reports_fail() -> None:
    """A report without usable totals fails."""
    assert not line_coverage.evaluate({})[0]
    assert not line_coverage.evaluate({"totals": {"covered_lines": "x"}})[0]


def test_command_line(tmp_path: Path) -> None:
    """The command line returns 1 below the floor and 0 at it."""
    low, high = tmp_path / "low.json", tmp_path / "high.json"
    low.write_text(json.dumps(_report(1, 2)), encoding="utf-8")
    high.write_text(json.dumps(_report(2, 2)), encoding="utf-8")
    assert line_coverage.main([str(low)]) == 1
    assert line_coverage.main([str(high)]) == 0
