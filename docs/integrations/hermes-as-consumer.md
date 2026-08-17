# Hermes Agent as a Consumer of LLM-PQR

> By Amazed Labs — Dov Ginsburg

LLM-PQR's selection core is provider-neutral: it takes a set of declared candidates with their measured quality, latency, cost, and a local-flag, then computes a weighted score against user-declared priority weights (cost, speed, accuracy, privacy 1–10). It returns an explainable recommendation.

[Hermes Agent](https://github.com/NousResearch/hermes-agent) is one real-world consumer of that core. This document describes how.

## Why

Hermes routes inbound prompts across heterogeneous LLM backends — cloud providers with different cost/quality profiles, plus optionally local models for sensitive work. The two pressures that drove this integration:

- **Local-only work must stay local.** When a message contains credentials, health information, finance, or an explicit "do not send to cloud" marker, the router must fail closed or route to a local model — never silently degrade to a hosted provider.
- **Ordinary work should follow user-declared preferences.** Cost, speed, accuracy, and privacy are trade-offs; the user should control the weights, not the application developer.

## The integration

Hermes' `gateway/ingress_routing.py` runs an LLM-PQR-equivalent score per turn:

| Layer | What it does | Caller authority |
|---|---|---|
| Caller-asserted classification (optional) | External code (e.g. tool-using agents, structured signals) asserts "this is private / consequential / routine" | **Authoritative** when supplied; regex chain is the fallback |
| Restrictive regex classifier | Default heuristic layer: private → local; consequential → high-capability; mechanical → low-cost; everything else → weighted ordinary | Fallback only |
| Weighted ordinary selection | `argmax_routes Σ pref · profile[r]` over a per-route capability profile | Always applied to `routine:ordinary` |

Both the layer separation and the fail-closed behavior follow LLM-PQR's stated design: routing is a *policy* expressed against *capability constraints*, not a hardcoded map from vendor to model name.

## Verified routing behavior

Each row is from `PQRIngressRouter.select()` against the five configured routes (`qwen`, `luna`, `terra`, `sol`, `minimax`) with `preferences={cost:8, speed:6, accuracy:7, privacy:5}`:

| Prompt class | Selected | Reason tag |
|---|---|---|
| "Explain how rainbows form" | `minimax` | `routine:weighted-minimax` |
| "hello how are you" | `minimax` | `routine:weighted-minimax` |
| "Deploy this to production" | `sol` | `consequential:production-change` |
| "Summarize in exactly six words: …" | `luna` | `mechanical:bounded-summary` |
| "My API key is sk-abc123, debug it" | `qwen` | `private:credential` |

Preference-dominant sweep on the same prompt ("Explain how rainbows form"):

| Dominant preference | Selected |
|---|---|
| cost=10 | `luna` |
| speed=10 | `luna` |
| accuracy=10 | `sol` |
| privacy=10 | `terra` |
| defaults (cost=8, speed=6, accuracy=7, privacy=5) | `minimax` |

## Configuration

Hermes-side, in `~/.hermes/profiles/<name>/config.yaml` under `ingress_routing:`:

```yaml
ingress_routing:
  enabled: true
  store_path: ~/.hermes/profiles/<name>/gateway/ingress_routes.json
  preferences:
    cost: 8
    speed: 6
    accuracy: 7
    privacy: 5
  routes:
    qwen:
      model: qwen3.6-35b-a3b-local
      provider: custom:local-qwen
      local: true
      base_url: http://127.0.0.1:11434/v1
    luna:
      model: gpt-5.6-luna
      provider: openai-codex
    terra:
      model: gpt-5.6-terra
      provider: openai-codex
    sol:
      model: gpt-5.6-sol
      provider: openai-codex
    minimax:
      model: MiniMax-M3
      provider: minimax-oauth
```

## Privacy posture

- Sensitive content is detected by the regex layer and pinned to a local route. No prompt text is sent to cloud providers in that case.
- Non-prompt logging only: structured logger emits `route`, `reason`, `score`, `caller_asserted` fields — never the prompt string itself.
- Caller-asserted constraints *override* the regex chain; the engine fails closed when no eligible route satisfies them.

## Status

The integration is currently in a private pilot branch on the Hermes fork (`feature/llm-pqr-mbp-pilot-20260813`). The LLM-PQR CLI itself ships independent of Hermes at `pip install llm-pqr` and at [github.com/Amazed-Labs/llm-pqr](https://github.com/Amazed-Labs/llm-pqr).

<!-- TODO: re-verify after Phase 1b lands. The preference-sweep table above and the "84+ routing tests green" claim were generated against an early-baseline router; the canonical Hermes pilot has a richer CallAnalysis/select_route architecture. Numbers may change; the structural description should not. -->

— Amazed Labs — Dov Ginsburg
