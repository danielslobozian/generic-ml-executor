# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Validation of file paths given to the gate tools on the command line.

A path must resolve inside the repository working directory or inside the
system temporary directory (where tests and temporary worktrees live); any
other path is refused, so a command-line argument cannot reach elsewhere.
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path


def safe_path(text: str) -> Path:
    """Return ``text`` as a path confined to the repository or the temporary directory.

    Args:
        text: The command-line argument.

    Returns:
        The resolved path.

    Raises:
        argparse.ArgumentTypeError: When the path resolves outside both roots.
    """
    resolved = Path(text).resolve()
    roots = (Path.cwd().resolve(), Path(tempfile.gettempdir()).resolve())
    if not any(resolved.is_relative_to(root) for root in roots):
        message = f"path outside the repository and the temporary directory: {text}"
        raise argparse.ArgumentTypeError(message)
    return resolved
