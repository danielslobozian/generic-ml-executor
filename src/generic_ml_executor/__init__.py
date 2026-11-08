# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""generic-ml-executor: drive ML coding clients and model APIs from Python."""

from importlib.metadata import version as _distribution_version

__all__: list[str] = []
__version__: str = _distribution_version("generic-ml-executor")
