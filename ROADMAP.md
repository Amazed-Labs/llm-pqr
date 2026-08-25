# LLM-PQR roadmap

LLM-PQR is intentionally a small, provider-neutral selection core. This roadmap prioritizes evidence quality and hard-policy correctness over becoming a provider proxy.

## Shipped

- Deterministic candidate selection with explainable scores.
- Hard local-only and required-capability constraints.
- Hard exclusion for declared unavailable providers.
- Optional, non-fabricated token-cost estimation.
- Synthetic routing corpus with privacy and minimum-coverage gates.
- Allowlisted route telemetry summarization that never emits unknown taxonomy values.
- Measured smoke provenance with explicit non-rankability.
- Python 3.10–3.13 CI and verified source/wheel package builds.
- Standalone unofficial Hermes Agent plugin (opt-in; consumes LLM-PQR; not a Nous router).

## Next

### Evaluation integrity

- Add schema validation for normalized evaluation result artifacts.
- Report quality conditional on response separately from reliability.
- Add repeat/coverage aggregation that enforces minimum-N before ranking.
- Add dated pricing provenance without coupling the selector to a vendor.

### Selection constraints

- Context-window and modality requirements.
- User-declared budget and latency ceilings.
- Data-residency and licensing labels as hard eligibility rules.
- A stable policy-reason taxonomy for downstream audit logs.

### Integration ergonomics

- Document adapter contracts for applications that already invoke providers.
- Add more sanitized consumer examples without importing consumer runtimes.
- Preserve context, memory, identity, and tools when consumers switch models unless isolation is explicitly requested.

## Later, evidence permitting

- Shadow-mode comparison between a consumer's current choice and LLM-PQR's recommendation.
- Versioned model registries supplied by users or independent data packages.
- Workload-specific calibration and uncertainty reporting.
- Export formats for common evaluation and observability tools.

## Explicit non-goals

- A hosted routing service.
- Credential storage or provider authentication.
- Sending prompts or invoking models from the selection core.
- Hidden vendor tiers or universal model rankings.
- Treating privacy as a weighted preference.
- Silently converting missing usage, price, latency, or quality into invented values.
- Changing an agent's runtime identity or capabilities merely because a different model was selected.

## Promotion bar

A feature moves from experiment to the stable selector only when it has:

1. A concrete consumer need.
2. A provider-neutral representation.
3. Failing-then-passing invariant tests.
4. Clear privacy and provenance behavior.
5. Documentation that distinguishes implementation, integration testing, benchmarking, rankability, and production readiness.
