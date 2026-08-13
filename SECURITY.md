# Security policy

## Supported versions

Security fixes are applied to the latest released version.

## Reporting a vulnerability

Please do **not** file public issues for vulnerabilities involving privacy boundaries, configuration parsing, or unsafe routing assumptions. Contact AMAZED Labs privately with a minimal reproduction and impact description.

## Scope and safety model

LLM-PQR v0.1 does not execute model calls, read credentials, or transmit prompts. It selects from user-supplied metadata.

Do not treat `local: true` as proof that a model endpoint is local. Any integration that routes private text must verify locality before provider construction and fail closed if verification fails.
