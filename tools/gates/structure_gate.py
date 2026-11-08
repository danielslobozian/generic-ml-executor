# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Structure gate: one class per production module and the module-length rule.

Rules (realization "Quality gates", `structure`):

1. Every production module except ``__init__.py`` defines exactly one class
   (nested classes count). A module-level ``def`` fails, except inside an
   ``if __name__ == "__main__":`` block.
2. ``__init__.py`` defines no class and only imports or re-exports; the only
   functions it may define are the PEP 562 ``__getattr__`` and ``__dir__``.
3. Module length in physical lines: up to 200 passes; 201-300 passes only with
   an entry in the review record; above 300 fails unless the exception record
   holds a reviewed exception.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

from tools.gates import repo_paths, toml_tables

REVIEW_LIMIT = 200
EXCEPTION_LIMIT = 300
PEP562_FUNCTIONS = frozenset({"__getattr__", "__dir__"})
INIT_ALLOWED = (ast.Import, ast.ImportFrom, ast.Assign, ast.AnnAssign, ast.Expr)
REVIEW_FIELDS = ("module", "reviewer", "date", "responsibility")
EXCEPTION_FIELDS = ("module", "reviewer", "date", "reason")


def _is_main_guard(node: ast.stmt) -> bool:
    if not isinstance(node, ast.If) or not isinstance(node.test, ast.Compare):
        return False
    left = node.test.left
    return isinstance(left, ast.Name) and left.id == "__name__"


def _count_classes(tree: ast.Module) -> int:
    return sum(isinstance(node, ast.ClassDef) for node in ast.walk(tree))


def _module_problems(rel: str, tree: ast.Module) -> list[str]:
    problems: list[str] = []
    classes = _count_classes(tree)
    if classes != 1:
        problems.append(
            f"{rel}: defines {classes} classes; a production module defines exactly one"
        )
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            problems.append(f"{rel}: module-level function '{node.name}' outside a class")
    return problems


def _init_problems(rel: str, tree: ast.Module) -> list[str]:
    problems: list[str] = []
    if _count_classes(tree):
        problems.append(f"{rel}: __init__ module defines a class")
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if node.name not in PEP562_FUNCTIONS:
                problems.append(f"{rel}: __init__ module defines function '{node.name}'")
        elif not isinstance(node, INIT_ALLOWED) and not _is_main_guard(node):
            problems.append(
                f"{rel}: __init__ module holds a statement other than import or re-export"
            )
    return problems


def _load_records(path: Path, key: str, fields: tuple[str, ...]) -> tuple[set[str], list[str]]:
    if not path.is_file():
        return set(), [f"{path}: record file missing"]
    try:
        entries = toml_tables.tables(toml_tables.load(path), key)
    except ValueError as error:
        return set(), [f"{path}: {error}"]
    modules: set[str] = set()
    problems: list[str] = []
    for entry in entries:
        if any(not entry.get(field) for field in fields):
            problems.append(f"{path}: an entry lacks one of {', '.join(fields)}")
        else:
            modules.add(str(entry["module"]))
    return modules, problems


def _length_problem(rel: str, lines: int, reviewed: set[str], excepted: set[str]) -> str | None:
    if lines > EXCEPTION_LIMIT and rel not in excepted:
        return f"{rel}: {lines} lines exceeds {EXCEPTION_LIMIT} without a reviewed exception"
    if REVIEW_LIMIT < lines <= EXCEPTION_LIMIT and rel not in reviewed and rel not in excepted:
        return f"{rel}: {lines} lines exceeds {REVIEW_LIMIT} without a responsibility review"
    return None


def check(package: Path, base: Path, reviews: Path, exceptions: Path) -> list[str]:
    """Return every structure violation under ``package``.

    Args:
        package: Root directory of the production package.
        base: Directory against which module paths are reported and recorded.
        reviews: The module-size review record.
        exceptions: The module-size exception record.

    Returns:
        One message per violation, each naming the module.
    """
    reviewed, problems = _load_records(reviews, "review", REVIEW_FIELDS)
    excepted, more = _load_records(exceptions, "exception", EXCEPTION_FIELDS)
    problems.extend(more)
    for path in sorted(package.rglob("*.py")):
        rel = path.relative_to(base).as_posix()
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=rel)
        if path.name == "__init__.py":
            problems.extend(_init_problems(rel, tree))
        else:
            problems.extend(_module_problems(rel, tree))
        length = _length_problem(rel, len(text.splitlines()), reviewed, excepted)
        if length:
            problems.append(length)
    return problems


def main(argv: list[str] | None = None) -> int:
    """Run the structure gate from the command line.

    Args:
        argv: Command-line arguments without the program name.

    Returns:
        The process exit status: 0 when the tree passes, 1 otherwise.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--package", type=repo_paths.safe_path, default=Path("src/generic_ml_executor")
    )
    parser.add_argument("--base", type=repo_paths.safe_path, default=Path())
    parser.add_argument(
        "--reviews", type=repo_paths.safe_path, default=Path("quality/module-size-reviews.toml")
    )
    parser.add_argument(
        "--exceptions",
        type=repo_paths.safe_path,
        default=Path("quality/module-size-exceptions.toml"),
    )
    args = parser.parse_args(argv)
    problems = check(args.package, args.base, args.reviews, args.exceptions)
    for problem in problems:
        print(f"structure: {problem}", file=sys.stderr)
    if not problems:
        print("structure: passed")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
