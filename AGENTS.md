# Coding standard

This file is the coding standard for every contributor to generic-ml-executor, human or tool.

## Layout and rings

- `src/generic_ml_executor/api/` — the public interface. Nothing outside `api` and the root `__init__.py` imports it.
- `src/generic_ml_executor/application/` — the application ring: `domain/model` (value objects), `domain/service` (pure rules, no drivers), `port/inbound`, `port/outbound`, `usecase`, and `wiring/composition` (the only composition root).
- `src/generic_ml_executor/adapter/outbound/` — adapters. Specific components (`client`, `provider`, `kpi`, `usage`) depend on general contracts; no general component depends on a specific one.
- The dependency rules are the Import Linter contracts in `.importlinter`; the `imports` gate enforces them.

## Modules and classes

- Each production module defines exactly one class, exceptions included. Pure rules are one class with static methods or `__call__`.
- `__init__.py` modules define no class and only import or re-export.
- Modules stay within 200 lines; 201–300 lines need a recorded responsibility review; longer modules need a reviewed exception.

## Naming and style

- PEP 8 names; modules and packages in `snake_case`, classes in `PascalCase`.
- Google-style docstrings on every public module, class and function.
- Strict typing (Pyright strict); no `Any` leaking through the public interface.
- Every source file starts with:

  ```python
  # SPDX-FileCopyrightText: 2026 Daniel Slobozian
  # SPDX-License-Identifier: Apache-2.0
  ```

## Dependencies

- Library code imports only the standard library and the declared runtime requirements. A runtime requirement is added in the change whose library code first imports it.
- Test support (`tests/support/`, `tools/`) imports only the standard library, the package under test and the development group.

## Contribution metadata

No AI co-author or AI attribution lines in commits, pull requests or files.
