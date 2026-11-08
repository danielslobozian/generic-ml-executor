# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Typed reading of YAML files (workflows, pre-commit configuration).

PyYAML is present in the locked development environment (through
``detect-secrets`` and ``pre-commit``); no package is added for this reader.
It is imported dynamically so the strict type checker sees only ``object``.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from pathlib import Path
from typing import cast


def parse(text: str) -> object:
    """Parse YAML text with the safe loader.

    Args:
        text: The YAML document.

    Returns:
        The parsed document (mappings, sequences and scalars).
    """
    module = importlib.import_module("yaml")
    loader = cast("Callable[[str], object]", module.safe_load)
    return loader(text)


def load(path: Path) -> object:
    """Read and parse a YAML file.

    Args:
        path: The file to read.

    Returns:
        The parsed document.
    """
    return parse(path.read_text(encoding="utf-8"))


def mapping(value: object) -> dict[object, object]:
    """Return ``value`` as a mapping, or an empty mapping.

    Args:
        value: A parsed YAML node.

    Returns:
        The mapping, or ``{}`` when the node is not a mapping.
    """
    return cast("dict[object, object]", value) if isinstance(value, dict) else {}


def sequence(value: object) -> list[object]:
    """Return ``value`` as a sequence; a scalar becomes a one-element sequence.

    Args:
        value: A parsed YAML node.

    Returns:
        The elements; ``None`` yields an empty list.
    """
    if value is None:
        return []
    if isinstance(value, list):
        return cast("list[object]", value)
    return [value]
