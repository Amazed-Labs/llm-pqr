# LLM-PQR

**Test your models. Pick with evidence.**

LLM-PQR is a small, provider-neutral tool for choosing among *your* models. You declare each model's measured quality, latency, token prices, capabilities, and whether it is local. Then you choose how much you value cost, speed, and quality. LLM-PQR produces an explainable recommendation without calling a provider or handling credentials.

> **Status:** alpha. The first release is a deterministic selection core and CLI, not an autonomous router or a universal benchmark.

## Why

Model choice is contextual. A low-cost local model may be ideal for private transformations; a stronger hosted model may be worthwhile for complex work. LLM-PQR keeps that decision in user-controlled data rather than hard-coding vendor tiers or marketing labels.

## Quick start

```bash
pip install llm-pqr
llm-pqr init --output models.json
# Edit models.json with your models and measured values.
llm-pqr choose --config models.json --input-tokens 1200 --output-tokens 300
```

Require privacy/locality or a capability when needed:

```bash
llm-pqr choose --config models.json --local-only --require text
llm-pqr choose --config models.json --require tools
```

The command returns JSON containing the selected model, excluded candidates, a score, the estimated cost (when rates are supplied), and the normalized priority weights.

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

Privacy is a constraint, not a score: a non-local candidate cannot win a `--local-only` request.

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

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and [CHANGELOG.md](CHANGELOG.md).

## License

MIT. See [LICENSE](LICENSE).
