# Hermes Agent plugin for LLM-PQR

**Status:** alpha. Independently maintained by Amazed Labs.

This is **not** an official Nous Research router. Hermes Agent does not
ship, endorse, or depend on this plugin. The plugin *consumes* the
`llm-pqr` library the same way any other application would.

It exists so you can opt into policy-based model selection at Hermes
message ingress without putting a third-party product into Hermes core.

## What it does

Hermes skills are markdown. Observer hooks such as `pre_api_request`
cannot change the model (their return value is ignored). This plugin
therefore registers middleware:

- `llm_request` — if an opt-in config exists, call `Router.choose` and
  return `{"request": ..., "source": "llm-pqr", "reason": "..."}`.
- `llm_execution` — when no candidate is eligible, **do not** call
  `next_call`. Return a refusal-shaped response so the original hosted
  model is not invoked.

If `$HERMES_HOME/llm-pqr.json`, `~/.hermes/llm-pqr.json`, and
`LLM_PQR_CONFIG` are all missing, both callbacks no-op and Hermes keeps
its current model.

## Honest limits

- Fail-closed "no eligible route" is a **plugin-layer** behavior. It is
  not a Hermes-core guarantee. A later Hermes fallback, retry, or
  another plugin could still reach a provider. The refusal object is a
  best-effort match to public Chat Completions / Anthropic / Codex
  response shapes; if Hermes changes those shapes, the refusal may be
  treated as invalid and retried.
- Middleware that *raises* is fail-open in Hermes. This plugin catches
  exceptions (including `Router.choose` `ValueError`) so a bug does not
  crash the agent. Unexpected errors therefore leave the original model
  in place.
- Token estimates are coarse character-length counts (`chars // 4`).
  They are not tokenizer-accurate. Message text is never copied into
  `llm_pqr.Request`.
- A `local: true` flag is a user declaration, not proof that the
  resolved endpoint is local.
- The plugin does not infer privacy, risk, or capability needs from
  prompt text.
- Continuity: only `model` is rewritten, plus `provider` / `base_url`
  when those keys already exist on the request. Tools, identity,
  memory, and conversation are left intact.
- No telemetry, phone-home, or usage tracking.

## Install / copy

The plugin is a directory, not part of the `llm-pqr` wheel. Copy it:

```bash
git clone https://github.com/Amazed-Labs/llm-pqr.git
cp -R llm-pqr/integrations/hermes-plugin ~/.hermes/plugins/llm-pqr
pip install 'llm-pqr>=0.3.1,<0.4'
hermes plugins enable llm-pqr
```

`plugin.yaml` names the plugin `llm-pqr` (version 0.1.0, author Amazed
Labs). Confirm with `hermes plugins list` and `hermes plugins doctor ~/.hermes/plugins/llm-pqr`.

Keep the library importable the same way this repository already does:
install `llm-pqr` into the Hermes Python environment. Do not vendor
Hermes Agent, and do not clone `NousResearch/hermes-agent` to use this
plugin.

## Write the config

Copy the example and replace candidates with **your** measurements:

```bash
cp ~/.hermes/plugins/llm-pqr/examples/llm-pqr.json ~/.hermes/llm-pqr.json
```

Lookup order:

1. `$LLM_PQR_CONFIG` (must be an existing file)
2. `$HERMES_HOME/llm-pqr.json`
3. `~/.hermes/llm-pqr.json`

Shape — same as the LLM-PQR CLI `models.json`:

```json
{
  "local_only": false,
  "require": ["tools"],
  "unavailable_providers": [],
  "priorities": {"cost": 0, "latency": 4, "quality": 6},
  "models": [
    {
      "id": "local-fast",
      "provider": "local-runtime",
      "model": "my-local-model-id",
      "local": true,
      "quality": 0.7,
      "latency_ms": 800,
      "capabilities": ["text", "json"],
      "base_url": "http://127.0.0.1:11434/v1"
    }
  ]
}
```

`local_only`, `require`, and `unavailable_providers` are plugin-only
keys that become `llm_pqr.Request` fields. Per-model `base_url` is also
plugin-only and is applied only when the Hermes request already has
`base_url`. Put Hermes-compatible model IDs in `model`.

Do not put API keys or prompts in this file.

## Slash command

`/pqr` prints the last content-free `Decision`: selected id, provider,
model, locality, exclusions, score, and estimated cost when known. It
never prints prompts, messages, or session IDs.

## Bundled skill

`skills/configure/SKILL.md` is registered via `ctx.register_skill`. Load
it in Hermes as the namespaced skill `llm-pqr:configure`.

## Non-goals

- Ranking models for the internet, or claiming a universal winner
- Replacing Hermes fallbacks, tools, memory, identity, or sessions
- Sending prompts into LLM-PQR
- Credential storage, provider authentication, or a hosted routing service
- Treating privacy as a weighted score
- Shipping inside `NousResearch/hermes-agent`

## Testing

Adapter unit tests live in this repository as
`tests/test_hermes_plugin_adapter.py`. They load the plugin by file path and
do not install Hermes Agent.

## Pitch path (not a usage tracker)

If you find this useful, the documented promotion path for third-party
Hermes plugins is the Nous Research Discord channel
`#plugins-skills-and-skins`, and later the community
`hermes-plugin-index`. That is an introduction, not telemetry.

## Attribution

MIT. Copyright © 2026 AMAZED Labs. Author in `plugin.yaml`: Amazed Labs.
Created by Dov Ginsburg. See the repository [`CITATION.cff`](../../CITATION.cff)
and [`LICENSE`](../../LICENSE).

LLM-PQR: https://github.com/Amazed-Labs/llm-pqr
Hermes plugin docs (public): https://hermes-agent.nousresearch.com/docs/developer-guide/plugins
Middleware contract: https://github.com/NousResearch/hermes-agent/blob/main/docs/middleware/README.md
