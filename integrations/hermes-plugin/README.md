# Unofficial Hermes plugin for LLM-PQR

**Status:** alpha. Independently maintained by Amazed Labs. This is **not**
an official Nous Research router. Hermes does not ship, endorse, or depend
on this plugin.

Policy routing at Hermes provider ingress: keep private prompts on a local
model (`local_only`), require a capability floor (`require`), or skip a
provider in cooldown (`unavailable_providers`) — before the hosted call.
If no eligible route exists, this plugin skips that call instead of
weakening the constraint.

Missing config stays a no-op for provider calls. `/pqr` still tells you
the plugin is idle and how to write a file, so you never have to wonder
whether routing is on.

## 60-second first run

```bash
hermes plugins install Amazed-Labs/llm-pqr/integrations/hermes-plugin
pip install 'llm-pqr>=0.3.1,<0.4'
hermes plugins enable llm-pqr
cp ~/.hermes/plugins/llm-pqr/examples/local-only.json ~/.hermes/llm-pqr.json
# edit REPLACE_* placeholders; keep local_only true to stay off hosted providers
```

In a Hermes session, type `/pqr` (or ask the agent to check routing — it
can call the `pqr_status` tool).

| `/pqr` state | Meaning |
|---|---|
| **idle** | No config file. Provider calls are unchanged. Status says where to write one. |
| **ready** | Config loaded. The next provider call will be routed. |
| **live** | Last turn selected a route (id, reason, exclusions). |
| **blocked** | Last turn skipped the hosted call, or the config file is broken. |

Then send a normal message and `/pqr` again. You should see **live** with
the selected id, or **blocked** with a reason such as missing `base_url`
or no eligible candidate.

For local + hosted candidates, copy `examples/mixed.json` instead. Both
starters are templates with placeholders. They are not measurements and
not a ranking.

If you prefer a local copy of the plugin:

```bash
git clone https://github.com/Amazed-Labs/llm-pqr.git
cp -R llm-pqr/integrations/hermes-plugin ~/.hermes/plugins/llm-pqr
pip install 'llm-pqr>=0.3.1,<0.4'
hermes plugins enable llm-pqr
```

`plugin.yaml` names the plugin `llm-pqr` (version 0.2.0, author Amazed
Labs). Confirm with `hermes plugins list` and
`hermes plugins doctor ~/.hermes/plugins/llm-pqr`.

This plugin is not listed in `hermes-plugin-index`. Use the
`owner/repo/subdir` install command above. Do not vendor Hermes Agent,
and do not clone `NousResearch/hermes-agent` to use the plugin.

## Config lookup

1. `$LLM_PQR_CONFIG` (must be an existing file)
2. `$HERMES_HOME/llm-pqr.json`
3. `~/.hermes/llm-pqr.json`

Shape — same as the LLM-PQR CLI `models.json`, plus plugin-only keys:

```json
{
  "local_only": true,
  "require": ["tools"],
  "unavailable_providers": [],
  "priorities": {"cost": 0, "latency": 0, "quality": 1},
  "models": [
    {
      "id": "local",
      "provider": "openai-compatible",
      "model": "REPLACE_WITH_YOUR_LOCAL_MODEL_ID",
      "local": true,
      "capabilities": ["text", "tools"],
      "base_url": "http://127.0.0.1:11434/v1"
    }
  ]
}
```

`local_only`, `require`, and `unavailable_providers` become
`llm_pqr.Request` fields. Per-model `base_url` is also plugin-only: for a
local candidate it is always written onto the rewritten request. A local
candidate without a usable `base_url` is refused for that turn. Put
Hermes-compatible model IDs in `model`.

Do not put API keys or prompts in this file. Replace placeholders with
**your** models. Do not treat example numbers in the LLM-PQR repo smoke
files as your measurements.

## What the middleware does

Hermes skills are markdown. Observer hooks such as `pre_api_request`
cannot change the model (their return value is ignored). This plugin
registers middleware:

