# Contributing

Thank you for helping improve LLM-PQR.

## Principles

- Candidates are user data, not hard-coded provider rankings.
- Keep provider adapters separate from selection policy.
- Do not add analytics, credential handling, or network calls to the core selector.
- Treat privacy/local-only as a hard constraint, never a weighted preference.
- Do not fabricate price, usage, latency, or quality measurements.

## Development

```bash
uv run --with pytest --with ruff pytest
uv run --with ruff ruff check src tests
uv run --with ruff ruff format --check src tests
```

Add a failing test before behavior changes. Public fixtures must be synthetic: no credentials, personal names, private endpoints, hostnames, sessions, or copied production logs.

## Pull requests

Describe the user-facing behavior, tests run, data provenance for any example pricing/performance, and relevant privacy implications.
