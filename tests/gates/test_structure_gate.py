# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""TEST-python-TT01-01 (structure part): the structure gate on passing and failing fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.gates import structure_gate

ONE_CLASS = '"""Module."""\n\n\nclass Thing:\n    """Thing."""\n'


def _tree(
    tmp_path: Path, files: dict[str, str], reviews: str = "", exceptions: str = ""
) -> list[str]:
    package = tmp_path / "pkg"
    for name, text in files.items():
        (package / name).parent.mkdir(parents=True, exist_ok=True)
        (package / name).write_text(text, encoding="utf-8")
    (tmp_path / "reviews.toml").write_text(reviews, encoding="utf-8")
    (tmp_path / "exceptions.toml").write_text(exceptions, encoding="utf-8")
    return structure_gate.check(
        package, tmp_path, tmp_path / "reviews.toml", tmp_path / "exceptions.toml"
    )


def _long(lines: int) -> str:
    return ONE_CLASS + "\n" * (lines - ONE_CLASS.count("\n"))


def test_skeleton_fixture_passes(tmp_path: Path) -> None:
    """A package of empty __init__ modules and one-class modules passes."""
    init = '"""Package."""\n\nfrom importlib import metadata as _m\n\n__all__: list[str] = []\n'
    pep562 = (
        '"""Lazy."""\n\n\ndef __getattr__(name: str) -> object:\n    raise AttributeError(name)\n'
    )
    main_guard = ONE_CLASS + '\n\nif __name__ == "__main__":\n    Thing()\n'
    files = {"__init__.py": init, "sub/__init__.py": pep562, "a.py": ONE_CLASS, "b.py": main_guard}
    assert _tree(tmp_path, files) == []


@pytest.mark.parametrize(
    ("files", "expected"),
    [
        ({"a.py": ONE_CLASS + "\n\nclass Other:\n    pass\n"}, "pkg/a.py: defines 2 classes"),
        (
            {"a.py": ONE_CLASS.replace("    ", "    class Inner:\n        pass\n    ", 1)},
            "pkg/a.py: defines 2",
        ),
        (
            {"a.py": ONE_CLASS + "\n\ndef helper() -> None:\n    pass\n"},
            "pkg/a.py: module-level function 'helper'",
        ),
        ({"a.py": '"""No class."""\n'}, "pkg/a.py: defines 0 classes"),
        ({"__init__.py": ONE_CLASS}, "pkg/__init__.py: __init__ module defines a class"),
        ({"__init__.py": '"""P."""\n\n\ndef make() -> None:\n    pass\n'}, "function 'make'"),
        (
            {"__init__.py": '"""P."""\n\nfor _x in ():\n    pass\n'},
            "other than import or re-export",
        ),
        ({"a.py": _long(201)}, "pkg/a.py: 201 lines exceeds 200 without a responsibility review"),
        ({"a.py": _long(301)}, "pkg/a.py: 301 lines exceeds 300 without a reviewed exception"),
    ],
)
def test_failing_fixture_is_named(tmp_path: Path, files: dict[str, str], expected: str) -> None:
    """Each violating fixture fails with a message naming the module."""
    problems = _tree(tmp_path, files)
    assert any(expected in problem for problem in problems), problems


def test_records_admit_long_modules(tmp_path: Path) -> None:
    """A review admits 201-300 lines; only an exception admits more than 300."""
    review = (
        'review = [{module = "pkg/a.py", reviewer = "r", date = 2026-11-08, responsibility = "x"}]'
    )
    review += "\n"
    exception = (
        'exception = [{module = "pkg/b.py", reviewer = "r", date = 2026-11-08, reason = "why"}]\n'
    )
    files = {"a.py": _long(250), "b.py": _long(320)}
    assert _tree(tmp_path, files, review, exception) == []
    assert any(
        "pkg/b.py: 320" in p
        for p in _tree(tmp_path, {"b.py": _long(320)}, review.replace("a.py", "b.py"))
    )


def test_incomplete_record_entry_fails(tmp_path: Path) -> None:
    """A review entry lacking its responsibility statement is reported."""
    review = 'review = [{module = "pkg/a.py", reviewer = "r", date = 2026-11-08}]\n'
    problems = _tree(tmp_path, {"a.py": _long(250)}, review)
    assert any("lacks one of" in p for p in problems)
    assert any("pkg/a.py: 250" in p for p in problems)


def test_repository_package_passes() -> None:
    """The committed package passes the gate."""
    assert structure_gate.main([]) == 0
