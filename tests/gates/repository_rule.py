# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Checks of the repository-rule files (realization RV-19(a)), used by TEST-python-TT01-05.

The commit-message hook and the pull-request scan share one committed pattern
file, which both scripts read; neither holds a pattern of its own.
"""

from __future__ import annotations

from pathlib import Path

from tools.gates import yaml_reader

HOOKS = Path("tools/hooks")
PATTERN_FILE = "attribution-pattern.txt"
TRIGGER_TYPES = {"opened", "edited", "reopened", "synchronize"}
DETECTOR_WORD = "co-authored"


def _mapping(value: object, key: str) -> dict[object, object]:
    return yaml_reader.mapping(yaml_reader.mapping(value).get(key))


def _triggers(workflow: dict[object, object]) -> dict[object, object]:
    # YAML 1.1 reads the bare key `on` as the boolean true.
    return yaml_reader.mapping(workflow.get("on", workflow.get(True)))


def ci_problems(path: Path) -> list[str]:
    """Check that ``ci.yml`` has a job named ``ci`` that needs every matrix job.

    Args:
        path: The workflow file.

    Returns:
        One message per defect, naming the file and the item.
    """
    jobs = _mapping(yaml_reader.load(path), "jobs")
    matrix_jobs = {str(n) for n, body in jobs.items() if _mapping(body, "strategy").get("matrix")}
    rollups = [
        yaml_reader.mapping(b) for b in jobs.values() if yaml_reader.mapping(b).get("name") == "ci"
    ]
    if len(rollups) != 1:
        return [f"{path}: expected one job with the display name 'ci', found {len(rollups)}"]
    needs = {str(n) for n in yaml_reader.sequence(rollups[0].get("needs"))}
    if not matrix_jobs or not matrix_jobs <= needs:
        return [f"{path}: the 'ci' job does not need every matrix job {sorted(matrix_jobs)}"]
    return []


def _permission_problems(
    path: Path, workflow: dict[object, object], job: dict[object, object]
) -> list[str]:
    problems: list[str] = []
    if yaml_reader.mapping(workflow.get("permissions")) != {"contents": "read"}:
        problems.append(f"{path}: permissions must be exactly contents: read")
    if "permissions" in job and yaml_reader.mapping(job.get("permissions")) != {"contents": "read"}:
        problems.append(f"{path}: the job adds permissions beyond contents: read")
    return problems


def hygiene_problems(path: Path) -> list[str]:
    """Check the fixed elements of ``pr-hygiene.yml``.

    Args:
        path: The workflow file.

    Returns:
        One message per defect, naming the file and the item.
    """
    workflow = yaml_reader.mapping(yaml_reader.load(path))
    problems: list[str] = []
    triggers = _triggers(workflow)
    types = {str(t) for t in yaml_reader.sequence(_mapping(triggers, "pull_request").get("types"))}
    if set(triggers) != {"pull_request"} or types != TRIGGER_TYPES:
        problems.append(f"{path}: trigger must be pull_request with types {sorted(TRIGGER_TYPES)}")
    jobs = _mapping(workflow, "jobs")
    if len(jobs) != 1:
        return [*problems, f"{path}: expected exactly one job, found {len(jobs)}"]
    job = yaml_reader.mapping(next(iter(jobs.values())))
    if job.get("name") != "no AI attribution":
        problems.append(f"{path}: the job's display name must be 'no AI attribution'")
    return problems + _permission_problems(path, workflow, job)


def pattern_problems(hooks: Path) -> list[str]:
    """Check that the hook and the scan read the one committed pattern file.

    Args:
        hooks: The hooks directory.

    Returns:
        One message per defect, naming the file and the item.
    """
    problems: list[str] = []
    if not (hooks / PATTERN_FILE).is_file():
        problems.append(f"{hooks / PATTERN_FILE}: the shared pattern file is missing")
    for script in ("check-commit-msg.sh", "scan-pull-request.sh"):
        text = (hooks / script).read_text(encoding="utf-8")
        if PATTERN_FILE not in text:
            problems.append(f"{hooks / script}: does not read the shared pattern file")
        if DETECTOR_WORD in text.lower():
            problems.append(f"{hooks / script}: holds a pattern of its own")
    return problems


def precommit_problems(path: Path) -> list[str]:
    """Check that pre-commit runs the hook at the ``commit-msg`` stage.

    Args:
        path: The pre-commit configuration.

    Returns:
        One message per defect, naming the file and the item.
    """
    for repo in yaml_reader.sequence(yaml_reader.mapping(yaml_reader.load(path)).get("repos")):
        for hook in yaml_reader.sequence(yaml_reader.mapping(repo).get("hooks")):
            body = yaml_reader.mapping(hook)
            stages = {str(s) for s in yaml_reader.sequence(body.get("stages"))}
            if body.get("entry") == "tools/hooks/check-commit-msg.sh" and "commit-msg" in stages:
                return []
    return [f"{path}: the hook does not run at the commit-msg stage"]
