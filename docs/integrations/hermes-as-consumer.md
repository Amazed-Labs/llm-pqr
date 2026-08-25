# A Hermes policy-routing pilot informed by LLM-PQR

> By Amazed Labs — Dov Ginsburg

LLM-PQR is a small, provider-neutral, offline selection core: you declare candidates and measured attributes, set the trade-offs you care about, and get an explainable recommendation.

A private [Hermes Agent](https://github.com/NousResearch/hermes-agent) pilot explores how those same *policy-routing questions* behave at message ingress. This is **not** a public Hermes integration and Hermes does not import LLM-PQR as a runtime dependency. It is an independently evolved pilot informed by the same idea: model selection should be an explicit policy under capability constraints, not a hidden vendor-to-model map.

## Why explore this

A message router needs to distinguish two kinds of decisions:

- **Hard constraints.** Sensitive content must remain on an authorized local route; consequential work needs a route that meets its required capability floor. If no eligible route exists, the engine must refuse rather than silently weaken that constraint.
- **Ordinary trade-offs.** For work without a hard constraint, a user can express the relative importance of cost, speed, accuracy, and privacy. The selection mechanism should make that preference legible and testable.

## The pilot architecture

The Hermes-side router is deliberately layered:

| Layer | Behavior |
|---|---|
| Call analysis | Derives complexity, risk, domain, intent, and a permitted model floor/ceiling window without calling a provider. |
| Caller assertion (optional) | Programmatic callers may supply a `CallAnalysis` when they have an authoritative structured classification; it takes precedence over the heuristic analysis. |
| Constraint enforcement | Private caller assertions require the local route; consequential caller assertions require the high-capability route. Missing required routes raise a structured `NoEligibleRouteError`. |
| Ordinary selection | Eligible routes are selected inside the analysis window using the configured user weights. |
| Rewrite monotonicity | If a prepared prompt requires a more restrictive route, it can upgrade the decision but cannot downgrade it. |

This is policy-based routing with capability constraints. It is not a claim that a specific vendor/model pairing is universally optimal.

## What is verified

As of the private pilot commit `6a5638594c`:

- **82/82** focused `tests/gateway/test_ingress_routing.py` tests pass.
- The focused suite covers caller assertions, missing-local and missing-high-capability fail-closed paths, monotonic prepared-prompt upgrades, weighted ordinary selection, route-store behavior, and logging metadata with prompt canaries.
- Structured ingress logging records route IDs, reason codes, caller-assertion status, prepared-route outcome, and score — **never raw prompt text**.
- The test result validates routing logic only. It is not a public cost, latency, quality, or provider benchmark, and the private pilot is not a production-release claim.

## Privacy and safety posture

- Heuristic detection is a conservative fallback; an authoritative caller assertion takes precedence when one is supplied programmatically.
- If an asserted private request has no authorized local route, the engine fails closed with `no-eligible-route:private`.
- If an asserted consequential request has no high-capability route, the engine fails closed with `no-eligible-route:consequential`.
- Ordinary requests may select the best eligible route within their window rather than being refused merely because an optional route is absent.

## Status

The Hermes work remains a private pilot on the `feature/llm-pqr-mbp-pilot-20260813` branch. LLM-PQR itself remains an independent alpha CLI: [github.com/Amazed-Labs/llm-pqr](https://github.com/Amazed-Labs/llm-pqr).

A later, separately maintained [opt-in Hermes plugin](../../integrations/hermes-plugin/README.md) now lives under `integrations/hermes-plugin/`. It consumes LLM-PQR as a library and is not an official Nous Research router. It is not the private pilot described above.

— Amazed Labs — Dov Ginsburg
