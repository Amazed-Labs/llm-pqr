# PQR continuity boundary

LLM-PQR selects an eligible model from user-supplied measurements and constraints. It is a **selection component**, not an agent-runtime sandbox.

## Consumer rule

A consumer that uses LLM-PQR—or an equivalent policy router—should treat the route as a model-selection result only. Selecting a different model must not implicitly remove the agent's configured:

- identity and standing instructions;
- relevant conversation context;
- memory and owner-authorized preferences;
- tools and other normal runtime capabilities.

A consumer may deliberately run a request in an isolated environment when that is a separately defined requirement—for example, bounded analysis of untrusted content. That isolation must be explicit in the consumer's runtime policy, such as `context_mode: isolated`; it is never implied by the selected provider, model, locality, cost, or capability score.

## Separation of responsibilities

LLM-PQR does not send prompts, run agents, or manage context, tools, memory, credentials, or provider sessions. Those are responsibilities of the consuming application. Keeping this boundary explicit makes routing auditable and prevents a cost or privacy routing decision from accidentally changing agent behavior.
