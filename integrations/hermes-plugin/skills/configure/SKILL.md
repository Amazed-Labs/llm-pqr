---
name: configure
description: Enable unofficial Amazed Labs LLM-PQR routing in Hermes and verify it with /pqr.
---

# Configure LLM-PQR for Hermes

Unofficial Amazed Labs plugin. Not a Nous Research router.

## Do this

1. Install: `hermes plugins install Amazed-Labs/llm-pqr/integrations/hermes-plugin`
2. Library: `pip install 'llm-pqr>=0.3.1,<0.4'`
3. Enable: `hermes plugins enable llm-pqr`
4. Write a config (templates, not measurements):

```bash
cp ~/.hermes/plugins/llm-pqr/examples/local-only.json ~/.hermes/llm-pqr.json
# or: examples/mixed.json for local + hosted
```

Replace every `REPLACE_*` placeholder. Keep `local_only: true` if prompts
must stay off hosted providers. Local candidates need a real `base_url`.

5. In the session, type `/pqr`.

- **idle** — no file found. Provider calls are unchanged. Write the JSON above.
- **ready** — config loaded; send a message, then `/pqr` again.
- **live** — last turn selected an id (reason and exclusions are listed).
- **blocked** — that turn skipped the hosted call. Read the block reason.

The `pqr_status` tool reports the same snapshot. Neither `/pqr` nor the
tool sends prompt text to the router.

Lookup order: `$LLM_PQR_CONFIG`, then `$HERMES_HOME/llm-pqr.json`, then
`~/.hermes/llm-pqr.json`.

## Common failures

| What you see | What to do |
|---|---|
| idle / no config file | Copy a starter to `~/.hermes/llm-pqr.json`. Missing config never starts routing. |
| local candidate has no usable base_url | Set `base_url` on that model (for example `http://127.0.0.1:11434/v1`). |
| no eligible candidates | Relax `local_only` / `require` / `unavailable_providers`, or add a matching model. |
| invalid JSON / unreadable / missing models | Fix the file. Broken config fails closed (skips the hosted call) and shows up in `/pqr`. |

Do not put prompts or API keys in the config. A `local: true` flag is a
declaration, not proof the endpoint is local.
