# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""TEST-python-TT01-05: required-check and hook definitions (realization RV-19(a)), every cell."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.gates import repository_rule as rule

CI = Path(".github/workflows/ci.yml")
HYGIENE = Path(".github/workflows/pr-hygiene.yml")
PRECOMMIT = Path(".pre-commit-config.yaml")


def test_skeleton_files_pass() -> None:
    """The committed workflows, scripts and pre-commit configuration pass every check."""
    assert rule.ci_problems(CI) == []
    assert rule.hygiene_problems(HYGIENE) == []
    assert rule.pattern_problems(rule.HOOKS) == []
    assert rule.precommit_problems(PRECOMMIT) == []


def _defect(tmp_path: Path, source: Path, old: str, new: str) -> Path:
    text = source.read_text(encoding="utf-8")
    assert old in text, old
    copy = tmp_path / source.name
    copy.write_text(text.replace(old, new, 1), encoding="utf-8")
    return copy


SECOND_JOB = "\n  other:\n    name: other\n    runs-on: ubuntu-latest\n    steps: []\n"
SCAN_STEP = "        run: sh tools/hooks/scan-pull-request.sh\n"
RUNS_ON = "    runs-on: ubuntu-latest\n"
Check = Callable[[Path], list[str]]
DEFECTS: list[tuple[Path, Check, str, str, str]] = [
    (HYGIENE, rule.hygiene_problems, "    name: no AI attribution\n", "", "display name"),
    (HYGIENE, rule.hygiene_problems, SCAN_STEP, SCAN_STEP + SECOND_JOB, "exactly one job"),
    (HYGIENE, rule.hygiene_problems, ", synchronize]", "]", "trigger"),
    (HYGIENE, rule.hygiene_problems, ", synchronize]", ", synchronize, closed]", "trigger"),
    (
        HYGIENE,
        rule.hygiene_problems,
        "  contents: read\n",
        "  contents: read\n  pull-requests: read\n",
        "exactly contents: read",
    ),
    (
        HYGIENE,
        rule.hygiene_problems,
        RUNS_ON,
        RUNS_ON + "    permissions:\n      contents: write\n",
        "beyond contents: read",
    ),
    (PRECOMMIT, rule.precommit_problems, "[commit-msg]", "[pre-commit]", "commit-msg"),
    (CI, rule.ci_problems, "    needs: [cell]\n", "", "does not need every matrix job"),
    (CI, rule.ci_problems, "    name: ci\n", "    name: rollup\n", "display name 'ci'"),
]


@pytest.mark.parametrize("defect", DEFECTS)
def test_defect_fixture_fails(tmp_path: Path, defect: tuple[Path, Check, str, str, str]) -> None:
    """Each one-defect copy fails, naming the file and the item."""
    source, check, old, new, expected = defect
    problems = check(_defect(tmp_path, source, old, new))
    assert any(expected in p and source.name in p for p in problems), problems


def _read_other_file(text: str) -> str:
    return text.replace("attribution-pattern.txt", "other.txt")


def _hold_own_pattern(text: str) -> str:
    return text + "\n# own pattern: co-" + "authored\n"


@pytest.mark.parametrize(
    ("script", "change"),
    [("scan-pull-request.sh", _read_other_file), ("check-commit-msg.sh", _hold_own_pattern)],
)
def test_pattern_defects_fail(tmp_path: Path, script: str, change: Callable[[str], str]) -> None:
    """A script that stops reading the shared file, or holds its own pattern, fails."""
    hooks = tmp_path / "hooks"
    shutil.copytree(rule.HOOKS, hooks)
    target = hooks / script
    target.write_text(change(target.read_text(encoding="utf-8")), encoding="utf-8")
    problems = rule.pattern_problems(hooks)
    assert any(script in p for p in problems), problems


def test_missing_pattern_file_fails(tmp_path: Path) -> None:
    """Without the shared pattern file both scripts would have nothing to compare."""
    hooks = tmp_path / "hooks"
    shutil.copytree(rule.HOOKS, hooks)
    (hooks / rule.PATTERN_FILE).unlink()
    assert any("pattern file is missing" in p for p in rule.pattern_problems(hooks))
