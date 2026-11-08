# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Acceptance-inventory gate (realization "Quality gates", `acceptance_inventory`).

Inputs: ``acceptance/target-cases.toml`` (the required-case set),
``acceptance/required-cases.toml`` (the inventory), the ``case`` markers of the
collected tests (JSON written by ``tools.gates.case_markers``) and, for
``release-pipeline`` entries, ``.github/workflows/release.yml``.

It fails when the inventory's identity set or ``target`` header differs from the
required-case set; an ``acceptance-host`` or ``ci`` entry is ``implemented``
without a marked test; a marked test maps to no entry, to a ``planned`` entry
or to a ``not-applicable`` entry; a ``not-applicable`` entry is outside
``product_not_applicable``; an implemented ``release-pipeline`` entry names a
job that ``release.yml`` lacks, that is off ``publish``'s ``needs`` chain or
whose ``if:`` excludes the ``release`` event; an entry has the venue
``validator``. ``planned`` entries pass.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import cast

from tools.gates import toml_tables, yaml_reader

STATUSES = frozenset({"planned", "implemented", "not-applicable"})
VENUES = frozenset({"acceptance-host", "ci", "release-pipeline"})
MARKED_VENUES = frozenset({"acceptance-host", "ci"})


def required_identities(target: dict[str, object]) -> set[str]:
    """Return every identity the required-case set names.

    Args:
        target: The parsed ``target-cases.toml``.

    Returns:
        The ``tc``, ``test`` and ``product_not_applicable`` identities.
    """
    identities = set(toml_tables.strings(target, "tc")) | set(toml_tables.strings(target, "test"))
    return identities | not_applicable_identities(target)


def not_applicable_identities(target: dict[str, object]) -> set[str]:
    """Return the ``product_not_applicable`` identities.

    Args:
        target: The parsed ``target-cases.toml``.

    Returns:
        The identities that do not apply to the product.
    """
    return {str(row.get("id")) for row in toml_tables.tables(target, "product_not_applicable")}


def _release_jobs(workflow: Path) -> dict[str, dict[object, object]]:
    if not workflow.is_file():
        return {}
    jobs = yaml_reader.mapping(yaml_reader.mapping(yaml_reader.load(workflow)).get("jobs"))
    return {str(name): yaml_reader.mapping(body) for name, body in jobs.items()}


def _publish_chain(jobs: dict[str, dict[object, object]]) -> set[str]:
    chain: set[str] = set()
    pending = ["publish"] if "publish" in jobs else []
    while pending:
        job = pending.pop()
        if job not in chain:
            chain.add(job)
            pending.extend(
                str(need) for need in yaml_reader.sequence(jobs.get(job, {}).get("needs"))
            )
    return chain


def _excludes_release(condition: object) -> bool:
    if not isinstance(condition, str) or "event_name" not in condition:
        return False
    text = condition.replace('"', "'").replace(" ", "")
    if "event_name!='release'" in text:
        return True
    return "event_name==" in text and "event_name=='release'" not in text


def _release_problems(ident: str, entry: dict[str, object], workflow: Path) -> list[str]:
    jobs = _release_jobs(workflow)
    chain = _publish_chain(jobs)
    names = toml_tables.strings(entry, "realized_by")
    if not names:
        return [f"{ident}: implemented release-pipeline entry names no job"]
    problems: list[str] = []
    for job in names:
        if job not in jobs:
            problems.append(f"{ident}: job '{job}' is not defined in {workflow}")
        elif job not in chain:
            problems.append(f"{ident}: job '{job}' is not on publish's needs chain")
        elif _excludes_release(jobs[job].get("if")):
            problems.append(f"{ident}: job '{job}' excludes the release event")
    return problems


def _entry_problems(entry: dict[str, object], marked: set[str], context: _Context) -> list[str]:
    ident = str(entry.get("id"))
    status, venue = str(entry.get("status")), str(entry.get("venue"))
    if venue == "validator":
        return [f"{ident}: venue 'validator' is never an inventory entry"]
    if status not in STATUSES or venue not in VENUES:
        return [f"{ident}: unknown status '{status}' or venue '{venue}'"]
    if status == "not-applicable" and ident not in context.not_applicable:
        return [f"{ident}: not-applicable but outside product_not_applicable"]
    return _implemented_problems(ident, entry, ident in marked, context)


def _implemented_problems(
    ident: str, entry: dict[str, object], marked: bool, context: _Context
) -> list[str]:
    if str(entry.get("status")) != "implemented":
        return []
    venue = str(entry.get("venue"))
    if venue in MARKED_VENUES and not marked:
        return [f"{ident}: implemented without a collected test carrying its marker"]
    if venue == "release-pipeline":
        return _release_problems(ident, entry, context.workflow)
    return []


class _Context:
    def __init__(self, not_applicable: set[str], workflow: Path) -> None:
        self.not_applicable = not_applicable
        self.workflow = workflow


def _marker_problems(markers: dict[str, list[str]], statuses: dict[str, str]) -> list[str]:
    problems: list[str] = []
    for node, cases in sorted(markers.items()):
        for case in cases:
            status = statuses.get(case)
            if status is None:
                problems.append(f"{case}: marked test {node} maps to no inventory entry")
            elif status != "implemented":
                problems.append(f"{case}: marked test {node} maps to a {status} entry")
    return problems


def check(
    target: dict[str, object],
    inventory: dict[str, object],
    markers: dict[str, list[str]],
    workflow: Path,
) -> list[str]:
    """Return every inventory violation.

    Args:
        target: The parsed ``target-cases.toml``.
        inventory: The parsed ``required-cases.toml``.
        markers: Each collected test's node identifier mapped to its case identities.
        workflow: The release workflow file.

    Returns:
        One message per violation, each naming the case.
    """
    entries = toml_tables.tables(inventory, "case")
    statuses = {str(entry.get("id")): str(entry.get("status")) for entry in entries}
    required = required_identities(target)
    problems: list[str] = []
    if toml_tables.table(target, "target") != toml_tables.table(inventory, "target"):
        problems.append("target: the inventory's target header differs from target-cases.toml")
    if len(statuses) != len(entries):
        problems.append("inventory: an identity has more than one entry")
    problems += [
        f"{i}: required but missing from the inventory" for i in sorted(required - set(statuses))
    ]
    problems += [
        f"{i}: in the inventory but not required" for i in sorted(set(statuses) - required)
    ]
    marked = {case for cases in markers.values() for case in cases}
    context = _Context(not_applicable_identities(target), workflow)
    for entry in entries:
        problems += _entry_problems(entry, marked, context)
    return problems + _marker_problems(markers, statuses)


def main(argv: list[str] | None = None) -> int:
    """Run the inventory gate from the command line.

    Args:
        argv: Command-line arguments without the program name.

    Returns:
        The process exit status: 0 when the inventory passes, 1 otherwise.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, default=Path("acceptance/target-cases.toml"))
    parser.add_argument("--inventory", type=Path, default=Path("acceptance/required-cases.toml"))
    parser.add_argument("--markers", type=Path, required=True)
    parser.add_argument(
        "--release-workflow", type=Path, default=Path(".github/workflows/release.yml")
    )
    args = parser.parse_args(argv)
    markers = cast("dict[str, list[str]]", json.loads(args.markers.read_text(encoding="utf-8")))
    problems = check(
        toml_tables.load(args.target),
        toml_tables.load(args.inventory),
        markers,
        args.release_workflow,
    )
    for problem in problems:
        print(f"acceptance_inventory: {problem}", file=sys.stderr)
    if not problems:
        print("acceptance_inventory: passed")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
