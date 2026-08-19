# Giving useful feedback

LLM-PQR is an alpha selection core. The most useful feedback is a small,
reproducible description of a decision it could not express correctly.

## Please include

- the LLM-PQR version and Python version;
- an anonymized candidate configuration (model/provider labels may be generic);
- the hard constraint or trade-off you needed, such as `local-only`, vision,
  tools, context length, latency ceiling, or structured output;
- what you expected to be selected or excluded, and what happened instead.

## Please do not include

- API keys, tokens, passwords, or connection strings;
- private prompts, customer data, patient data, or source documents;
- internal hostnames, private URLs, or identifying telemetry.

Use the [first-run feedback issue template](https://github.com/Amazed-Labs/llm-pqr/issues/new?template=first-run-feedback.md)
for a short report. A minimal report is enough: one candidate set, one missing
constraint, and one expected decision.

LLM-PQR does not call providers or collect telemetry. Feedback is public only
when you choose to post an issue.