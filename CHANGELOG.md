# Changelog

## Unreleased

- Hermes plugin: fail closed on broken config, unexpected routing errors,
  and block-pop failures; always attach provider/base_url for local
  routes (or refuse if base_url is missing). Missing config remains a
  no-op. Selection core, CLI, and package version 0.3.1 are unchanged.
- Add a standalone, unofficial Hermes Agent plugin under
  `integrations/hermes-plugin/`. It consumes LLM-PQR via middleware and is
  not an official Nous Research router. Install via
  `hermes plugins install Amazed-Labs/llm-pqr/integrations/hermes-plugin`.
  Selection core, CLI, tests for the core, and package version 0.3.1 are
  unchanged.

## 0.3.1 — 2026-08-22

- Score deterministic `json_exact` and `json_fields` evaluation rubrics,
  including JSON wrapped in fenced code blocks.
- Publish a 192-row sanitized public-text benchmark slice with 48/48 valid
  responses and 36 deterministically scored responses per candidate.
- Verify the expanded aggregate from checked-in sanitized rows while keeping
  raw responses, usage, and unsupported cost claims out of the repository.

## 0.3.0 — 2026-08-21

- Add `llm-pqr summarize` for allowlisted, content-free route metrics with
  outcome counts and per-route latency percentiles.
- Require an explicit trusted route/reason taxonomy and reject unknown,
  encoded, identifier-shaped, or content-shaped telemetry values.
- Replace placeholder model examples with a bounded measured smoke aggregate,
  24 sanitized auditable rows, immutable provenance hashes, and a verifier.
- Add provider-cooldown exclusions, the model-selection continuity boundary,
  roadmap and contribution guidance, and evidence-led launch materials.
- Package every referenced document, example, evaluation fixture, taxonomy,
  and test in the source distribution.

## 0.2.2 — 2026-08-20

- Add `Request.unavailable_providers` for callers that know a provider pool is
  in quota cooldown. Candidates on those providers are excluded before weighted
  selection and explained as `provider unavailable`.
- GitHub-only tag; not published to PyPI. The same API shipped on PyPI in 0.3.0.

## 0.2.1 — 2026-08-19

- Add a first-run configuration example and a focused feedback path for missing
  routing constraints and capabilities.

## 0.2.0 — 2026-08-17

- Add `docs/integrations/hermes-as-consumer.md` documenting the private
  Hermes policy-routing pilot. The pilot is independent of this package;
  LLM-PQR does not import, link, or run it. The doc explicitly avoids any
  production, benchmark, latency, cost, or quality claim about the pilot.
- No runtime code changes; selection core, CLI, and evals unchanged.

## 0.1.1 — 2026-08-16

- Publishable Python package and verified CLI entry point.
- Reproducible weighted-selection example with explainable output.
- Explicit local-only eligibility example and privacy design note.
- Synthetic/redacted routing corpus and bounded smoke runner.

## 0.1.0 — 2026-08-16

- Provider-neutral candidate registry and weighted selector.
- Hard local-only and capability constraints.
- Explainable JSON CLI with editable starter configuration.
- No provider calls, credentials, telemetry, or prompt storage.
- Synthetic/redacted routing evaluation corpus and bounded smoke runner.
