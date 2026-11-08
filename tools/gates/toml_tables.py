# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Typed access to TOML documents and their arrays of tables."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import cast

_ObjectMap = dict[str, object]


def load(path: Path) -> dict[str, object]:
    """Read a TOML file.

    Args:
        path: The file to read.

    Returns:
        The parsed document.
    """
    return parse(path.read_text(encoding="utf-8"))


def parse(text: str) -> dict[str, object]:
    """Parse TOML text.

    Args:
        text: The TOML document.

    Returns:
        The parsed document.
    """
    return cast(_ObjectMap, tomllib.loads(text))


def tables(document: dict[str, object], key: str) -> list[dict[str, object]]:
    """Return the array of tables stored under ``key``.

    Args:
        document: A parsed TOML document.
        key: The array's key.

    Returns:
        The tables; an absent key yields an empty list.

    Raises:
        ValueError: When the value is not an array of tables.
    """
    value = document.get(key, [])
    if not isinstance(value, list):
        message = f"'{key}' is not an array of tables"
        raise ValueError(message)  # noqa: TRY004
    result: list[dict[str, object]] = []
    for item in cast("list[object]", value):
        if not isinstance(item, dict):
            message = f"'{key}' holds an element that is not a table"
            raise ValueError(message)  # noqa: TRY004
        result.append(cast(_ObjectMap, item))
    return result


def strings(document: dict[str, object], key: str) -> list[str]:
    """Return the array of strings stored under ``key``.

    Args:
        document: A parsed TOML document or table.
        key: The array's key.

    Returns:
        The strings; an absent key yields an empty list.

    Raises:
        ValueError: When the value is not an array of strings.
    """
    value = document.get(key, [])
    if not isinstance(value, list) or not all(
        isinstance(item, str) for item in cast("list[object]", value)
    ):
        message = f"'{key}' is not an array of strings"
        raise ValueError(message)
    return cast("list[str]", value)


def table(document: dict[str, object], key: str) -> dict[str, object]:
    """Return the table stored under ``key``.

    Args:
        document: A parsed TOML document.
        key: The table's key.

    Returns:
        The table; an absent key yields an empty table.

    Raises:
        ValueError: When the value is not a table.
    """
    value = document.get(key, {})
    if not isinstance(value, dict):
        message = f"'{key}' is not a table"
        raise ValueError(message)  # noqa: TRY004
    return cast(_ObjectMap, value)
