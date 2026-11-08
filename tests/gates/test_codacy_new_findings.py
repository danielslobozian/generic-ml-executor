# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Codacy comparison: significant new findings by severity and category, as a multiset."""

from __future__ import annotations

import json
from pathlib import Path

from tools.gates import codacy_new_findings as cnf


def _result(rule: str, level: str, line: str, **properties: object) -> dict[str, object]:
    location = {
        "physicalLocation": {
            "artifactLocation": {"uri": "src/a.py"},
            "region": {"snippet": {"text": line}},
        }
    }
    return {"ruleId": rule, "level": level, "locations": [location], "properties": properties}


def _sarif(tool: str, *results: dict[str, object]) -> dict[str, object]:
    return {
        "version": "2.1.0",
        "runs": [{"tool": {"driver": {"name": tool}}, "results": list(results)}],
    }


def test_existing_findings_are_not_new() -> None:
    """A finding present at the base, at the same identity, is not new."""
    base = _sarif("Pylint", _result("E1", "error", "x = 1"))
    assert cnf.new_significant(base, base) == []


def test_multiset_counts_repeats() -> None:
    """A second occurrence of an identical finding is new."""
    base = _sarif("Pylint", _result("E1", "error", "x = 1"))
    head = _sarif("Pylint", _result("E1", "error", "x = 1"), _result("E1", "error", "x  =  1"))
    assert len(cnf.new_significant(base, head)) == 1


def test_significance_rule() -> None:
    """High fails anywhere; Medium fails only in Security; Low never fails."""
    empty = _sarif("Pylint")
    cases = [
        (_sarif("Pylint", _result("E1", "error", "a")), 1),
        (_sarif("Pylint", _result("W1", "warning", "b")), 0),
        (_sarif("Opengrep", _result("python.lang.security.audit.x", "warning", "c")), 1),
        (_sarif("Trivy", _result("CVE-1", "note", "d", severity="Medium")), 1),
        (_sarif("Pylint", _result("W2", "warning", "e", severity="Critical")), 1),
        (_sarif("Pylint", _result("W3", "note", "f")), 0),
        (_sarif("Pylint", _result("W4", "warning", "g", category="security")), 1),
    ]
    for head, expected in cases:
        assert len(cnf.new_significant(empty, head)) == expected, head


def test_fingerprints_take_precedence() -> None:
    """Partial fingerprints identify a finding regardless of its line text."""
    first = _result("E1", "error", "a")
    first["partialFingerprints"] = {"k": "1"}
    moved = _result("E1", "error", "b")
    moved["partialFingerprints"] = {"k": "1"}
    assert cnf.new_significant(_sarif("T", first), _sarif("T", moved)) == []


def test_command_line(tmp_path: Path) -> None:
    """The command line fails on a significant new finding."""
    base, head = tmp_path / "base.sarif", tmp_path / "head.sarif"
    base.write_text(json.dumps(_sarif("T")), encoding="utf-8")
    head.write_text(json.dumps(_sarif("T", _result("E1", "error", "a"))), encoding="utf-8")
    assert cnf.main([str(base), str(base)]) == 0
    assert cnf.main([str(base), str(head)]) == 1
