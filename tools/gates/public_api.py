# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Public-interface gate (TS-DOC-05; realization "Quality gates", `public_api`).

The public surface is every name in the root package's ``__all__``, with its
kind and signature as griffe reads them from ``src``. The gate fails when:

- the surface differs from the committed snapshot ``api/public-api.json``; or
- the snapshot changed against the comparison base, and the same change does
  not also modify ``docs/reference/public-api.md``, ``CHANGELOG.md`` and at
  least one file under ``tests/``.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import griffe

from tools.gates import comparison_base

SNAPSHOT = "api/public-api.json"
COUPLED = ("docs/reference/public-api.md", "CHANGELOG.md")
PACKAGE = "generic_ml_executor"


def _describe(obj: griffe.Object | griffe.Alias) -> dict[str, str]:
    target = obj.final_target if isinstance(obj, griffe.Alias) else obj
    entry = {"kind": target.kind.value, "path": target.path}
    if isinstance(target, griffe.Function):
        entry["signature"] = str(target.signature())
    return entry


def surface(search_path: Path) -> dict[str, dict[str, str]]:
    """Return the public surface of the package.

    Args:
        search_path: Directory holding the package (``src``).

    Returns:
        Each exported name mapped to its kind, path and, for functions, signature.
    """
    module = griffe.load(PACKAGE, search_paths=[str(search_path)])
    names = sorted(str(name) for name in module.exports or [])
    return {name: _describe(module.members[name]) for name in names if name in module.members}


def render(snapshot: dict[str, dict[str, str]]) -> str:
    """Render a snapshot as the committed JSON text.

    Args:
        snapshot: The public surface.

    Returns:
        Deterministic JSON with a final newline.
    """
    return json.dumps({"package": PACKAGE, "surface": snapshot}, indent=2, sort_keys=True) + "\n"


def coupling_problems(changed: set[str]) -> list[str]:
    """Return the missing companions of a snapshot change.

    Args:
        changed: Repository-relative paths the change modifies.

    Returns:
        One message per missing companion file or file group.
    """
    if SNAPSHOT not in changed:
        return []
    problems = [
        f"the public surface changed without changing {p}" for p in COUPLED if p not in changed
    ]
    if not any(path.startswith("tests/") for path in changed):
        problems.append("the public surface changed without changing a file under tests/")
    return problems


def _changed_files(base: str | None) -> set[str]:
    if base is None:
        listing = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True)
    else:
        listing = subprocess.run(
            ["git", "diff", "--name-only", base], capture_output=True, text=True, check=True
        )
    return set(listing.stdout.split())


def main(argv: list[str] | None = None) -> int:
    """Run the public-interface gate from the command line.

    Args:
        argv: Command-line arguments without the program name.

    Returns:
        The process exit status: 0 when the gate passes, 1 otherwise.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write the current surface")
    args = parser.parse_args(argv)
    current = render(surface(Path("src")))
    if args.write:
        Path(SNAPSHOT).write_text(current, encoding="utf-8")
        return 0
    problems: list[str] = []
    committed = Path(SNAPSHOT).read_text(encoding="utf-8") if Path(SNAPSHOT).is_file() else ""
    if committed != current:
        problems.append(f"the public surface differs from {Path(SNAPSHOT)}; update the snapshot")
    problems += coupling_problems(_changed_files(comparison_base.resolve()))
    for problem in problems:
        print(f"public_api: {problem}", file=sys.stderr)
    if not problems:
        print("public_api: passed")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
