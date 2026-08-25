# Proposal: an opt-in policy-routing integration for Hermes Agent

> **Status:** proposal from Amazed Labs and Dov Ginsburg. It is not an official Nous Research or Hermes Agent roadmap commitment. A standalone opt-in plugin now lives at [`integrations/hermes-plugin/`](../../integrations/hermes-plugin/README.md); it consumes LLM-PQR and is independently maintained.

## Summary

LLM-PQR is a small, offline, provider-neutral model-selection core. It accepts user-supplied candidate measurements, capabilities, locality declarations, and priorities, then returns an explainable selection. It does not call providers, receive prompts, store credentials, or collect telemetry.

A private Hermes Agent pilot explored a complementary runtime pattern: **analyze locally before provider invocation, enforce hard policy constraints, select within the permitted route window, then execute the ordinary Hermes turn.**

This proposal asks for feedback on an opt-in, edge-level integration that makes this pattern reusable without putting a third-party product into Hermes core.

## The problem

A provider fallback chain answers “what runs if the preferred provider fails?” It does not answer the prior decision: **which routes are eligible for this turn?**

Routing needs to separate:

1. **Hard constraints** — for example, content that must remain on an authorized local endpoint, or a consequential action that requires a high-capability route. If no eligible route exists, the turn fails closed.
2. **Ordinary trade-offs** — among eligible routes, select using user-controlled weights such as cost, latency, quality, and privacy.

The integration should preserve Hermes invariants: normal conversation ownership, prompts, memory, skills, tools, and session continuity remain intact. A route selects a model for a turn; it must not silently create a reduced, contextless agent.

## Proposed shape

### 1. A generic opt-in policy-routing interface

A Hermes integration would be configured through normal user-facing configuration, not environment flags. It would declare routes as data:

```yaml
ingress_routing:
  enabled: true
  preferences: {cost: 8, speed: 6, accuracy: 7, privacy: 5}
  routes:
    local:
      model: my-local-vision-model
      provider: openai-compatible
      base_url: http://127.0.0.1:8000/v1
      local: true
      capabilities: [text, vision]
    economy:
      model: provider/economy-model
      provider: openrouter
      capabilities: [text, tools]
    frontier:
      model: provider/frontier-model
      provider: openrouter
      capabilities: [text, tools, vision]
```

Candidate declarations remain provider-neutral. The integration does not prescribe a model vendor or claim universal rankings.

### 2. Deterministic local pre-routing

Before any provider sees a request, a local analysis produces a structured policy window:

- complexity, risk, intent, and required capabilities;
- route floor and ceiling;
- confidence and reason codes;
- whether the turn needs a local-only or higher-capability route.

A user or programmatic caller can supply an authoritative structured assertion when a heuristic is insufficient. The pre-router does not rely on a cloud model to decide whether content may go to the cloud.

### 3. Technical locality verification

A route labeled `local: true` must resolve to a verified local endpoint or an explicitly configured local command. A configuration label alone is not enough for private content.

If an asserted private request lacks an eligible verified-local route, the integration returns a structured fail-closed result rather than weakening the constraint.

### 4. Privacy-preserving, local-only measurement

No outbound analytics or identifiers are required. An opt-in local metric can record only:

- UTC timestamp;
- chosen route;
- reason class;
- end-to-end latency;
- coarse outcome (`success`, `failed`, `interrupted`, or `failed_closed`).

It must not record prompts, responses, attachment paths, chat/user/session IDs, secrets, or provider payloads. A retention period and aggregate-only reporting should be explicit configuration choices.

## Pilot evidence

The private pilot has focused on correctness and safe observability rather than a public performance claim.

- The current active route path has recorded **346 completed routed turns**: Terra 154, MiniMax 123, local Qwen 52, and Sol 17.
- Outcomes: 342 successful and 4 interrupted.
- The routing metric rows contain only route, policy reason, latency, outcome, and (in the current revision) UTC timestamp.
- Focused gateway/PQR/media regression coverage passed **43 tests** in the current worktree.

These observations demonstrate that the active path can select more than one route. They do **not** establish universal quality, cost savings, or benchmark rankings. Those would require a published workload, provider-specific telemetry provenance, comparable coverage thresholds, and explicit release acceptance.

## Why an edge integration rather than core coupling

LLM-PQR should remain an independent CLI/library. Hermes should not take a mandatory runtime dependency on it.

A practical path is a standalone opt-in plugin or a small generic policy-routing extension point owned by Hermes. This keeps the core narrow, lets users select their own model/provider registry, and avoids introducing outbound telemetry or vendor coupling.

## Requested feedback from the Hermes community

1. Is an opt-in standalone plugin the right initial surface, or is there already an extension point that should be used?
2. Which generic policy fields would be necessary for real deployments beyond `local-only`, capability labels, cost, latency, and quality?
3. What should the minimal operator-facing evidence report include to make routing behavior auditable without exposing content?
4. Which hard constraints should be technical fail-closed gates rather than soft weighted preferences?

## Scope and non-goals

This proposal does **not** ask Hermes to:

- adopt a vendor-specific router or external analytics backend;
- send prompts or content to LLM-PQR;
- make universal claims about which model is “best”;
- replace fallback providers, ordinary Hermes sessions, tools, memory, or user control;
- enable telemetry without an explicit, user-facing opt-in.

## Links

- [LLM-PQR repository](https://github.com/Amazed-Labs/llm-pqr)
- [LLM-PQR PyPI package](https://pypi.org/project/llm-pqr/)
- [Hermes continuity boundary from the private pilot](../integrations/hermes-as-consumer.md)
