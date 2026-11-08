#!/bin/sh
# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
#
# Pull-request scan of the `no AI attribution` check: fails when the pull
# request's title (PR_TITLE), its body (PR_BODY) or the message of any commit
# in BASE_SHA..HEAD_SHA, read with Git from the checked-out history, matches the
# committed attribution pattern (attribution-pattern.txt, shared with the
# commit-message hook), case-insensitively. Title and body arrive only through
# environment variables.
set -eu
pattern="$(cat "$(dirname "$0")/attribution-pattern.txt")"
: "${BASE_SHA:?BASE_SHA is required}"
: "${HEAD_SHA:?HEAD_SHA is required}"
status=0
if printf '%s\n' "${PR_TITLE:-}" | grep -Eiq -e "$pattern"; then
  echo "pull-request title carries an AI co-author or AI attribution line" >&2
  status=1
fi
if printf '%s\n' "${PR_BODY:-}" | grep -Eiq -e "$pattern"; then
  echo "pull-request body carries an AI co-author or AI attribution line" >&2
  status=1
fi
for commit in $(git rev-list "$BASE_SHA..$HEAD_SHA"); do
  if git log -1 --format=%B "$commit" | grep -Eiq -e "$pattern"; then
    echo "commit $commit carries an AI co-author or AI attribution line" >&2
    status=1
  fi
done
if [ "$status" -eq 0 ]; then
  echo "no AI attribution found in the title, the body or $(git rev-list --count "$BASE_SHA..$HEAD_SHA") commit(s)"
fi
exit "$status"
