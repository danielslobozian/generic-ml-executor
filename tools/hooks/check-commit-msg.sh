#!/bin/sh
# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
#
# Commit-message hook (pre-commit, commit-msg stage): rejects a message that
# carries an AI co-author or AI attribution line. The pattern is the committed
# file attribution-pattern.txt next to this script, which the pull-request scan
# (scan-pull-request.sh) reads too; matching is case-insensitive (POSIX ERE).
set -eu
pattern_file="$(dirname "$0")/attribution-pattern.txt"
pattern="$(cat "$pattern_file")"
message_file="${1:?usage: check-commit-msg.sh <commit-message-file>}"
if grep -Eiq -e "$pattern" "$message_file"; then
  echo "commit message rejected: it carries an AI co-author or AI attribution line" >&2
  exit 1
fi
