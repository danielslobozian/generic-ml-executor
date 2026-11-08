# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Public-interface gate: snapshot equality and the documentation-and-tests coupling."""

from __future__ import annotations

from pathlib import Path

from tools.gates import public_api


def test_committed_snapshot_equals_surface() -> None:
    """The committed snapshot is the current (empty) public surface."""
    current = public_api.render(public_api.surface(Path("src")))
    assert Path(public_api.SNAPSHOT).read_text(encoding="utf-8") == current
    assert public_api.surface(Path("src")) == {}


def test_coupling() -> None:
    """A snapshot change needs the reference, the changelog and a test change."""
    snapshot = public_api.SNAPSHOT
    assert public_api.coupling_problems({"README.md"}) == []
    assert len(public_api.coupling_problems({snapshot})) == 3
    complete = {snapshot, "docs/reference/public-api.md", "CHANGELOG.md", "tests/unit/test_x.py"}
    assert public_api.coupling_problems(complete) == []
    assert public_api.coupling_problems(complete - {"CHANGELOG.md"}) == [
        "the public surface changed without changing CHANGELOG.md"
    ]
