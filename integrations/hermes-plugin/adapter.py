"""Content-free LLM-PQR adapter for a Hermes Agent plugin.

This module must not import Hermes. Callers pass duck-typed middleware
payloads. Prompts, messages, conversation history, attachments, session
IDs, and credentials are never forwarded into ``llm_pqr.Router``.
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Callable, Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from llm_pqr import ModelCandidate, Priorities, Request, Router

PLUGIN_NAME = "llm-pqr"
PLUGIN_VERSION = "0.1.0"
NO_ELIGIBLE_MESSAGE = "no eligible candidates; relax requirements or add a compatible model"
LOCAL_MISSING_BASE_URL_MESSAGE = "local candidate has no usable base_url"
ROUTING_FAILED_MESSAGE = "routing failed"
REFUSAL_PREFIX = (
    "LLM-PQR refused this turn: no eligible route matched the configured "
    "constraints. The original hosted model was not invoked. This fail-closed "
    "behavior is enforced by the plugin, not by Hermes core."
)
_MODEL_FIELDS = frozenset(
    {
        "id",
        "provider",
        "model",
        "local",
        "quality",
        "latency_ms",
        "input_cost_per_million",
        "output_cost_per_million",
        "capabilities",
    }
)
_CONTENT_KEYS = frozenset(
    {
        "messages",
        "input",
        "contents",
        "prompt",
        "system",
        "conversation",
        "history",
        "attachments",
        "files",
        "image",
        "image_url",
        "session_id",
        "task_id",
        "user",
        "api_key",
        "authorization",
        "headers",
        "token",
        "credentials",
    }
)


def resolve_config_path(
    *,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path | None:
    """Return the opt-in config path, or None when routing should no-op."""

    env = environ if environ is not None else os.environ
    explicit = (env.get("LLM_PQR_CONFIG") or "").strip()
    if explicit:
        path = Path(explicit).expanduser()
        return path if path.is_file() else None
    hermes_home = (env.get("HERMES_HOME") or "").strip()
    if hermes_home:
        path = Path(hermes_home).expanduser() / "llm-pqr.json"
        if path.is_file():
            return path
    root = home if home is not None else Path.home()
    fallback = root / ".hermes" / "llm-pqr.json"
    return fallback if fallback.is_file() else None


def load_plugin_config(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict) or not isinstance(payload.get("models"), list):
        raise TypeError("config requires a 'models' list")
    return payload


def candidates_from_config(
    payload: Mapping[str, Any],
) -> tuple[list[ModelCandidate], dict[str, dict[str, str]]]:
    candidates: list[ModelCandidate] = []
    extras: dict[str, dict[str, str]] = {}
    for row in payload["models"]:
        if not isinstance(row, dict):
            raise TypeError("each model entry must be an object")
        fields = {key: row[key] for key in _MODEL_FIELDS if key in row}
        if "capabilities" in fields:
            fields["capabilities"] = frozenset(fields["capabilities"])
        candidate = ModelCandidate(**fields)
        extra: dict[str, str] = {}
        base_url = row.get("base_url")
        if isinstance(base_url, str) and base_url.strip():
            extra["base_url"] = base_url.strip()
        extras[candidate.id] = extra
        candidates.append(candidate)
    return candidates, extras


def request_from_config(
    payload: Mapping[str, Any],
    *,
    estimated_input_tokens: int,
    estimated_output_tokens: int,
) -> Request:
    require = payload.get("require") or payload.get("required_capabilities") or []
    unavailable = payload.get("unavailable_providers") or []
    if isinstance(require, str):
        require = [require]
    if isinstance(unavailable, str):
        unavailable = [unavailable]
    return Request(
        local_only=bool(payload.get("local_only", False)),
        required_capabilities=frozenset(require),
        unavailable_providers=frozenset(unavailable),
        estimated_input_tokens=estimated_input_tokens,
        estimated_output_tokens=estimated_output_tokens,
    )


def estimate_tokens(request: Mapping[str, Any] | None) -> tuple[int, int]:
    """Coarse length-derived counts. Message text never leaves this function."""

    payload = request if isinstance(request, Mapping) else {}
    chars = _message_chars(payload.get("messages"))
    if chars == 0:
        chars = _message_chars(payload.get("input"))
    estimated_input = max(1, chars // 4) if chars else 1_000
    output = payload.get("max_tokens")
    if output is None:
        output = payload.get("max_completion_tokens")
    if isinstance(output, bool) or not isinstance(output, int) or output < 0:
        estimated_output = 250
    else:
        estimated_output = output
    return estimated_input, estimated_output


def content_free_decision(decision: Any) -> dict[str, Any]:
    candidate = decision.candidate
    return {
        "selected": {
            "id": candidate.id,
            "provider": candidate.provider,
            "model": candidate.model,
            "local": candidate.local,
        },
        "reason": decision.reason,
        "score": decision.score,
        "estimated_cost_usd": decision.estimated_cost_usd,
        "excluded": dict(decision.excluded),
        "explanation": decision.explain(),
    }


def content_free_block(*, reason: str, excluded: Mapping[str, str] | None = None) -> dict[str, Any]:
    return {
        "selected": None,
        "reason": reason,
        "score": None,
        "estimated_cost_usd": None,
        "excluded": dict(excluded or {}),
        "explanation": reason,
    }


def apply_candidate(
    request: Mapping[str, Any],
    candidate: ModelCandidate,
    extra: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Rewrite the selected model. Local routes always set provider and base_url.

    Hermes payloads typically have only ``model``. A local rewrite that omits
    ``provider`` / ``base_url`` would leave Hermes on its default hosted
    provider. Hosted candidates may still need only a model rewrite.
    """

    updated = dict(request)
    updated["model"] = candidate.model
    extra = extra or {}
    if candidate.local:
        base_url = extra.get("base_url")
        if not base_url:
            raise ValueError(LOCAL_MISSING_BASE_URL_MESSAGE)
        updated["provider"] = candidate.provider
        updated["base_url"] = base_url
        return updated
    if "provider" in updated:
        updated["provider"] = candidate.provider
    if "base_url" in updated and extra.get("base_url"):
        updated["base_url"] = extra["base_url"]
    return updated


