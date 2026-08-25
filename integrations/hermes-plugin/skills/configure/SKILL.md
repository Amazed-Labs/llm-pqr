---
name: configure
description: Configure the unofficial Amazed Labs LLM-PQR plugin for Hermes Agent.
---

# Configure LLM-PQR for Hermes

This skill belongs to the independently maintained `llm-pqr` plugin by Amazed Labs. It is **not** an official Nous Research router. Hermes does not ship or require this plugin.

## Enable routing

1. Copy this plugin directory to `~/.hermes/plugins/llm-pqr/` (or `$HERMES_HOME/plugins/llm-pqr/`).
2. Install the library the plugin consumes: `pip install 'llm-pqr>=0.3.1,<0.4'`.
3. Enable the plugin: `hermes plugins enable llm-pqr`.
4. Write an opt-in config file. Without it the plugin is a no-op and Hermes keeps its current model.

Config lookup order:

1. `$LLM_PQR_CONFIG`
2. `$HERMES_HOME/llm-pqr.json`
3. `~/.hermes/llm-pqr.json`

## Config shape

Use the same JSON as `llm-pqr` `models.json`: `priorities` plus a `models` list of measured candidates. Plugin-only keys (optional):

- `local_only` (boolean) — hard-exclude every non-local candidate
- `require` (string list) — required capability labels such as `tools` or `vision`
- `unavailable_providers` (string list) — hard-exclude those provider IDs
- per-model `base_url` — applied only when the Hermes request already has a `base_url` key

Do not put prompts, credentials, or session IDs in this file. LLM-PQR never infers privacy from message text.

Copy `examples/llm-pqr.json` from this plugin and replace every candidate with measurements from your workload.

## What the plugin changes

On each provider call, `llm_request` middleware may rewrite `model`, and `provider` / `base_url` only if those keys already exist. Tools, identity, memory, and conversation are left intact.

If no candidate is eligible, `llm_execution` skips the provider call and returns a refusal-shaped response. That fail-closed behavior is plugin-layer only, not a Hermes-core guarantee.

## Inspect the last decision

In a Hermes session, `/pqr` prints the last content-free decision: selected id, exclusions, and score. It never prints prompts.

## Non-goals

- Not an official Nous router or usage tracker
- Does not call providers, store credentials, or phone home
- Does not rank models for you; you supply measurements
- A `local: true` flag is a declaration, not endpoint attestation
