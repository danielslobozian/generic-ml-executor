# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Line-coverage floor of TS-QA-10, computed from coverage.py's JSON totals.

The measured quantity is ``covered_lines / num_statements``; coverage.py's
combined line-and-branch percentage is not used. Zero measured statements
fail as a misconfiguration.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import cast

from tools.gates import repo_paths

FLOOR = 0.90


def evaluate(report: dict[str, object], floor: float = FLOOR) -> tuple[bool, str]:
    """Decide whether a coverage.py JSON report meets the line floor.

    Args:
        report: The parsed coverage.py JSON report.
        floor: The minimum line ratio.

    Returns:
        Whether the floor is met, and a message stating the measured ratio.
    """
    totals = report.get("totals")
    if not isinstance(totals, dict):
        return False, "coverage report has no totals"
    numbers = cast("dict[str, object]", totals)
    statements = numbers.get("num_statements")
    covered = numbers.get("covered_lines")
    if not isinstance(statements, int) or not isinstance(covered, int):
        return False, "coverage totals lack num_statements or covered_lines"
    if statements == 0:
        return False, "zero measured statements: coverage is misconfigured"
    ratio = covered / statements
    verdict = "meets" if ratio >= floor else "is below"
    message = f"line coverage {covered}/{statements} = {ratio:.4f} {verdict} the floor {floor:.2f}"
    return ratio >= floor, message


def main(argv: list[str] | None = None) -> int:
    """Run the line-coverage check from the command line.

    Args:
        argv: Command-line arguments without the program name.

    Returns:
        The process exit status: 0 when the floor is met, 1 otherwise.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "report", type=repo_paths.safe_path, nargs="?", default=Path("coverage.json")
    )
    args = parser.parse_args(argv)
    report = cast("dict[str, object]", json.loads(args.report.read_text(encoding="utf-8")))
    passed, message = evaluate(report)
    print(f"coverage: {message}", file=sys.stdout if passed else sys.stderr)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
