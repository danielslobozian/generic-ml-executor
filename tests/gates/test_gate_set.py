# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""TEST-python-TT01-01 (register part): RV-17(b) register fixtures for the `gate_set` gate."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.gates import gate_set

NOXFILE = Path("noxfile.py").read_text(encoding="utf-8")
REGISTER = Path(gate_set.REGISTER).read_text(encoding="utf-8")


def _row(session: str, owner: str, state: str) -> str:
    return f'\n[[gate]]\nsession = "{session}"\nowner = "{owner}"\nstate = "{state}"\n'


def test_unchanged_skeleton_register_passes() -> None:
    """The committed register matches the nox file, with itself as the prior state."""
    assert gate_set.check(NOXFILE, REGISTER, REGISTER) == []
    assert gate_set.check(NOXFILE, REGISTER, None) == []


@pytest.mark.parametrize(
    ("register", "noxfile", "expected"),
    [
        (
            REGISTER.replace(_row("lint", "TU-01", "active"), _row("lint", "TU-01", "pending")),
            NOXFILE,
            "'lint' is pending",
        ),
        (
            REGISTER.replace(
                _row("evidence", "TU-02", "pending"), _row("evidence", "TU-05", "pending")
            ),
            NOXFILE,
            "'evidence' has owner 'TU-05'",
        ),
        (
            REGISTER.replace(_row("codacy", "TU-01", "active"), ""),
            NOXFILE,
            "'codacy' is in noxfile.py but not in the register",
        ),
        (
            REGISTER + _row("extra", "TU-01", "active"),
            NOXFILE,
            "'extra' is in the register but not in noxfile.py",
        ),
        (
            REGISTER.replace(_row("lint", "TU-01", "active"), _row("lint", "TU-01", "on")),
            NOXFILE,
            "'lint' has state 'on'",
        ),
    ],
)
def test_failing_register_is_named(register: str, noxfile: str, expected: str) -> None:
    """Each RV-17(b) fixture fails, naming the session."""
    problems = gate_set.check(noxfile, register, None)
    assert any(expected in problem for problem in problems), problems


def test_active_at_base_and_pending_now_fails() -> None:
    """A session active at the comparison base cannot return to pending."""
    prior = REGISTER.replace(
        _row("evidence", "TU-02", "pending"), _row("evidence", "TU-02", "active")
    )
    problems = gate_set.check(NOXFILE, REGISTER, prior)
    assert problems == ["session 'evidence' was active at the comparison base and is not now"]


def test_named_sessions_are_read_from_decorators() -> None:
    """Session names come from the decorator, including a `name=` override."""
    source = (
        "import nox\n\n@nox.session(python=False)\ndef a(s): ...\n\n"
        "@nox.session(name='b-gate')\ndef b(s): ...\n\ndef helper(): ...\n"
    )
    assert gate_set.nox_sessions(source) == {"a", "b-gate"}


def test_command_line_with_prior_register(tmp_path: Path) -> None:
    """The command line accepts an explicit prior register."""
    prior = tmp_path / "prior.toml"
    prior.write_text(REGISTER, encoding="utf-8")
    assert gate_set.main([f"--prior-register={prior}"]) == 0
