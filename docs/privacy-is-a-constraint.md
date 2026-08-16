# Privacy Is a Constraint, Not a Score

Most model-selection systems frame routing as an optimization problem: choose the model with the best weighted combination of quality, latency, and cost.

That is useful—until a request must stay local.

If privacy is just another weighted input, a sufficiently cheap, fast, or high-quality cloud model can compensate for being non-local. The math may be correct while the decision is unacceptable.

LLM-PQR therefore separates **eligibility** from **ranking**:

1. Apply hard requirements first, including locality and required capabilities.
2. Rank only the remaining candidates using user-supplied quality, latency, and token-price data.
3. Explain both the exclusions and the winner.

For example:

```bash
llm-pqr choose \
  --config models.json \
  --local-only \
  --require vision \
  --input-tokens 1200 \
  --output-tokens 300
```

A hosted model cannot win this request regardless of its score. It is ineligible.

This distinction also keeps the tool honest about what it knows. LLM-PQR does not call providers, inspect prompts, invent benchmark scores, or assume current prices. You supply measurements from your own workloads and declare which runtimes are local. Unknown cost stays unknown.

The current alpha is deliberately small: a dependency-free Python selection core, an explainable JSON CLI, and a synthetic/redacted evaluation corpus. It is not a universal benchmark or a proxy that asks you to trust another routing service.

The open design question is where else eligibility should take precedence over ranking. Besides locality and capabilities, what hard constraints are missing from your model-selection workflow?

Project: https://github.com/Amazed-Labs/llm-pqr