def refusal_response(message: str, *, api_mode: str | None = None) -> Any:
    """Return a provider-shaped refusal without calling the downstream provider.

    Public Hermes docs say execution middleware should return the same shape
    the active provider adapter expects. The exact object differs by
    ``api_mode``. This helper covers the shapes documented or visible in
    public transport validators. It is not a Hermes-core guarantee: a later
    Hermes fallback chain could still run after this plugin returns.
    """

    text = f"{REFUSAL_PREFIX} {message}".strip()
    mode = (api_mode or "chat_completions").strip().lower()
    if mode == "anthropic_messages":
        return SimpleNamespace(
            id="llm-pqr-blocked",
            model="llm-pqr",
            role="assistant",
            content=[SimpleNamespace(type="text", text=text)],
            stop_reason="end_turn",
            usage=SimpleNamespace(input_tokens=0, output_tokens=0),
        )
    if mode == "codex_responses":
        return SimpleNamespace(
            id="llm-pqr-blocked",
            model="llm-pqr",
            status="completed",
            output_text=text,
            output=[
                SimpleNamespace(
                    type="message",
                    role="assistant",
                    content=[SimpleNamespace(type="output_text", text=text)],
                )
            ],
            usage=SimpleNamespace(input_tokens=0, output_tokens=0),
        )
    return SimpleNamespace(
        id="llm-pqr-blocked",
        model="llm-pqr",
        object="chat.completion",
        choices=[
            SimpleNamespace(
                index=0,
                finish_reason="stop",
                message=SimpleNamespace(
                    role="assistant",
                    content=text,
                    tool_calls=None,
                    refusal=None,
                ),
            )
        ],
        usage=SimpleNamespace(prompt_tokens=0, completion_tokens=0, total_tokens=0),
    )


def format_last_decision(snapshot: Mapping[str, Any] | None) -> str:
    if not snapshot:
        return "LLM-PQR: no decision yet. Enable the plugin and add ~/.hermes/llm-pqr.json."
    return json.dumps(snapshot, indent=2, sort_keys=True)


def _message_chars(value: Any) -> int:
    """Count visible text only. Skip binary, credential, and identity fields."""

    if value is None:
        return 0
    if isinstance(value, str):
        return len(value)
    if isinstance(value, Mapping):
        if "content" in value:
            return _message_chars(value.get("content"))
        if "text" in value:
            return _message_chars(value.get("text"))
        total = 0
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in _CONTENT_KEYS or lowered in {
                "image_url",
                "image",
                "data",
                "source",
                "file",
            }:
                continue
            total += _message_chars(item)
        return total
    if isinstance(value, (list, tuple)):
        return sum(_message_chars(item) for item in value)
    return 0


def _eligibility_exclusions(candidates: list[ModelCandidate], request: Request) -> dict[str, str]:
    excluded: dict[str, str] = {}
    for candidate in candidates:
        if candidate.provider in request.unavailable_providers:
            excluded[candidate.id] = "provider unavailable"
        elif request.local_only and not candidate.local:
            excluded[candidate.id] = "not local"
        elif not request.required_capabilities.issubset(candidate.capabilities):
            excluded[candidate.id] = "missing required capabilities"
    return excluded


