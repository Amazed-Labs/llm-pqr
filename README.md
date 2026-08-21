# LLM-PQR

[![CI](https://github.com/Amazed-Labs/llm-pqr/actions/workflows/ci.yml/badge.svg)](https://github.com/Amazed-Labs/llm-pqr/actions/workflows/ci.yml)

**Test your models. Pick with evidence.**

LLM-PQR is a small, provider-neutral tool for choosing among *your* models. You declare each model's measured quality, latency, token prices, capabilities, and whether it is local. Then you choose how much you value cost, speed, and quality. LLM-PQR produces an explainable recommendation without calling a provider or handling credentials.

> **Status:** alpha. The first release is a deterministic selection core and CLI, not an autonomous router or a universal benchmark.

## Why

Model choice is contextual. A low-cost local model may be ideal for private transformations; a stronger hosted model may be worthwhile for complex work. LLM-PQR keeps that decision in user-controlled data rather than hard-coding vendor tiers or marketing labels.

## Real-world reference

A private [Hermes Agent policy-routing pilot](docs/integrations/hermes-as-consumer.md) explores the same bounded-routing questions LLM-PQR answers: hard local-only constraints, capability floors, monotonic rewrites, and content-free route logging. The pilot is independent of this package; LLM-PQR does not import, link, or run it, and the document makes no production or benchmark claims. See [PQR continuity](docs/pqr-continuity.md) for the consumer boundary: selecting a model must not silently alter an agent's context, memory, identity, or tools.

## Quick start

```bash
python -m pip install llm-pqr
llm-pqr init --output models.json
llm-pqr choose \
  --config models.json \
  --input-tokens 1200 \
  --output-tokens 300
```

## Make the first result useful

`init` intentionally creates placeholders: LLM-PQR never guesses a provider,
model, price, or quality score for you. Replace the generated candidate with
one model you already use and values you have measured or verified. For example:

```json
{
  "priorities": {"cost": 8, "latency": 6, "quality": 7},
  "models": [
    {
      "id": "my-local-model",
      "provider": "my-local-runtime",
      "model": "my-model-name",
      "local": true,
      "quality": 0.72,
      "latency_ms": 850,
      "input_cost_per_million": 0,
      "output_cost_per_million": 0,
      "capabilities": ["text", "json"]
    }
  ]
}
```

Then re-run `llm-pqr choose` with your expected input and output token counts.
The numbers above are an editable example, not a ranking or a claim about any
model. See [Giving useful feedback](docs/giving-useful-feedback.md) if a
constraint, capability label, or output was missing for your setup.

The checked-in example is a **real bounded smoke run**, not a placeholder:

```bash
llm-pqr choose \
  --config examples/models.json \
  --input-tokens 1200 \
  --output-tokens 300
```

The source run used the synthetic `routing-v1` corpus on an Apple M1 Max MBP.
`examples/measured-smoke-20260814.json` records the run ID, corpus and source
artifact hashes, sample counts, rubric pass rates, and median wall-clock latency.
Usage and cost remain `null` because the adapter emitted no machine-readable
usage. Each candidate has only five or six valid responses, below the corpus's
minimum-N gate, so this is reproducible integration evidence—not a model ranking.

With cost disabled because it was unmeasured, and latency/quality weighted
`4/6`, the example selects `sol`:

```json
{
  "estimated_cost_usd": null,
  "score": 0.60335,
  "selected": {
    "id": "sol",
    "local": false,
    "model": "gpt-5.6-sol",
    "provider": "openai-codex"
  }
}
```

Add `--local-only` and every hosted candidate becomes ineligible rather than
receiving a lower privacy score. The measured local candidate is selected:

```bash
llm-pqr choose --config examples/models.json --local-only
```

```json
{
  "excluded": {
    "luna": "not local",
    "sol": "not local",
    "terra": "not local"
  },
  "selected": {
    "id": "local-qwen",
    "local": true,
    "model": "qwen3.6-35b-a3b-local",
    "provider": "local-qwen"
  }
}
```

### Avoid a provider pool that is temporarily unavailable

LLM-PQR never calls a provider or reads credentials. If your application already
knows that a provider is in a rate-limit or quota cooldown, pass that provider
ID as a hard availability constraint before routing:

```python
from llm_pqr import Request

request = Request(
    unavailable_providers=frozenset({"openai-codex"}),
)
decision = router.choose(request)
```

Candidates from an unavailable provider are excluded before weighted scoring,
with the explanation `provider unavailable`. This prevents a known-cooling-down
provider from winning only to fail at request time. Your integration remains
responsible for discovering, expiring, and clearing provider health state.

The values in `examples/models.json` are measured from one bounded smoke run,
not universal rankings. Use the checked-in provenance summary to reproduce the
example, then replace it with measurements and verified prices for your workload.

Create a fresh editable configuration with:

```bash
llm-pqr init --output models.json
```

Require a capability when needed:

```bash
llm-pqr choose --config models.json --require tools
```

Summarize content-free route telemetry before or alongside a full evaluation:

```bash
llm-pqr summarize tests/fixtures/pre-llm-pqr-evals.jsonl
```

The summarizer accepts only `route`, `reason`, `latency_ms`, and `outcome`.
It rejects prompts, responses, identifiers, paths, and every other field.

The command returns JSON containing the selected model, excluded candidates, a score, the estimated cost (when rates are supplied), and normalized priority weights.

## User-controlled configuration

`llm-pqr init` creates an editable JSON file:

```json
{
  "priorities": {"cost": 0.35, "latency": 0.25, "quality": 0.40},
  "models": [
    {
      "id": "local-model",
      "provider": "your-local-runtime",
      "model": "replace-me",
      "local": true,
      "quality": 0.65,
      "latency_ms": 900,
      "input_cost_per_million": 0,
      "output_cost_per_million": 0,
      "capabilities": ["text"]
    }
  ]
}
```

### Fields

- `id`, `provider`, `model`: your labels. No provider is special-cased.
- `local`: a technical locality declaration. `--local-only` excludes every model not marked local.
- `quality`: a 0–1 score from **your** benchmark or evaluation. LLM-PQR does not invent it.
- `latency_ms`: your measured latency estimate.
- `input_cost_per_million`, `output_cost_per_million`: USD token rates you have verified. Omit either if unknown; LLM-PQR reports cost as unknown rather than fabricating it.
- `capabilities`: user-defined labels such as `text`, `tools`, `vision`, or `json`.
- `priorities`: non-negative relative weights. They are normalized automatically, so `8/1/1` is equivalent to `0.8/0.1/0.1`.

## Decision model

1. Apply hard requirements first: `local_only` and required capabilities.
2. Normalize the remaining candidates' declared cost, latency, and quality values.
3. Choose the highest weighted score and explain the result.

Privacy is a constraint, not a score: a non-local candidate cannot win a `--local-only` request. See [Privacy Is a Constraint, Not a Score](docs/privacy-is-a-constraint.md) for the design rationale.

## Important limits

- This release **does not call providers**, send prompts, store credentials, or measure models automatically.
- A `local: true` declaration is user-supplied metadata, not a network-attested guarantee. Production integrations must verify resolved endpoints are local before handling private content.
- Scores and recommendations are conditional on your workloads, model versions, settings, hardware, and measurements. They are not universal rankings.
- Token counts are not cost. Use current model-specific input/output rates and record their source/date in your workflow.

## Development

```bash
uv run --with pytest --with ruff pytest
uv run --with ruff ruff check src tests
uv run --with ruff ruff format --check src tests
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [ROADMAP.md](ROADMAP.md), [SECURITY.md](SECURITY.md), [CHANGELOG.md](CHANGELOG.md), and the prepared [launch notes](LAUNCH_NOTES.md).

## Feedback

If you tried LLM-PQR, please [open a feedback issue](https://github.com/Amazed-Labs/llm-pqr/issues/new?template=first-run-feedback.md)
with one model constraint, capability, or recommendation that did not fit your
setup. Reports about missing constraints are especially useful; do not include
API keys, private prompts, customer data, or internal endpoints.

## Project and attribution

LLM-PQR was created by **Dov Ginsburg** and is maintained by **Amazed Labs**.
The canonical project is [Amazed-Labs/llm-pqr](https://github.com/Amazed-Labs/llm-pqr).

If you use, modify, or redistribute LLM-PQR, please preserve the copyright and
license notice required by the MIT License. For academic or published work, the
repository includes a [`CITATION.cff`](CITATION.cff) file with the preferred
citation.

## License

MIT. Copyright © 2026 AMAZED Labs. See [LICENSE](LICENSE).
