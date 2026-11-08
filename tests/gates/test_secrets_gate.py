# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Committed-secret check: only audited false positives of the baseline pass."""

from __future__ import annotations

from tools.gates import secrets_gate


def _baseline(*items: tuple[str, str, bool | None]) -> dict[str, object]:
    results: dict[str, list[dict[str, object]]] = {}
    for path, digest, audited in items:
        entry: dict[str, object] = {
            "hashed_secret": digest,
            "line_number": 3,
            "type": "Secret Keyword",
        }
        if audited is not None:
            entry["is_secret"] = audited
        results.setdefault(path, []).append(entry)
    return {"results": results}


def test_audited_false_positive_passes() -> None:
    """A finding the committed baseline marks as not a secret passes."""
    committed = _baseline(("a.toml", "h1", False))
    assert secrets_gate.problems(committed, _baseline(("a.toml", "h1", None))) == []


def test_new_or_unaudited_finding_fails() -> None:
    """A new finding, or one not audited as a false positive, fails naming file and line."""
    committed = _baseline(("a.toml", "h1", False), ("b.py", "h2", None))
    rescanned = _baseline(("a.toml", "h1", None), ("b.py", "h2", None), ("c.py", "h3", None))
    assert secrets_gate.problems(committed, rescanned) == [
        "b.py:3: Secret Keyword is not an audited false positive",
        "c.py:3: Secret Keyword is not an audited false positive",
    ]
