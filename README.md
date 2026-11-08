# generic-ml-executor

Python library for driving ML coding clients and model APIs, with a gateway to observe and control each client's own traffic.

> **Status:** early development. This repository holds the package skeleton and its quality gates; no library behaviour is available yet. The complete documentation set arrives with a later change.

## Development

The gates run through one entry point, identical locally and in CI:

```sh
uv run --frozen nox -s green
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the gate rules and the contribution process.

## Licence

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
