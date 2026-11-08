# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Sonar gate (TS-QA-13; realization "Quality gates", `sonar`).

1. Read the quality gate assigned to the project through the SonarQube Cloud
   web API and compare its conditions with ``tools/gates/sonar_quality_gate.toml``;
   a missing or different condition fails.
2. Run ``pysonar`` with ``sonar.qualitygate.wait=true``: a pull-request
   analysis on a pull request in CI, a branch analysis of ``main`` on a push,
   and locally a branch analysis of the current branch with ``main`` as the
   new-code reference.

The gate fails when ``SONAR_TOKEN`` is absent, when the service cannot be
reached or does not answer within its bound, or when the quality-gate status is
not OK. Unavailable infrastructure is never a pass.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import cast

from tools.gates import toml_tables

CONFIG = Path("tools/gates/sonar_quality_gate.toml")
TIMEOUT_SECONDS = 60
WAIT_SECONDS = "600"


class GateUnavailableError(RuntimeError):
    """The Sonar service or its credentials are unavailable."""


def _get(host: str, path: str, query: dict[str, str], token: str) -> dict[str, object]:
    url = f"{host}{path}?{urllib.parse.urlencode(query)}"
    if not url.startswith("https://"):
        message = f"refusing a non-HTTPS service URL: {host}"
        raise GateUnavailableError(message)
    request = urllib.request.Request(url)  # noqa: S310
    credentials = base64.b64encode(f"{token}:".encode()).decode()
    request.add_header("Authorization", f"Basic {credentials}")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as answer:  # noqa: S310
            return cast("dict[str, object]", json.loads(answer.read()))
    except OSError as error:
        message = f"SonarQube Cloud did not answer {path}: {error}"
        raise GateUnavailableError(message) from error


def condition_problems(
    expected: list[dict[str, object]], actual: list[dict[str, object]]
) -> list[str]:
    """Compare required conditions with the service's conditions.

    Args:
        expected: The committed conditions.
        actual: The conditions the service reports for the project's gate.

    Returns:
        One message per missing or different condition.
    """
    service = {str(c.get("metric")): (str(c.get("op")), str(c.get("error"))) for c in actual}
    problems: list[str] = []
    for condition in expected:
        metric = str(condition.get("metric"))
        wanted = (str(condition.get("op")), str(condition.get("error")))
        if metric not in service:
            problems.append(f"quality gate lacks the condition on {metric}")
        elif service[metric] != wanted:
            problems.append(
                f"quality gate condition on {metric} is {service[metric]}, expected {wanted}"
            )
    return problems


def _gate_conditions(service: dict[str, object], token: str) -> list[dict[str, object]]:
    host, org = str(service["host"]), str(service["organization"])
    assigned = _get(
        host,
        "/api/qualitygates/get_by_project",
        {"project": str(service["project"]), "organization": org},
        token,
    )
    gate = toml_tables.table(assigned, "qualityGate")
    shown = _get(
        host, "/api/qualitygates/show", {"id": str(gate.get("id")), "organization": org}, token
    )
    return toml_tables.tables(shown, "conditions")


def _event() -> dict[str, object]:
    path = os.environ.get("GITHUB_EVENT_PATH")
    if not path:
        return {}
    return cast("dict[str, object]", json.loads(Path(path).read_text(encoding="utf-8")))


def analysis_arguments() -> list[str]:
    """Return the pysonar arguments that select the analysis kind.

    Returns:
        Pull-request, ``main`` branch or local branch arguments.
    """
    event_name = os.environ.get("GITHUB_EVENT_NAME")
    if event_name == "pull_request":
        pull = toml_tables.table(_event(), "pull_request")
        head, base = toml_tables.table(pull, "head"), toml_tables.table(pull, "base")
        return [
            f"--sonar-pullrequest-key={pull.get('number')}",
            f"--sonar-pullrequest-branch={head.get('ref')}",
            f"--sonar-pullrequest-base={base.get('ref')}",
        ]
    if event_name == "push":
        return [f"--sonar-branch-name={os.environ.get('GITHUB_REF_NAME', 'main')}"]
    branch = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    return [f"--sonar-branch-name={branch}", "--sonar-newcode-reference-branch=main"]


def main(argv: list[str] | None = None) -> int:
    """Run the Sonar gate from the command line.

    Args:
        argv: Command-line arguments without the program name.

    Returns:
        The process exit status: 0 when the quality gate passes, 1 otherwise.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    config = toml_tables.load(CONFIG)
    service = toml_tables.table(config, "service")
    token = os.environ.get("SONAR_TOKEN", "")
    if not token:
        print("sonar: SONAR_TOKEN is absent: gate infrastructure unavailable", file=sys.stderr)
        return 1
    try:
        problems = condition_problems(
            toml_tables.tables(config, "condition"), _gate_conditions(service, token)
        )
    except GateUnavailableError as error:
        print(f"sonar: {error}", file=sys.stderr)
        return 1
    for problem in problems:
        print(f"sonar: {problem}", file=sys.stderr)
    if problems:
        return 1
    command = [
        "pysonar",
        f"--sonar-host-url={service['host']}",
        f"--sonar-organization={service['organization']}",
        f"--sonar-project-key={service['project']}",
        "--sonar-qualitygate-wait",
        f"--sonar-qualitygate-timeout={WAIT_SECONDS}",
        *analysis_arguments(),
    ]
    result = subprocess.run(command, check=False)
    print(
        "sonar: quality gate passed"
        if result.returncode == 0
        else "sonar: quality gate failed or unavailable"
    )
    return result.returncode and 1


if __name__ == "__main__":
    sys.exit(main())
