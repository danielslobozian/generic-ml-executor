# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The package skeleton: version from the installed metadata, empty surface, inline types."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

import generic_ml_executor


def test_version_comes_from_the_installed_metadata() -> None:
    """``__version__`` equals the single version source ``VERSION``."""
    assert generic_ml_executor.__version__ == Path("VERSION").read_text(encoding="utf-8").strip()


def test_public_surface_is_empty_at_the_skeleton() -> None:
    """The skeleton exports no public name yet."""
    assert generic_ml_executor.__all__ == []


def test_inline_type_marker_is_present() -> None:
    """The package carries the PEP 561 marker ``py.typed``."""
    assert resources.files("generic_ml_executor").joinpath("py.typed").is_file()
