# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Gate register check (realization "Quality gates", `gate_set`).

The register ``tools/gates/gate-set.toml`` holds one ``[[gate]]`` row per gate
session: ``session``, ``owner`` (TU) and ``state`` (``active`` or ``pending``).
The check fails when:

- the register and the gate sessions of ``noxfile.py`` differ in either
  direction (``green``, ``acceptance`` and ``installed`` are not gate sessions);
- a session other than ``evidence`` (owner TU-02) or ``docs`` (owner TU-19) is
  ``pending``, or either of them has another owner;
- a session ``active`` at the comparison base is ``pending`` in the change.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

from tools.gates import comparison_base, repo_paths, toml_tables

REGISTER = "tools/gates/gate-set.toml"
NOT_GATES = frozenset({"green", "acceptance", "installed"})
PENDING_OWNERS = {"evidence": "TU-02", "docs": "TU-19"}
STATES = frozenset({"active", "pending"})


def nox_sessions(noxfile_text: str) -> set[str]:
    """Return the names of the sessions a nox file defines.

    Args:
        noxfile_text: The nox file's source.

    Returns:
        Every session name, including the non-gate sessions.
    """
    names: set[str] = set()
    for node in ast.walk(ast.parse(noxfile_text)):
        if isinstance(node, ast.FunctionDef):
            for decorator in node.decorator_list:
                name = _session_name(decorator, node.name)
                if name:
                    names.add(name)
    return names


def _session_name(decorator: ast.expr, function: str) -> str | None:
    target = decorator.func if isinstance(decorator, ast.Call) else decorator
    if not (isinstance(target, ast.Attribute) and target.attr == "session"):
        return None
    if isinstance(decorator, ast.Call):
        for keyword in decorator.keywords:
            if keyword.arg == "name" and isinstance(keyword.value, ast.Constant):
                return str(keyword.value.value)
    return function


def register_rows(text: str) -> dict[str, tuple[str, str]]:
    """Parse a register.

    Args:
        text: The register's TOML text.

    Returns:
        Each session mapped to its owner and state.
    """
    rows: dict[str, tuple[str, str]] = {}
    for row in toml_tables.tables(toml_tables.parse(text), "gate"):
        rows[str(row.get("session", ""))] = (str(row.get("owner", "")), str(row.get("state", "")))
    return rows


def _row_problems(rows: dict[str, tuple[str, str]]) -> list[str]:
    problems: list[str] = []
    for session, (owner, state) in sorted(rows.items()):
        if state not in STATES:
            problems.append(f"session '{session}' has state '{state}'")
        if session in PENDING_OWNERS and owner != PENDING_OWNERS[session]:
            problems.append(
                f"session '{session}' has owner '{owner}', not {PENDING_OWNERS[session]}"
            )
        if state == "pending" and session not in PENDING_OWNERS:
            problems.append(f"session '{session}' is pending; only evidence and docs may be")
    return problems


def check(noxfile_text: str, register_text: str, prior_text: str | None) -> list[str]:
    """Return every register violation.

    Args:
        noxfile_text: The nox file's source.
        register_text: The register in the change.
        prior_text: The register at the comparison base, or ``None``.

    Returns:
        One message per violation, each naming the session.
    """
    rows = register_rows(register_text)
    gates = nox_sessions(noxfile_text) - NOT_GATES
    problems = [
        f"session '{s}' is in noxfile.py but not in the register" for s in sorted(gates - set(rows))
    ]
    problems += [
        f"session '{s}' is in the register but not in noxfile.py" for s in sorted(set(rows) - gates)
    ]
    problems += _row_problems(rows)
    if prior_text is not None:
        for session, (_, state) in sorted(register_rows(prior_text).items()):
            if state == "active" and rows.get(session, ("", ""))[1] != "active":
                problems.append(
                    f"session '{session}' was active at the comparison base and is not now"
                )
    return problems


def main(argv: list[str] | None = None) -> int:
    """Run the register check from the command line.

    Args:
        argv: Command-line arguments without the program name.

    Returns:
        The process exit status: 0 when the register passes, 1 otherwise.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--noxfile", type=repo_paths.safe_path, default=Path("noxfile.py"))
    parser.add_argument("--register", type=repo_paths.safe_path, default=Path(REGISTER))
    parser.add_argument(
        "--prior-register", type=repo_paths.safe_path, help="register at the comparison base"
    )
    args = parser.parse_args(argv)
    if args.prior_register is not None:
        prior = args.prior_register.read_text(encoding="utf-8")
    else:
        base = comparison_base.resolve()
        prior = comparison_base.show(base, REGISTER) if base else None
    problems = check(
        args.noxfile.read_text(encoding="utf-8"), args.register.read_text(encoding="utf-8"), prior
    )
    for problem in problems:
        print(f"gate_set: {problem}", file=sys.stderr)
    if not problems:
        print("gate_set: passed")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
