# LLM-PQR launch notes

> Prepared copy only. Nothing in this file is an announcement record or evidence that a post was sent.

## What is launching

LLM-PQR is a small, MIT-licensed Python library and CLI for choosing among user-declared model candidates. It applies hard eligibility constraints first—such as local-only, required capabilities, and unavailable providers—then ranks eligible candidates using user-supplied quality, latency, cost, and priority data.

The selector is offline and provider-neutral. It does not send prompts, call providers, inspect credentials, or invent missing measurements.

## Evidence included in this repository

- CI across Python 3.10–3.13.
- A synthetic routing corpus with explicit privacy and ranking gates.
- A route-metrics summarizer that requires an explicit taxonomy allowlist and rejects unexpected fields or values.
- A bounded measured smoke summary with immutable source and corpus hashes.
- Real measured quality and median latency in `examples/models.json`.
- Unknown usage and cost remain `null`.
- The measured smoke is explicitly **not rankable** because each candidate has fewer than the required 36 valid responses.

## Hacker News draft

**Title:** Show HN: LLM-PQR – evidence-based, provider-neutral model selection

I built LLM-PQR, a small MIT-licensed Python tool for choosing among models using measurements you control: quality, latency, token rates, capabilities, and locality.

The key design choice is that privacy and capability requirements are eligibility constraints, not weighted preferences. A hosted model cannot compensate for a local-only requirement by being cheaper or stronger.

```bash
pip install llm-pqr
llm-pqr init --output models.json
llm-pqr choose --config models.json --local-only
```

The output explains the winner, exclusions, normalized weights, and estimated cost when complete rates are supplied. The tool itself does not call providers or handle credentials.

The repository now includes a bounded measured smoke example with hashes and sample counts. It withholds rankings because the sample is below the declared minimum-N gate, and it leaves cost unknown because the adapter did not emit machine-readable usage.

GitHub: https://github.com/Amazed-Labs/llm-pqr

I would especially value feedback on which requirements should be hard gates, and what provenance you need before trusting model measurements.

## Reddit / r/LocalLLaMA draft

**Title:** I made a model selector where local-only is a hard constraint, not a preference

Local models are often treated as one more point on a quality/cost/latency curve. That fails when the actual requirement is “these bytes must not leave the machine.”

LLM-PQR applies locality before ranking:

- `--local-only` excludes every hosted candidate.
- Required capabilities and unavailable providers are also hard filters.
- Eligible candidates are ranked using measurements and priorities you supply.
- The CLI explains both exclusions and the selected candidate.

It is provider-neutral, MIT licensed, and does not send prompts or read credentials:
https://github.com/Amazed-Labs/llm-pqr

The checked-in example uses a real bounded smoke run on a local Qwen route plus hosted candidates. The result is deliberately marked unrankable: the sample is small, usage was unavailable, and cost remains unknown rather than being guessed.

What would you accept as technical proof that a “local” route is actually local—loopback resolution, Unix sockets, firewall policy, or runtime attestation?

## X draft

LLM-PQR is a provider-neutral model selector built around evidence and hard constraints.

Bring measured quality, latency, cost, and capabilities. Local-only and provider availability are enforced before ranking. Missing usage stays unknown—no invented costs or universal model rankings.

https://github.com/Amazed-Labs/llm-pqr

## Release checklist

- [x] Public repository and MIT license
- [x] CI badge and Python 3.10–3.13 matrix
- [x] Deterministic tests, Ruff, formatting, and verified build checks
- [x] Synthetic corpus and content-free telemetry fixture
- [x] Measured smoke provenance and non-rankability disclosure
- [x] Security, contribution, continuity, and roadmap documentation
- [ ] Publish or send any draft above only as a separate, explicit action
