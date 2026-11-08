#!/bin/sh
# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
#
# Branch-name guard (pre-commit stage): changes reach main only through pull
# requests, so no commit is made on main itself.
set -eu
branch="$(git rev-parse --abbrev-ref HEAD)"
if [ "$branch" = "main" ]; then
  echo "commit refused: work on a branch and open a pull request into main" >&2
  exit 1
fi
