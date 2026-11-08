# Contributing

Thank you for helping. This file states the rules every change must meet.

## One gate entry point

All quality gates run through nox, with the tool versions locked in `uv.lock`:

```sh
uv run --frozen nox -s green
```

`green` reads the gate register `tools/gates/gate-set.toml`, prints the active and the pending sessions, and runs every active one. CI runs exactly the same command on every cell of Linux, macOS and Windows × CPython 3.11–3.15. A change is accepted only when `green` passes locally and the required checks pass on its pull request. A gate that cannot run (for example, an unreachable service) fails; it never passes silently.

| session | rule |
|---|---|
| `lint` | `ruff check` and `ruff format --check` with the rule set in `pyproject.toml` (the family's strict set plus McCabe `C90`, maximum complexity 10, Google docstrings). |
| `complexity` | cognitive complexity at most 15 (`complexipy`) over `src`, `tests`, `tools` and `noxfile.py`. |
| `structure` | every production module defines exactly one class (`__init__.py` defines none and only imports or re-exports; PEP 562 `__getattr__`/`__dir__` allowed); modules of 201–300 lines need an entry in `quality/module-size-reviews.toml`; modules above 300 lines fail unless `quality/module-size-exceptions.toml` holds a reviewed exception. |
| `imports` | the eight Import Linter contracts in `.importlinter`. |
| `typecheck` | Pyright strict (exact version pin), zero errors. |
| `tests` | pytest on the running interpreter; warnings are errors. |
| `coverage` | line coverage of the package at least 90 % (`covered_lines / num_statements`); branch coverage measured. |
| `security` | `pip-audit` over the locked environments; `detect-secrets` against `.secrets.baseline`. |
| `licenses` | runtime licences MIT, BSD, Apache-2.0, PSF-2.0 or ISC; development tools may also be MPL-2.0 or LGPL. |
| `workflows` | `zizmor` over `.github/workflows`; every workflow declares `permissions: contents: read`. |
| `public_api` | the public surface snapshot `api/public-api.json`; a change of the surface must also change `docs/reference/public-api.md`, `CHANGELOG.md` and at least one file under `tests/`. |
| `gate_set` | the register matches the gate sessions; only `evidence` (TU-02) and `docs` (TU-19) may be `pending`; an active gate never returns to `pending`. |
| `acceptance_inventory` | `acceptance/required-cases.toml` matches `acceptance/target-cases.toml` and the tests marked `pytest.mark.case(...)`. |
| `sonar` | SonarQube Cloud quality gate (no new bugs, no new vulnerabilities, every new hotspot reviewed, maintainability A on new code); needs `SONAR_TOKEN`. |
| `codacy` | the pinned Codacy CLI; a change must not add a finding of severity High or Critical, or a Security finding of severity Medium or above. |

## Pull requests and required checks

- Every change reaches `main` through a pull request. Two checks are required: `ci` (all CI cells passed) and `no AI attribution`.
- Commit messages, pull-request titles and bodies, and files must not contain AI co-author or AI attribution lines. The commit-message hook (`tools/hooks/check-commit-msg.sh`, installed with `uv run --frozen pre-commit install --hook-type commit-msg`) and the `no AI attribution` check enforce this. Never bypass the hook.
- **Pull requests from forks** receive no `SONAR_TOKEN`, so their `sonar` session fails as "gate infrastructure unavailable" and the change is not accepted. A maintainer accepts such a change only after pushing its commits to a branch of this repository, where the gate runs with credentials.

## Style

See [AGENTS.md](AGENTS.md) for the coding standard (naming, one class per module, ring placement). Every source file starts with SPDX headers.
