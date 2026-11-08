# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The Git commit a change is compared with.

- On a pull request in CI: the merge base of ``HEAD`` and the pull request's base branch.
- On a push to ``main`` in CI: the first parent of ``HEAD``.
- Locally: the merge base of ``HEAD`` and ``origin/main``.

``None`` means there is no prior state (the first commit of the repository).
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import cast


def _git(*args: str) -> str | None:
    result = subprocess.run(["git", *args], capture_output=True, text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def _pull_request_base_sha() -> str | None:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        return None
    event = cast("dict[str, object]", json.loads(Path(event_path).read_text(encoding="utf-8")))
    pull_request = event.get("pull_request")
    if not isinstance(pull_request, dict):
        return None
    base = cast("dict[str, object]", pull_request).get("base")
    if not isinstance(base, dict):
        return None
    sha = cast("dict[str, object]", base).get("sha")
    return sha if isinstance(sha, str) else None


def resolve() -> str | None:
    """Return the comparison base commit for the current change.

    Returns:
        A commit identifier, or ``None`` when the change has no prior state.
    """
    event = os.environ.get("GITHUB_EVENT_NAME")
    if event == "pull_request":
        base_sha = _pull_request_base_sha()
        return _git("merge-base", "HEAD", base_sha) if base_sha else None
    if event == "push":
        return _git("rev-parse", "--verify", "--quiet", "HEAD^")
    return _git("merge-base", "HEAD", "origin/main")


def show(commit: str, path: str) -> str | None:
    """Return a file's content at a commit.

    Args:
        commit: The commit.
        path: The repository-relative path.

    Returns:
        The file's text, or ``None`` when the file does not exist at that commit.
    """
    return _git("show", f"{commit}:{path}")
