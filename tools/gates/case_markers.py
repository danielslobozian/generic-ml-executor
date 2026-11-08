# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Pytest plugin that writes the ``case`` markers of the collected tests to JSON.

Used by the ``acceptance_inventory`` session:
``pytest --collect-only -p tools.gates.case_markers --case-markers-out=<file>``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register the output option.

    Args:
        parser: The pytest option parser.
    """
    parser.addoption("--case-markers-out", action="store", default=None)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Write each collected test's case identities.

    Args:
        config: The pytest configuration.
        items: The collected tests.
    """
    out = config.getoption("--case-markers-out")
    if not isinstance(out, str):
        return
    markers: dict[str, list[str]] = {}
    for item in items:
        cases = [str(mark.args[0]) for mark in item.iter_markers("case") if mark.args]
        if cases:
            markers[item.nodeid] = sorted(cases)
    Path(out).write_text(json.dumps(markers, indent=2, sort_keys=True) + "\n", encoding="utf-8")
