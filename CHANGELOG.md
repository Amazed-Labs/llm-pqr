# Changelog

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
