# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Committed-secret check (realization "Quality gates", `security`).

Re-scans the tracked files with ``detect-secrets scan --baseline`` on a copy of
``.secrets.baseline`` and fails on any finding that the committed baseline does
not hold as an audited false positive (``is_secret: false``), naming the file
and line, never the value.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import cast

BASELINE = Path(".secrets.baseline")


def _findings(baseline: dict[str, object]) -> dict[tuple[str, str], dict[str, object]]:
    results = cast("dict[str, list[dict[str, object]]]", baseline.get("results", {}))
    return {
        (path, str(item["hashed_secret"])): item
        for path, items in results.items()
        for item in items
    }


def problems(committed: dict[str, object], rescanned: dict[str, object]) -> list[str]:
    """Return the findings that are not audited false positives of the committed baseline.

    Args:
        committed: The committed baseline.
        rescanned: The baseline after a fresh scan.

    Returns:
        One message per unaudited finding, naming the file, line and type.
    """
    audited = {k for k, item in _findings(committed).items() if item.get("is_secret") is False}
    return [
        f"{path}:{item.get('line_number')}: {item.get('type')} is not an audited false positive"
        for (path, digest), item in sorted(_findings(rescanned).items())
        if (path, digest) not in audited
    ]


def main(argv: list[str] | None = None) -> int:
    """Run the committed-secret check from the command line.

    Args:
        argv: Command-line arguments without the program name.

    Returns:
        The process exit status: 0 when no new secret exists, 1 otherwise.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=BASELINE)
    args = parser.parse_args(argv)
    committed = cast("dict[str, object]", json.loads(args.baseline.read_text(encoding="utf-8")))
    with tempfile.TemporaryDirectory() as work:
        copy = Path(work) / "baseline.json"
        shutil.copyfile(args.baseline, copy)
        subprocess.run(["detect-secrets", "scan", "--baseline", str(copy)], check=True)
        rescanned = cast("dict[str, object]", json.loads(copy.read_text(encoding="utf-8")))
    found = problems(committed, rescanned)
    for problem in found:
        print(f"security: {problem}", file=sys.stderr)
    print(f"security: {len(_findings(rescanned))} detect-secrets findings, {len(found)} unaudited")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