class RoutingAdapter:
    """Thread-safe adapter used by Hermes middleware callbacks."""

    def __init__(
        self,
        *,
        environ: Mapping[str, str] | None = None,
        home: Path | None = None,
        choose: Callable[[Router, Request], Any] | None = None,
    ) -> None:
        self._environ = environ
        self._home = home
        self._choose = choose or (lambda router, request: router.choose(request))
        self._lock = threading.Lock()
        self._last_decision: dict[str, Any] | None = None
        self._blocks: dict[str, dict[str, Any]] = {}

    def last_decision(self) -> dict[str, Any] | None:
        with self._lock:
            return None if self._last_decision is None else dict(self._last_decision)

    def on_llm_request(
        self, request: Mapping[str, Any] | None = None, **kwargs: Any
    ) -> dict[str, Any] | None:
        try:
            return self._on_llm_request(request if isinstance(request, Mapping) else {}, **kwargs)
        except Exception as exc:
            self._fail_closed(exc, **kwargs)
            return None

    def on_llm_execution(
        self,
        request: Mapping[str, Any] | None = None,
        next_call: Callable[[Any], Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        try:
            block = self._pop_block(**kwargs)
        except Exception:
            self._fail_closed(RuntimeError("failed to read routing block"), **kwargs)
            return self._refusal(ROUTING_FAILED_MESSAGE, **kwargs)
        if block is not None:
            return self._refusal(str(block.get("reason") or NO_ELIGIBLE_MESSAGE), **kwargs)
        if next_call is None:
            return None
        return next_call(request)

    def _on_llm_request(self, request: Mapping[str, Any], **kwargs: Any) -> dict[str, Any] | None:
        path = resolve_config_path(environ=self._environ, home=self._home)
        if path is None:
            return None
        try:
            payload = load_plugin_config(path)
            candidates, extras = candidates_from_config(payload)
            input_tokens, output_tokens = estimate_tokens(request)
            pqr_request = request_from_config(
                payload,
                estimated_input_tokens=input_tokens,
                estimated_output_tokens=output_tokens,
            )
            router = Router(candidates, Priorities(**payload.get("priorities", {})))
        except Exception as exc:
            self._fail_closed(exc, **kwargs)
            return None
        try:
            decision = self._choose(router, pqr_request)
            rewritten = apply_candidate(
                request, decision.candidate, extras.get(decision.candidate.id)
            )
        except ValueError as exc:
            excluded = _eligibility_exclusions(candidates, pqr_request)
            snapshot = content_free_block(reason=str(exc) or NO_ELIGIBLE_MESSAGE, excluded=excluded)
            self._record_block(snapshot, **kwargs)
            return None
        except Exception as exc:
            self._fail_closed(exc, **kwargs)
            return None
        snapshot = content_free_decision(decision)
        self._store_decision(snapshot)
        self._clear_block(**kwargs)
        return {
            "request": rewritten,
            "source": PLUGIN_NAME,
            "reason": snapshot["explanation"],
        }

    def _fail_closed(self, exc: BaseException, **kwargs: Any) -> None:
        snapshot = content_free_block(reason=str(exc) or ROUTING_FAILED_MESSAGE)
        self._record_block(snapshot, **kwargs)

    def _record_block(self, snapshot: Mapping[str, Any], **kwargs: Any) -> None:
        try:
            self._store_decision(snapshot)
            self._set_block(snapshot, **kwargs)
        except Exception:
            return

    def _refusal(self, message: str, **kwargs: Any) -> Any:
        try:
            return refusal_response(message, api_mode=kwargs.get("api_mode"))
        except Exception:
            return refusal_response(NO_ELIGIBLE_MESSAGE)

    def _correlation_key(self, **kwargs: Any) -> str:
        for key in ("api_request_id", "turn_id", "task_id"):
            value = kwargs.get(key)
            if value:
                return f"{key}:{value}"
        return "_"

    def _store_decision(self, snapshot: Mapping[str, Any]) -> None:
        with self._lock:
            self._last_decision = dict(snapshot)

    def _set_block(self, snapshot: Mapping[str, Any], **kwargs: Any) -> None:
        with self._lock:
            self._blocks[self._correlation_key(**kwargs)] = dict(snapshot)

    def _clear_block(self, **kwargs: Any) -> None:
        with self._lock:
            self._blocks.pop(self._correlation_key(**kwargs), None)

    def _pop_block(self, **kwargs: Any) -> dict[str, Any] | None:
        with self._lock:
            return self._blocks.pop(self._correlation_key(**kwargs), None)
