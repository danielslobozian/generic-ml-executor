# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The single entry point of the quality gates (TS-QA-12).

Run through uv so every tool comes from ``uv.lock``, identically locally and in CI::

    uv run --frozen nox -s green

Every session runs in the locked project environment (``python=False``).
``green`` reads the gate register ``tools/gates/gate-set.toml``, prints the
active and pending sessions and runs every active one; CI runs exactly that.
"""

from __future__ import annotations

import json
import platform
import sys
import tomllib
from collections.abc import Callable
from pathlib import Path

import nox

nox.options.default_venv_backend = "none"
nox.options.error_on_missing_interpreters = True

RESULTS = Path("results")
REGISTER = Path("tools/gates/gate-set.toml")
CODE = ("src", "tests", "tools", "noxfile.py")
GATES: dict[str, Callable[[nox.Session], None]] = {}


def gate(function: Callable[[nox.Session], None]) -> Callable[[nox.Session], None]:
    """Register a gate session so that ``green`` can run it.

    Args:
        function: The session body.

    Returns:
        The same function, registered under its name.
    """
    GATES[function.__name__] = function
    return function


def _python_tag() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}"


def _cell_name() -> str:
    system = {"linux": "linux", "darwin": "macos", "win32": "windows"}.get(
        sys.platform, sys.platform
    )
    return f"{system}-{_python_tag()}"


def _pytest(session: nox.Session, *extra: str) -> None:
    session.run("pytest", "-p", "tools.gates.cell_report", *extra, *session.posargs)


@nox.session(python=False)
@gate
def lint(session: nox.Session) -> None:
    """Ruff lint and format check."""
    session.run("ruff", "check", ".")
    session.run("ruff", "format", "--check", ".")


@nox.session(python=False)
@gate
def complexity(session: nox.Session) -> None:
    """Cognitive complexity of at most 15 over all code."""
    session.run("complexipy", "--max-complexity-allowed", "15", "--failed", *CODE)


@nox.session(python=False)
@gate
def structure(session: nox.Session) -> None:
    """One class per production module and the module-length rule."""
    session.run("python", "-m", "tools.gates.structure_gate")


@nox.session(python=False)
@gate
def imports(session: nox.Session) -> None:
    """The Import Linter contracts of ``.importlinter``."""
    session.run("lint-imports", "--no-cache")


@nox.session(python=False)
@gate
def typecheck(session: nox.Session) -> None:
    """Pyright strict over the configured paths, zero errors."""
    session.run("pyright", "--pythonversion", _python_tag())


@nox.session(python=False)
@gate
def tests(session: nox.Session) -> None:
    """The test suite on the running interpreter."""
    _pytest(session, f"--cell-report-out={RESULTS / 'tests.json'}")


def _measure_coverage(session: nox.Session) -> None:
    _pytest(
        session,
        "--cov=generic_ml_executor",
        "--cov-branch",
        "--cov-report=json:coverage.json",
        "--cov-report=xml:coverage.xml",
        "--cov-report=term",
    )


@nox.session(python=False)
@gate
def coverage(session: nox.Session) -> None:
    """Line coverage floor of 90 % of the package, branch coverage measured."""
    _measure_coverage(session)
    session.run("python", "-m", "tools.gates.line_coverage", "coverage.json")


@nox.session(python=False)
@gate
def security(session: nox.Session) -> None:
    """Known vulnerabilities in the locked environments and committed secrets."""
    RESULTS.mkdir(exist_ok=True)
    requirements = RESULTS / "requirements-locked.txt"
    session.run(
        "uv", "export", "--frozen", "--all-groups", "--no-emit-project",
        "--format", "requirements-txt", "-o", str(requirements),
    )  # fmt: skip
    session.run(
        "pip-audit", "--strict", "--disable-pip", "--require-hashes", "-r", str(requirements)
    )
    session.run("python", "-m", "tools.gates.secrets_gate")


@nox.session(python=False)
@gate
def licenses(session: nox.Session) -> None:
    """Licences of the runtime and development environments."""
    session.run("python", "-m", "tools.gates.license_policy")


@nox.session(python=False)
@gate
def workflows(session: nox.Session) -> None:
    """Workflow audit: permissions, pinned actions, untrusted input."""
    session.run("zizmor", "--offline", "--persona", "pedantic", ".github/workflows")


@nox.session(python=False)
@gate
def public_api(session: nox.Session) -> None:
    """Public surface snapshot and its documentation-and-tests coupling."""
    session.run("python", "-m", "tools.gates.public_api")


@nox.session(python=False)
@gate
def gate_set(session: nox.Session) -> None:
    """The gate register against the sessions of this file."""
    session.run("python", "-m", "tools.gates.gate_set")


@nox.session(python=False)
@gate
def acceptance_inventory(session: nox.Session) -> None:
    """The acceptance inventory against the required-case set and the marked tests."""
    RESULTS.mkdir(exist_ok=True)
    markers = RESULTS / "case-markers.json"
    session.run(
        "pytest", "--collect-only", "-q", "-p", "tools.gates.case_markers",
        f"--case-markers-out={markers}",
    )  # fmt: skip
    session.run("python", "-m", "tools.gates.acceptance_inventory", f"--markers={markers}")


@nox.session(python=False)
@gate
def sonar(session: nox.Session) -> None:
    """SonarQube Cloud analysis with its quality gate (needs ``SONAR_TOKEN``)."""
    _measure_coverage(session)
    session.run("python", "-m", "tools.gates.sonar_gate")


@nox.session(python=False)
@gate
def codacy(session: nox.Session) -> None:
    """Codacy CLI analysis: no significant new finding against the comparison base."""
    session.run("python", "-m", "tools.gates.codacy_gate")


@nox.session(python=False)
@gate
def evidence(session: nox.Session) -> None:
    """Capability-evidence record check; pending until TU-02 delivers it."""
    session.error("the evidence gate is pending until TU-02 delivers its check and record")


@nox.session(python=False)
@gate
def docs(session: nox.Session) -> None:
    """Documentation-set gates; pending until TU-19 delivers them."""
    session.error("the docs gate is pending until TU-19 delivers the documentation set")


def _register() -> list[tuple[str, str]]:
    rows = tomllib.loads(REGISTER.read_text(encoding="utf-8")).get("gate", [])
    return [(str(row["session"]), str(row["state"])) for row in rows]


def _write_cell_report(sessions: list[str], outcomes: dict[str, str]) -> None:
    tests_path = RESULTS / "tests.json"
    cases: object = (
        json.loads(tests_path.read_text(encoding="utf-8")) if tests_path.is_file() else {}
    )
    report = {
        "cell": _cell_name(),
        "os": platform.system(),
        "python": platform.python_version(),
        "gate_sessions_run": sessions,
        "gate_session_outcomes": outcomes,
        "cases": cases,
    }
    target = RESULTS / f"{_cell_name()}.json"
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


@nox.session(python=False)
def green(session: nox.Session) -> None:
    """Every active gate of the register, in one invocation."""
    rows = _register()
    active = [name for name, state in rows if state == "active"]
    pending = [name for name, state in rows if state == "pending"]
    session.log(f"active gate sessions: {' '.join(active)}")
    session.log(f"pending gate sessions: {' '.join(pending) or '(none)'}")
    missing = [name for name in active if name not in GATES]
    if missing:
        session.error(f"active sessions without a definition: {' '.join(missing)}")
    RESULTS.mkdir(exist_ok=True)
    outcomes = {name: _run_gate(session, name) for name in active}
    _write_cell_report(active, outcomes)
    failed = [name for name, outcome in outcomes.items() if outcome != "passed"]
    if failed:
        session.error(f"failed gate sessions: {' '.join(failed)}")
    session.log(f"every active gate session passed: {' '.join(active)}")


def _run_gate(session: nox.Session, name: str) -> str:
    session.log(f"--- gate session: {name}")
    try:
        GATES[name](session)
    except Exception as failure:  # noqa: BLE001 - every gate runs; failures are reported together
        session.warn(f"gate session {name} failed: {failure}")
        return "failed"
    return "passed"
