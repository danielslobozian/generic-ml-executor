# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Compare two Codacy CLI SARIF reports and fail on significant new findings.

A finding is identified by tool, rule, path and its SARIF
``partialFingerprints`` (else ``fingerprints``, else the normalised text of
the flagged line), counted as a multiset. The change fails when it adds a
finding of severity High or Critical in any category, or of severity Medium or
above in the Security category.

Severity is read from the result's or the rule's ``properties.severity``
(Codacy's ``Info``/``Minor``/``Medium``/``High``/``Critical`` or ``Warning``/
``Error`` names); when absent it is derived from the SARIF ``level``:
``error`` is High, ``warning`` Medium, anything else Low. A finding is in the
Security category when its properties name that category or tag, when its rule
identifier has a ``security`` segment, or when the tool is a vulnerability
scanner (Trivy).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from typing import cast

from tools.gates import repo_paths

_ObjectMap = dict[str, object]

RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}
SEVERITY_NAMES = {
    "info": "low",
    "minor": "low",
    "low": "low",
    "warning": "medium",
    "medium": "medium",
    "major": "high",
    "error": "high",
    "high": "high",
    "critical": "critical",
}
LEVELS = {"error": "high", "warning": "medium"}
SECURITY_TOOLS = frozenset({"trivy"})


@dataclass(frozen=True)
class Finding:
    """One SARIF result reduced to its identity and significance."""

    tool: str
    rule: str
    path: str
    fingerprint: str
    severity: str
    security: bool

    def key(self) -> tuple[str, str, str, str]:
        """Return the identity used for the multiset comparison.

        Returns:
            Tool, rule, path and fingerprint.
        """
        return (self.tool, self.rule, self.path, self.fingerprint)

    def significant(self) -> bool:
        """Return whether a new occurrence of this finding fails the gate.

        Returns:
            True for High or Critical, or Medium and above in Security.
        """
        rank = RANK[self.severity]
        return rank >= RANK["high"] or (self.security and rank >= RANK["medium"])


def _dict(value: object) -> dict[str, object]:
    return cast(_ObjectMap, value) if isinstance(value, dict) else {}


def _list(value: object) -> list[object]:
    return cast("list[object]", value) if isinstance(value, list) else []


def _fingerprint(result: dict[str, object], location: dict[str, object]) -> str:
    for key in ("partialFingerprints", "fingerprints"):
        prints = _dict(result.get(key))
        if prints:
            return json.dumps(prints, sort_keys=True)
    snippet = _dict(_dict(location.get("region")).get("snippet")).get("text")
    if isinstance(snippet, str):
        return " ".join(snippet.split())
    return " ".join(str(_dict(result.get("message")).get("text", "")).split())


def _severity(result: dict[str, object], rule: dict[str, object]) -> str:
    for properties in (_dict(result.get("properties")), _dict(rule.get("properties"))):
        name = properties.get("severity")
        if isinstance(name, str) and name.lower() in SEVERITY_NAMES:
            return SEVERITY_NAMES[name.lower()]
    return LEVELS.get(str(result.get("level", "warning")), "low")


def _security(tool: str, rule_id: str, result: dict[str, object], rule: dict[str, object]) -> bool:
    if tool.lower() in SECURITY_TOOLS or re.search(
        r"(^|[./_-])security([./_-]|$)", rule_id.lower()
    ):
        return True
    for properties in (_dict(result.get("properties")), _dict(rule.get("properties"))):
        words = [str(properties.get("category", ""))] + [
            str(t) for t in _list(properties.get("tags"))
        ]
        if any(word.lower() == "security" for word in words):
            return True
    return False


def _first_location(result: dict[str, object]) -> dict[str, object]:
    locations = _list(result.get("locations"))
    return _dict(_dict(locations[0]).get("physicalLocation")) if locations else {}


def _rules(driver: dict[str, object]) -> dict[str, dict[str, object]]:
    return {str(_dict(rule).get("id")): _dict(rule) for rule in _list(driver.get("rules"))}


def findings(report: dict[str, object]) -> list[Finding]:
    """Extract the findings of a SARIF report.

    Args:
        report: The parsed SARIF document.

    Returns:
        Every result of every run.
    """
    found: list[Finding] = []
    for run in map(_dict, _list(report.get("runs"))):
        driver = _dict(_dict(run.get("tool")).get("driver"))
        tool = str(driver.get("name", "unknown"))
        rules = _rules(driver)
        for result in map(_dict, _list(run.get("results"))):
            rule_id = str(result.get("ruleId", ""))
            rule = rules.get(rule_id, {})
            location = _dict(_first_location(result))
            path = str(_dict(location.get("artifactLocation")).get("uri", ""))
            found.append(
                Finding(
                    tool=tool,
                    rule=rule_id,
                    path=path.removeprefix("file://"),
                    fingerprint=_fingerprint(result, location),
                    severity=_severity(result, rule),
                    security=_security(tool, rule_id, result, rule),
                )
            )
    return found


def new_significant(base: dict[str, object], head: dict[str, object]) -> list[Finding]:
    """Return the significant findings the head adds over the base.

    Args:
        base: The SARIF report at the comparison base.
        head: The SARIF report of the change.

    Returns:
        One entry per added significant occurrence.
    """
    remaining = Counter(f.key() for f in findings(base))
    added: list[Finding] = []
    for finding in findings(head):
        if remaining[finding.key()] > 0:
            remaining[finding.key()] -= 1
        elif finding.significant():
            added.append(finding)
    return added


def main(argv: list[str] | None = None) -> int:
    """Run the comparison from the command line.

    Args:
        argv: Command-line arguments without the program name.

    Returns:
        The process exit status: 0 when no significant finding is added, 1 otherwise.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", type=repo_paths.safe_path)
    parser.add_argument("head", type=repo_paths.safe_path)
    args = parser.parse_args(argv)
    base = cast(_ObjectMap, json.loads(args.base.read_text(encoding="utf-8")))
    head = cast(_ObjectMap, json.loads(args.head.read_text(encoding="utf-8")))
    added = new_significant(base, head)
    for finding in added:
        category = "security" if finding.security else "other"
        print(
            f"codacy: new {finding.severity} {category} finding {finding.tool}/{finding.rule} "
            f"in {finding.path}",
            file=sys.stderr,
        )
    total = len(findings(head))
    print(f"codacy: {total} findings in the change, {len(added)} significant new")
    return 1 if added else 0


if __name__ == "__main__":
    sys.exit(main())
