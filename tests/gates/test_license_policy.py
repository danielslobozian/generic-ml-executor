# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Licence policy: allowed families for runtime and development packages."""

from __future__ import annotations

import pytest

from tools.gates import license_policy as policy


@pytest.mark.parametrize(
    ("licence", "runtime", "development"),
    [
        ("MIT License", True, True),
        ("BSD-3-Clause", True, True),
        ("Apache Software License", True, True),
        ("Apache-2.0 OR BSD-2-Clause", True, True),
        ("Python Software Foundation License", True, True),
        ("ISC License (ISCL)", True, True),
        ("Mozilla Public License 2.0 (MPL 2.0)", False, True),
        ("GNU Lesser General Public License v3 (LGPLv3)", False, True),
        ("GNU General Public License v3 (GPLv3)", False, False),
        ("UNKNOWN", False, False),
    ],
)
def test_families(licence: str, runtime: bool, development: bool) -> None:
    """Each licence string is admitted exactly where the policy allows it."""
    assert policy.allowed(licence, policy.RUNTIME_ALLOWED) is runtime
    assert policy.allowed(licence, policy.DEV_ALLOWED) is development