- `llm_request` — if an opt-in config exists, call `Router.choose` and
  return `{"request": ..., "source": "llm-pqr", "reason": "..."}`.
- `llm_execution` — when no candidate is eligible, **do not** call
  `next_call`. Return a refusal-shaped response so the original hosted
  model is not invoked.

Callbacks accept Hermes kwargs (`request`, `original_request`,
`next_call`). If `$HERMES_HOME/llm-pqr.json`, `~/.hermes/llm-pqr.json`,
and `LLM_PQR_CONFIG` are all missing, both callbacks no-op and Hermes
keeps its current model. Status still reports **idle**.

## Slash command and tool

`/pqr` prints idle vs live, the config path used (or missing), last
selected id/reason/exclusions, and last block reason. It never prints
prompts, messages, or session IDs.

`pqr_status` is the same snapshot as a plugin tool so the agent can tell
you routing is idle without guessing. It does not send prompt text to
`Router.choose`.

## Bundled skill

`skills/configure/SKILL.md` is registered via `ctx.register_skill`. Load
it in Hermes as the namespaced skill `llm-pqr:configure`.

## Honest limits

- Fail-closed "no eligible route", broken config, unexpected routing
  errors, block-pop failures, and a lost block record are **plugin-layer**
  behaviors. They are not a Hermes-core guarantee. A later Hermes fallback, retry, or
  another plugin could still reach a provider. The refusal object is a
  best-effort match to public Chat Completions / Anthropic / Codex
  response shapes; if Hermes changes those shapes, the refusal may be
  treated as invalid and retried.
- Middleware that *raises* is fail-open in Hermes core. This plugin
  catches exceptions (including `Router.choose` `ValueError` and unexpected
  errors) so a bug does not crash the agent **and** does not fall through
  to the original hosted model when an opt-in config is present. Missing
  config remains a no-op for the provider call.
- Token estimates are coarse character-length counts (`chars // 4`).
  They are not tokenizer-accurate. Message text is never copied into
  `llm_pqr.Request`.
- A `local: true` flag is a user declaration, not proof that the
  resolved endpoint is local.
- The plugin does not infer privacy, risk, or capability needs from
  prompt text.
- Continuity: `model` is rewritten. For a local candidate, `provider`
  and `base_url` are always written onto the request so Hermes does not
  keep its default hosted provider. If a local candidate has no usable
  `base_url`, that turn is refused. Hosted candidates may only need a
  model rewrite. Tools, identity, memory, and conversation are left intact.
- No telemetry, phone-home, or usage tracking.
- No universal ranking. Starter templates are not your measurements.

## Non-goals

- Ranking models for the internet, or claiming a universal winner
- Replacing Hermes fallbacks, tools, memory, identity, or sessions
- Sending prompts into LLM-PQR
- Credential storage, provider authentication, or a hosted routing service
- Treating privacy as a weighted score
- Shipping inside `NousResearch/hermes-agent`
- Listing in `hermes-plugin-index`

## Testing

Adapter unit tests live in this repository as
`tests/test_hermes_plugin_adapter.py`. They load the plugin by file path and
do not install Hermes Agent.

## Pitch path (not a usage tracker)

If you find this useful, the documented promotion path for third-party
Hermes plugins is the Nous Research Discord channel
`#plugins-skills-and-skins`. That is an introduction, not telemetry.
This plugin is not listed in `hermes-plugin-index`.

## Attribution

MIT. Copyright © 2026 AMAZED Labs. Author in `plugin.yaml`: Amazed Labs.
Created by Dov Ginsburg. See the repository [`CITATION.cff`](../../CITATION.cff)
and [`LICENSE`](../../LICENSE).

LLM-PQR: https://github.com/Amazed-Labs/llm-pqr
Hermes plugin docs (public): https://hermes-agent.nousresearch.com/docs/developer-guide/plugins
Middleware contract: https://github.com/NousResearch/hermes-agent/blob/main/docs/middleware/README.md
