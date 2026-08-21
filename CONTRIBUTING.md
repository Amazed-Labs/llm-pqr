# Contributing to LLM-PQR

Thank you for helping improve LLM-PQR.

## Design principles

- Candidates are user data, not hard-coded provider rankings.
- Keep provider execution outside the selection core.
- Do not add analytics, credential handling, or network calls to the selector.
- Treat privacy, required capabilities, and declared provider availability as hard constraints.
- Do not fabricate price, usage, latency, quality, or provenance.
- Keep unknown values unknown; `null` is better than an unsupported estimate.
- Preserve the consumer boundary: model selection must not implicitly remove agent context, memory, identity, or tools.

## Development setup

Install [uv](https://docs.astral.sh/uv/), clone the repository, then run:

```bash
uv run --with pytest --with ruff pytest
uv run --with ruff ruff check src tests
uv run --with ruff ruff format --check src tests
uv build
```

The same checks run in CI on Python 3.10–3.13.

## Tests

Write a failing test before changing behavior. Prefer behavior invariants over snapshots:

- a hosted candidate can never win a local-only request;
- unavailable providers are excluded before scoring;
- unknown cost remains unknown;
- repeated identical inputs produce the same decision;
- telemetry containing content or identity fields is rejected.

Unit tests must not contact real providers or depend on credentials. Public fixtures must be synthetic or sanitized summaries: no prompts, responses, credentials, personal names, private endpoints, hostnames, paths, chat/session/user identifiers, or copied production logs.

## Measurement provenance

Any measured example must include:

- the evaluation date and workload/corpus identifier;
- immutable input/source hashes where available;
- model/provider/runtime labels and relevant hardware;
- scheduled, valid, failed, and policy-blocked counts;
- the exact quality and latency aggregation method;
- machine-readable usage provenance, or `null`;
- dated price provenance, or `null` cost;
- an explicit ranking decision based on the repository's minimum-N and coverage gates.

A bounded smoke run may prove integration, but it must not be presented as a universal ranking.

## Pull requests

Keep commits focused and use conventional commit subjects where practical. In the PR description include:

1. User-facing behavior and motivation.
2. Tests and build commands actually run.
3. Data provenance for any measurements or prices.
4. Privacy, locality, and compatibility implications.
5. Known limitations or evidence still missing.

Do not include generated environments, credentials, private result artifacts, or unredacted logs.

## Security

Report vulnerabilities using [SECURITY.md](SECURITY.md). Do not open a public issue containing credentials, private prompts, internal endpoints, or exploit details that would put users at risk.
