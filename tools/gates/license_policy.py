# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Licence gate (TS-QA-14 licence review; realization "Runtime and dependencies").

Runtime dependencies must be MIT, BSD-2/3-Clause, Apache-2.0, PSF-2.0 or ISC.
Development-only tools may also be MPL-2.0 or LGPL. The runtime set is the
locked runtime environment (``uv export --no-dev``); every other installed
distribution of the locked development environment is a development tool.
Licences are read with ``pip-licenses --from=mixed``; a licence that maps to
no allowed family fails, naming the package.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from typing import cast

RUNTIME_ALLOWED = frozenset({"MIT", "BSD", "Apache-2.0", "PSF-2.0", "ISC"})
DEV_ALLOWED = RUNTIME_ALLOWED | {"MPL-2.0", "LGPL"}
FAMILIES = (
    (re.compile(r"\bLGPL|Lesser General Public", re.IGNORECASE), "LGPL"),
    (re.compile(r"\bA?GPL|General Public License", re.IGNORECASE), "GPL"),
    (re.compile(r"\bMIT\b|MIT-CMU|Expat", re.IGNORECASE), "MIT"),
    (re.compile(r"\bBSD\b|0BSD", re.IGNORECASE), "BSD"),
    (re.compile(r"Apache", re.IGNORECASE), "Apache-2.0"),
    (re.compile(r"\bPSF\b|Python Software Foundation", re.IGNORECASE), "PSF-2.0"),
    (re.compile(r"\bISC\b", re.IGNORECASE), "ISC"),
    (re.compile(r"\bMPL\b|Mozilla Public", re.IGNORECASE), "MPL-2.0"),
)
SPLIT = re.compile(r" (?:OR|AND|/) |;", re.IGNORECASE)


def families(licence: str) -> set[str]:
    """Return the licence families a licence string names.

    Args:
        licence: A licence expression, name or classifier list.

    Returns:
        The families found; empty for an unknown licence. A ``GPL`` family
        appears only when no ``LGPL`` reading covers the same part.
    """
    found: set[str] = set()
    for part in SPLIT.split(licence):
        for pattern, family in FAMILIES:
            if pattern.search(part):
                found.add(family)
                break
    return found


def allowed(licence: str, permitted: frozenset[str]) -> bool:
    """Return whether a licence string is acceptable.

    Args:
        licence: The licence string.
        permitted: The permitted families.

    Returns:
        True when at least one named family is permitted (a choice of licences).
    """
    return bool(families(licence) & permitted)


def _runtime_names() -> set[str]:
    export = subprocess.run(
        [
            "uv",
            "export",
            "--frozen",
            "--no-dev",
            "--no-emit-project",
            "--no-hashes",
            "--format",
            "requirements-txt",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    names = {re.split(r"[=<>!~;\s\[]", line, maxsplit=1)[0] for line in export.splitlines()}
    return {_normalise(name) for name in names if name and not name.startswith(("#", "-"))}


def _normalise(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def main(argv: list[str] | None = None) -> int:
    """Run the licence gate from the command line.

    Args:
        argv: Command-line arguments without the program name.

    Returns:
        The process exit status: 0 when every licence is allowed, 1 otherwise.
    """
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    listing = subprocess.run(
        ["pip-licenses", "--from=mixed", "--format=json"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    runtime = _runtime_names()
    problems: list[str] = []
    rows = cast("list[dict[str, str]]", json.loads(listing))
    for row in rows:
        name, licence = row["Name"], row["License"]
        is_runtime = _normalise(name) in runtime
        if not allowed(licence, RUNTIME_ALLOWED if is_runtime else DEV_ALLOWED):
            kind = "runtime" if is_runtime else "development"
            problems.append(f"{kind} package {name} has a disallowed or unknown licence: {licence}")
    for problem in problems:
        print(f"licenses: {problem}", file=sys.stderr)
    print(f"licenses: {len(rows)} packages checked, {len(runtime)} runtime")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
