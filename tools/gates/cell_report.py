# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Pytest plugin that records each test's outcome and case identities to JSON.

``green`` merges this file into the cell report ``results/<os>-<python>.json``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_OUTCOMES: dict[str, dict[str, object]] = {}


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register the output option.

    Args:
        parser: The pytest option parser.
    """
    parser.addoption("--cell-report-out", action="store", default=None)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Record each collected test with its case identities.

    Args:
        items: The collected tests.
    """
    for item in items:
        cases = sorted(str(mark.args[0]) for mark in item.iter_markers("case") if mark.args)
        _OUTCOMES[item.nodeid] = {"cases": cases, "outcome": "not-run"}


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    """Record a test's outcome, keeping the first failure of any phase.

    Args:
        report: The report of one test phase.
    """
    entry = _OUTCOMES.setdefault(report.nodeid, {"cases": [], "outcome": "not-run"})
    counts = report.when == "call" or report.outcome != "passed"
    if counts and entry["outcome"] in {"not-run", "passed"}:
        entry["outcome"] = report.outcome


def pytest_sessionfinish(session: pytest.Session) -> None:
    """Write the recorded outcomes.

    Args:
        session: The pytest session.
    """
    out = session.config.getoption("--cell-report-out")
    if isinstance(out, str):
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(_OUTCOMES, indent=2, sort_keys=True) + "\n"
        Path(out).write_text(text, encoding="utf-8")
