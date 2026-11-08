# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Codacy gate (TS-QA-13; realization "Quality gates", `codacy`).

Fetches the pinned Codacy CLI v2 file for this OS and architecture into the uv
cache directory, verifies its SHA-256, then runs ``analyze`` (SARIF) with the
committed ``.codacy/`` configuration twice: on the working tree and on a
temporary worktree at the comparison base (with the same configuration).
``codacy_new_findings`` compares the two reports. The gate fails when the CLI
cannot be fetched, verified or run.
"""

from __future__ import annotations

import argparse
import hashlib
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from tools.gates import codacy_new_findings, comparison_base, toml_tables

CONFIG = Path("tools/gates/codacy_cli.toml")
CONFIG_DIR = Path(".codacy")
RESULTS = Path("results")
CODACY_YML = Path(".codacy.yml")
FAILURE_SIGNALS = ("failed to run", "installation failed", "failed to install")
EMPTY_SARIF = '{"version": "2.1.0", "runs": []}\n'
MACHINES = {"amd64": "x86_64", "x86_64": "x86_64", "arm64": "arm64", "aarch64": "arm64"}


class CodacyUnavailableError(RuntimeError):
    """The pinned CLI cannot be fetched, verified or run."""


def asset_key() -> str:
    """Return the configuration key of the running OS and architecture.

    Returns:
        ``<sys.platform>-<machine>``, for example ``linux-x86_64``.
    """
    return f"{sys.platform}-{MACHINES.get(platform.machine().lower(), platform.machine().lower())}"


def _cache_root() -> Path:
    result = subprocess.run(["uv", "cache", "dir"], capture_output=True, text=True, check=True)
    return Path(result.stdout.strip()) / "codacy-cli"


def _download(url: str, target: Path) -> None:
    if not url.startswith("https://"):
        message = f"refusing a non-HTTPS download: {url}"
        raise CodacyUnavailableError(message)
    try:
        with urllib.request.urlopen(url, timeout=120) as answer:  # noqa: S310
            target.write_bytes(answer.read())
    except OSError as error:
        message = f"cannot fetch {url}: {error}"
        raise CodacyUnavailableError(message) from error


def _extract(archive: Path, folder: Path) -> None:
    if archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(folder)  # noqa: S202
    else:
        with tarfile.open(archive) as bundle:
            bundle.extractall(folder, filter="data")


def fetch(config: dict[str, object]) -> Path:
    """Return the verified CLI executable, downloading it when needed.

    Args:
        config: The parsed ``codacy_cli.toml``.

    Returns:
        Path of the executable.

    Raises:
        CodacyUnavailableError: When no asset fits or the digest differs.
    """
    assets = toml_tables.table(config, "asset")
    if asset_key() not in assets:
        message = f"no pinned Codacy CLI file for {asset_key()}"
        raise CodacyUnavailableError(message)
    asset = toml_tables.table(assets, asset_key())
    version, name = str(config["version"]), str(asset["file"])
    folder = _cache_root() / version / asset_key()
    archive = folder / name
    folder.mkdir(parents=True, exist_ok=True)
    if not archive.is_file():
        _download(str(config["url"]).format(version=version, file=name), archive)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != asset["sha256"]:
        archive.unlink()
        message = f"digest mismatch for {name}: {digest}"
        raise CodacyUnavailableError(message)
    executable = folder / ("codacy-cli-v2.exe" if sys.platform == "win32" else "codacy-cli-v2")
    if not executable.is_file():
        _extract(archive, folder)
    return executable


def failure_signal(output: str) -> str | None:
    """Return the CLI's own report of an analyser that did not install or run.

    The CLI can exit 0 after an analyser failed; such output is unavailable
    infrastructure, never a pass.

    Args:
        output: The CLI's combined output.

    Returns:
        The first line signalling a failure, or ``None``.
    """
    for line in output.splitlines():
        if any(signal in line.lower() for signal in FAILURE_SIGNALS):
            return line.strip()
    return None


def analyze(executable: Path, tree: Path, output: Path) -> None:
    """Install the configured analysers and analyse a tree into SARIF.

    Args:
        executable: The verified CLI.
        tree: The tree to analyse (holding ``.codacy/``).
        output: The SARIF file to write.

    Raises:
        CodacyUnavailableError: When the CLI or one of its analysers fails.
    """
    for arguments in (["install"], ["analyze", "--format", "sarif", "-o", str(output)]):
        result = subprocess.run(
            [str(executable), *arguments],
            cwd=tree,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        print(result.stdout + result.stderr)
        signal = failure_signal(result.stdout + result.stderr)
        if result.returncode != 0 or signal:
            message = f"codacy-cli {arguments[0]} failed (status {result.returncode}): {signal}"
            raise CodacyUnavailableError(message)
    if not output.is_file():
        message = "codacy-cli wrote no report"
        raise CodacyUnavailableError(message)


def _analyze_commit(executable: Path, commit: str, tree: Path, report: Path) -> None:
    subprocess.run(["git", "worktree", "add", "--detach", str(tree), commit], check=True)
    try:
        shutil.rmtree(tree / CONFIG_DIR.name, ignore_errors=True)
        shutil.copytree(CONFIG_DIR, tree / CONFIG_DIR.name)
        shutil.copyfile(CODACY_YML, tree / CODACY_YML.name)
        analyze(executable, tree, report.resolve())
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(tree)], check=False)


def run(config_path: Path, results: Path) -> int:
    """Run the complete gate on clean worktrees of the change and of its comparison base.

    Both trees hold exactly the committed files and the change's ``.codacy/``
    configuration, so local environments and caches are never analysed.

    Args:
        config_path: The ``codacy_cli.toml`` file.
        results: Directory receiving the two SARIF reports.

    Returns:
        The exit status: 0 when no significant new finding exists, 1 otherwise.
    """
    results.mkdir(parents=True, exist_ok=True)
    head_report, base_report = results / "codacy-head.sarif", results / "codacy-base.sarif"
    executable = fetch(toml_tables.load(config_path))
    base = comparison_base.resolve()
    with tempfile.TemporaryDirectory() as work:
        _analyze_commit(executable, "HEAD", Path(work) / "head", head_report)
        if base is None:
            base_report.write_text(EMPTY_SARIF, encoding="utf-8")
        else:
            _analyze_commit(executable, base, Path(work) / "base", base_report)
    return codacy_new_findings.main([str(base_report), str(head_report)])


def main(argv: list[str] | None = None) -> int:
    """Run the Codacy gate from the command line.

    Args:
        argv: Command-line arguments without the program name.

    Returns:
        The process exit status.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    try:
        return run(CONFIG, RESULTS)
    except (CodacyUnavailableError, subprocess.CalledProcessError) as error:
        print(f"codacy: gate infrastructure unavailable: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
