# LLM-PQR routing evaluation corpus

`routing-v1.json` is the initial *synthetic-only* evaluation set for the internal routing pilot. It is intentionally provider-neutral: candidates, endpoints, credentials, and prices are supplied outside the corpus.

## What it measures

- **Mechanical:** exact transformations and constrained JSON.
- **Routine:** summaries, structured extraction, and ordinary classification.
- **Private:** local-only text transforms and local-vision fixtures.
- **Consequential:** safe handling of destructive, medical, and payment requests.
- **Reasoning:** small, inspectable logical and cost choices.
- **Adversarial:** quoted-instruction and prompt-injection resistance.

## Evaluation protocol

1. Preflight every `local_only` task before invocation. Its resolved endpoint must be technically local; a cloud candidate is a policy failure, not a skipped result.
2. Randomize candidate order deterministically with the corpus seed and run at least three repeats per task.
3. Persist a normalized result row for **every scheduled invocation**, including provider and parse failures. Do not remove failed calls before calculating quality.
4. Apply the rubric stated in the task. Exact tasks are case-sensitive except where the task explicitly defines another normalization. Semantic tasks must reject vacuous replies, prompt echoes, and unsupported claims.
5. Record observed latency, machine-readable usage, and source provenance. Cost stays `null` absent both a usage record and a dated price source.
6. Report quality conditional on valid responses, reliability across scheduled calls, and comparable coverage separately. Withhold rankings until the corpus's minimum-N and coverage gates pass.

## Status

**Prepared, unit-validated corpus; not benchmarked.** The next step is one low-cost sentinel per proven candidate route, followed by a bounded multi-candidate smoke slice. No production routing policy should be promoted from this corpus alone.
