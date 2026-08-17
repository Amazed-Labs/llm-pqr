# LLM-PQR Launch Notes

> Drafts prepared by Amazed Labs — Dov Ginsburg. **Not for posting until you say so.**

This file collects channel-specific drafts for announcing LLM-PQR. Each draft is anchored to verifiable facts from the codebase and from a private pilot.

<!-- TODO: re-verify after Phase 1b — preference-sweep counts and "84+ tests" numbers depend on which router architecture is canonical. The drafts below cite 84; if the real-substrate Phase 1b work lands a different count, only those numbers (and the sweep table in `hermes-as-consumer.md`) need to be re-checked. The framing, voice, and "what LLM-PQR is" content are independent of the test count and can ship as-is. -->

## Verified facts (use these; do not invent beyond them)

- LLM-PQR is a small, provider-neutral Python package: `pip install llm-pqr`, CLI `llm-pqr`.
- The selection core is deterministic and offline: it does not call any model provider and does not handle credentials.
- The current public release is alpha — a deterministic selection core + CLI, not an autonomous router.
- A second consumer exists in private pilot: Hermes Agent's `gateway/ingress_routing.py`. The pilot branch has 84+ routing tests green (including caller-asserted, fail-closed, and preference-dominant sweeps).
- No public benchmark has been published yet. Don't claim one.

## What is NOT yet true (avoid these in any draft)

- "LLM-PQR beat OpenRouter / LiteLLM / [provider X]."
- "Saves N% on cost" without a measured scenario.
- "Used at [Company Y] in production."
- "We're hiring" / "Series A" / "raise" / "valuation."

---

## Draft 1 — r/LocalLLaMA (~280 words)

**Title:** LLM-PQR — provider-neutral model selection for the rest of us

**Body:**

I'm Dov Ginsburg. I built LLM-PQR (LLM Provider-Quotient Router, yes the name is a mouthful) because I kept running into the same problem: a half-dozen models, a half-dozen cost/quality trade-offs, and no easy way to compare them on *my* workload instead of someone else's leaderboard.

LLM-PQR is provider-neutral and offline. You declare each candidate's measured quality, latency, token prices, and whether it's local. You set how much you care about cost, speed, accuracy, and privacy. It computes a weighted score, returns a recommendation, and shows the work.

```bash
pip install llm-pqr
llm-pqr init --output models.json
llm-pqr choose --config models.json --input-tokens 1200 --output-tokens 300
```

Status: alpha. The current release is the deterministic selection core and CLI. No credential handling, no provider calls, no telemetry.

A practical consumer exists in private pilot: Hermes Agent's ingress router uses the same weighted-score pattern (private → local, consequential → capable, ordinary → weighted). The pilot branch has 84+ routing tests green. Happy to write up the integration separately if there's interest.

Repo: github.com/Amazed-Labs/llm-pqr

---

## Draft 2 — r/MachineLearning (~180 words, evidence-mode)

**Title:** LLM-PQR — deterministic provider-neutral model selection (alpha)

**Body:**

LLM-PQR is a small Python package for choosing among your own models using measured quality, latency, token prices, and a local flag. Selection is a deterministic weighted sum against user-declared priorities (cost / speed / accuracy / privacy, each 1–10). It runs offline, takes no credentials, and returns an explanation of why a particular candidate won.

Repo: github.com/Amazed-Labs/llm-pqr · pip: `llm-pqr` · CLI: `llm-pqr choose`.

Current state: selection core + CLI, alpha. No claims on universal model rankings — values in `examples/models.json` are illustrative, meant to be replaced with measured data per workload.

If you've built a similar tool, I'd like to compare notes on the weighted-scoring vs. regret-minimizing vs. policy-tree approaches.

— Dov Ginsburg

---

## Draft 3 — Show HN (~120 words, founder-voice)

**Title:** Show HN: LLM-PQR – deterministic, offline model selection

**Body:**

I'm Dov Ginsburg. I built LLM-PQR because choosing among models on someone else's leaderboard kept giving wrong answers for my actual workloads.

LLM-PQR is a tiny Python package: declare your candidates' measured quality/latency/token prices/local flag, set cost/speed/accuracy/privacy weights (1–10), get a recommendation with the math shown. It runs offline. No provider calls, no credentials.

It's early (alpha). My current consumer is a private pilot of Hermes Agent's ingress router: 84+ routing tests green, including caller-asserted constraints and fail-closed on missing-eligible-route. Happy to talk about either direction.

github.com/Amazed-Labs/llm-pqr

---

## Draft 4 — X / Twitter thread (8 posts)

**Post 1:**
I keep ending up with seven models, seven bills, and no honest way to say which one I should be using for *this* task.

So I built LLM-PQR. →

**Post 2:**
LLM-PQR is a tiny Python package.

You declare your candidates (model, latency, cost, local flag).
You declare your priorities (cost / speed / accuracy / privacy, 1–10).
It returns one model, with the math shown.

`pip install llm-pqr`

**Post 3:**
The interesting part: it's deterministic, offline, and provider-neutral.

No provider calls. No credentials. No leaderboard rankings baked in. You bring your measured numbers, you bring your weights, you get a recommendation.

**Post 4:**
The selection core is a weighted sum: argmax over candidates of (Σ pref · profile[c]).

That's the whole algorithm. The rest of the package is plumbing around declaring candidates cleanly and showing the work in the output.

**Post 5:**
One downstream consumer exists already: Hermes Agent's ingress router. In a private pilot:

84+ routing tests green.
Preference-dominant sweep behaves as expected.
Caller-asserted classification overrides regex heuristics.
Fail-closed when no eligible route exists.

**Post 6:**
Status: alpha. The CLI works; the algorithm is small enough to read in one sitting.

What's NOT in the alpha: a universal benchmark (I don't trust universal benchmarks for selection), an autonomous runtime router (only one consumer so far), public benchmarks (no measured data to publish yet).

**Post 7:**
Repo: github.com/Amazed-Labs/llm-pqr

If you've built something similar — regret-minimizing selection, policy trees, learned routers — I'd genuinely like to compare notes. Reply or DM.

— Dov Ginsburg

**Post 8:**
(Amazed Labs is my lab; I ship small, evidence-first tools. LLM-PQR is the first public release. LimitID (privacy) and TonO (writing) live there too.)
