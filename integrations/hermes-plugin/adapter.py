"""Content-free LLM-PQR adapter for a Hermes Agent plugin.

This module must not import Hermes. Callers pass duck-typed middleware
payloads. Prompts, messages, conversation history, attachments, session
IDs, and credentials are never forwarded into ``llm_pqr.Router``.
"""

from __future__ import annotations

import json
import os
import threading
from collections import deque
from collections.abc import Callable, Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from llm_pqr import ModelCandidate, Priorities, Request, Router

PLUGIN_NAME = "llm-pqr"
PLUGIN_VERSION = "0.2.0"
NO_ELIGIBLE_MESSAGE = "no eligible candidates; relax requirements or add a compatible model"
LOCAL_MISSING_BASE_URL_MESSAGE = "local candidate has no usable base_url"
ROUTING_FAILED_MESSAGE = "routing failed"
CONFIG_WRITE_HINT = (
    "Copy a starter template (placeholders, not measurements), then /pqr again:\n"
    "  cp ~/.hermes/plugins/llm-pqr/examples/local-only.json ~/.hermes/llm-pqr.json\n"
    "  # or: examples/mixed.json for local + hosted candidates\n"
    "Without a config file, this plugin does not change provider calls."
)
_BLOCK_MARK = "_llm_pqr_block"
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

    lookup = describe_config_lookup(environ=environ, home=home)
    if not lookup["found"] or not lookup["path"]:
        return None
    path = Path(lookup["path"])
    return path if path.is_file() else None


def describe_config_lookup(
    *,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> dict[str, Any]:
    """Content-free lookup for status. Does not start routing."""

    env = environ if environ is not None else os.environ
    root = home if home is not None else Path.home()
    looked_for: list[dict[str, Any]] = []

    explicit = (env.get("LLM_PQR_CONFIG") or "").strip()
    if explicit:
        path = Path(explicit).expanduser()
        present = path.is_file()
        looked_for.append({"source": "LLM_PQR_CONFIG", "path": str(path), "present": present})
        if present:
            return {
                "found": True,
                "path": str(path),
                "source": "LLM_PQR_CONFIG",
                "looked_for": looked_for,
                "missing_reason": None,
            }
        return {
            "found": False,
            "path": str(path),
            "source": "LLM_PQR_CONFIG",
            "looked_for": looked_for,
            "missing_reason": f"LLM_PQR_CONFIG is set to {path} but that file does not exist",
        }

    hermes_home = (env.get("HERMES_HOME") or "").strip()
    if hermes_home:
        path = Path(hermes_home).expanduser() / "llm-pqr.json"
        present = path.is_file()
        looked_for.append({"source": "HERMES_HOME", "path": str(path), "present": present})
        if present:
            return {
                "found": True,
                "path": str(path),
                "source": "HERMES_HOME",
                "looked_for": looked_for,
                "missing_reason": None,
            }
    else:
        looked_for.append({"source": "HERMES_HOME", "path": None, "present": False})

    fallback = root / ".hermes" / "llm-pqr.json"
    present = fallback.is_file()
    looked_for.append({"source": "default", "path": str(fallback), "present": present})
    if present:
        return {
            "found": True,
            "path": str(fallback),
            "source": "default",
            "looked_for": looked_for,
            "missing_reason": None,
        }
    return {
        "found": False,
        "path": None,
        "source": None,
        "looked_for": looked_for,
        "missing_reason": "no config file found",
    }


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
        raw = extra.get("base_url")
        base_url = raw.strip() if isinstance(raw, str) else ""
        if not base_url:
            raise ValueError(LOCAL_MISSING_BASE_URL_MESSAGE)
        updated["provider"] = candidate.provider
        updated["base_url"] = base_url
        return updated
    if "provider" in updated:
        updated["provider"] = candidate.provider
    hosted_base = extra.get("base_url")
    if isinstance(hosted_base, str):
        hosted_base = hosted_base.strip()
    if "base_url" in updated and hosted_base:
        updated["base_url"] = hosted_base
    return updated


def _chat_completion_refusal(text: str) -> Any:
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
    return _chat_completion_refusal(text)


def format_last_decision(snapshot: Mapping[str, Any] | None) -> str:
    if not snapshot:
        return (
            "LLM-PQR: no decision yet. Status is idle until a config file exists. "
            f"Write one to start routing.\n{CONFIG_WRITE_HINT}"
        )
    return json.dumps(snapshot, indent=2, sort_keys=True)


def content_free_error(exc: BaseException) -> str:
    """Short error text for /pqr. Never includes file bodies or prompts."""

    if isinstance(exc, json.JSONDecodeError):
        return f"invalid JSON ({exc.msg})"
    if isinstance(exc, PermissionError):
        return "config file is unreadable"
    text = str(exc).strip() or type(exc).__name__
    return text.split("\n", 1)[0][:300]


def scoring_notes(payload: Mapping[str, Any]) -> list[str]:
    """Warn when missing cost/latency would be scored as 1.0. Does not change choose()."""

    notes: list[str] = []
    priorities = payload.get("priorities") if isinstance(payload.get("priorities"), dict) else {}
    models = payload.get("models") if isinstance(payload.get("models"), list) else []
    try:
        cost_w = float(priorities.get("cost") or 0)
    except (TypeError, ValueError):
        cost_w = 0.0
    try:
        latency_w = float(priorities.get("latency") or 0)
    except (TypeError, ValueError):
        latency_w = 0.0

    def _ids(predicate: Callable[[Mapping[str, Any]], bool]) -> list[str]:
        found: list[str] = []
        for row in models:
            if not isinstance(row, dict):
                continue
            ident = row.get("id")
            if isinstance(ident, str) and ident and predicate(row):
                found.append(ident)
        return found

    if cost_w > 0:
        missing_cost = _ids(
            lambda row: (
                row.get("input_cost_per_million") is None
                or row.get("output_cost_per_million") is None
            )
        )
        known_cost = _ids(
            lambda row: (
                row.get("input_cost_per_million") is not None
                and row.get("output_cost_per_million") is not None
            )
        )
        if missing_cost and known_cost:
            notes.append(
                "Some candidates have no token rates while cost weight is non-zero "
                f"({', '.join(missing_cost)}). llm-pqr scores missing cost as 1.0 when "
                "mixed with known rates — that is not a measurement. Supply rates or set "
                "cost weight to 0."
            )
    if latency_w > 0:
        missing_latency = _ids(lambda row: row.get("latency_ms") is None)
        known_latency = _ids(lambda row: row.get("latency_ms") is not None)
        if missing_latency and known_latency:
            notes.append(
                "Some candidates have no latency_ms while latency weight is non-zero "
                f"({', '.join(missing_latency)}). llm-pqr scores missing latency as 1.0 "
                "when mixed with known values — that is not a measurement. Supply "
                "latency_ms or set latency weight to 0."
            )
    return notes


def inspect_config(
    *,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> dict[str, Any]:
    """Load config for status only. Never calls Router.choose or reads prompts."""

    lookup = describe_config_lookup(environ=environ, home=home)
    result: dict[str, Any] = {
        "found": bool(lookup["found"]),
        "path": lookup["path"],
        "source": lookup["source"],
        "looked_for": lookup["looked_for"],
        "error": lookup.get("missing_reason"),
        "hint": CONFIG_WRITE_HINT,
        "policy": None,
        "candidates": None,
        "notes": [],
    }
    if not lookup["found"] or not lookup["path"]:
        return result
    path = Path(lookup["path"])
    try:
        payload = load_plugin_config(path)
        candidates, extras = candidates_from_config(payload)
        Router(candidates, Priorities(**payload.get("priorities", {})))
        pqr_request = request_from_config(
            payload, estimated_input_tokens=1, estimated_output_tokens=1
        )
    except Exception as exc:
        result["error"] = content_free_error(exc)
        return result
    result["error"] = None
    result["policy"] = {
        "local_only": bool(pqr_request.local_only),
        "require": sorted(pqr_request.required_capabilities),
        "unavailable_providers": sorted(pqr_request.unavailable_providers),
    }
    listed: list[dict[str, Any]] = []
    missing_base: list[str] = []
    for candidate in candidates:
        has_base = bool(extras.get(candidate.id, {}).get("base_url"))
        listed.append({"id": candidate.id, "local": candidate.local, "has_base_url": has_base})
        if candidate.local and not has_base:
            missing_base.append(candidate.id)
    result["candidates"] = listed
    notes = scoring_notes(payload)
    if missing_base:
        notes.append(
            "Local candidate(s) "
            + ", ".join(missing_base)
            + " have no usable base_url; a local rewrite will refuse rather than "
            "send the prompt to the default hosted provider."
        )
    result["notes"] = notes
    return result


def build_status(
    *,
    config: Mapping[str, Any],
    last_selected: Mapping[str, Any] | None = None,
    last_block: Mapping[str, Any] | None = None,
    last_decision: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    found = bool(config.get("found"))
    error = config.get("error")
    if not found:
        state = "idle"
        headline = (
            "idle because no config was found; provider calls are unchanged. "
            "Write ~/.hermes/llm-pqr.json (or set LLM_PQR_CONFIG) to start routing."
        )
        if isinstance(error, str) and error and error != "no config file found":
            headline = f"idle because {error}; provider calls are unchanged."
    elif error:
        state = "blocked"
        headline = f"blocked: {error}"
    elif last_decision is not None and last_decision.get("selected") is None:
        state = "blocked"
        headline = f"blocked: {last_decision.get('reason') or NO_ELIGIBLE_MESSAGE}"
    elif last_decision is not None and last_decision.get("selected"):
        state = "live"
        selected = last_decision.get("selected") or {}
        ident = selected.get("id") if isinstance(selected, Mapping) else None
        headline = f"live: last turn selected {ident or 'a route'}"
    elif last_selected is not None:
        state = "live"
        selected = last_selected.get("selected") or {}
        ident = selected.get("id") if isinstance(selected, Mapping) else None
        headline = f"live: last turn selected {ident or 'a route'}"
    else:
        state = "ready"
        headline = "ready: config loaded; routing will apply on the next provider call."
    return {
        "plugin": PLUGIN_NAME,
        "version": PLUGIN_VERSION,
        "unofficial": True,
        "state": state,
        "headline": headline,
        "config": dict(config),
        "last_selected": None if last_selected is None else dict(last_selected),
        "last_block": None if last_block is None else dict(last_block),
    }


def format_status(status: Mapping[str, Any]) -> str:
    """Human-readable /pqr text. Never includes prompts."""

    version = status.get("version", PLUGIN_VERSION)
    lines = [
        f"LLM-PQR {version} — unofficial Amazed Labs plugin (not a Nous Research router)",
        "",
        f"State: {status.get('state', 'idle')}",
        str(status.get("headline") or ""),
        "",
    ]
    config = status.get("config") if isinstance(status.get("config"), Mapping) else {}
    if config.get("found") and config.get("path"):
        lines.append(f"Config: {config['path']}")
    elif config.get("path"):
        lines.append(f"Config: {config['path']} (missing)")
    else:
        lines.append("Config: (none)")
    looked = config.get("looked_for") if isinstance(config.get("looked_for"), list) else []
    if looked:
        lines.append("Looked for:")
        for row in looked:
            if not isinstance(row, Mapping):
                continue
            source = row.get("source") or "path"
            path = row.get("path")
            if path is None:
                lines.append(f"  - {source}: not set")
                continue
            mark = "found" if row.get("present") else "missing"
            lines.append(f"  - {source}: {path} ({mark})")
    policy = config.get("policy") if isinstance(config.get("policy"), Mapping) else None
    if policy:
        lines.append(
            "Policy: local_only={local_only}  require={require}  "
            "unavailable_providers={unavailable_providers}".format(
                local_only=policy.get("local_only"),
                require=policy.get("require") or [],
                unavailable_providers=policy.get("unavailable_providers") or [],
            )
        )
    candidates = config.get("candidates") if isinstance(config.get("candidates"), list) else None
    if candidates:
        parts = []
        for row in candidates:
            if not isinstance(row, Mapping):
                continue
            ident = row.get("id") or "?"
            kind = "local" if row.get("local") else "hosted"
            extra = ""
            if row.get("local"):
                extra = ", base_url set" if row.get("has_base_url") else ", no base_url"
            parts.append(f"{ident} ({kind}{extra})")
        if parts:
            lines.append("Candidates: " + "; ".join(parts))
    if config.get("error") and config.get("found"):
        lines.append(f"Config problem: {config['error']}")
    notes = config.get("notes") if isinstance(config.get("notes"), list) else []
    for note in notes:
        if isinstance(note, str) and note:
            lines.append(f"Note: {note}")
    selected = (
        status.get("last_selected") if isinstance(status.get("last_selected"), Mapping) else None
    )
    lines.append("")
    if selected and isinstance(selected.get("selected"), Mapping):
        info = selected["selected"]
        lines.append(f"Last selected: {info.get('id')}")
        lines.append(
            f"  provider={info.get('provider')}  model={info.get('model')}  "
            f"local={info.get('local')}"
        )
        if selected.get("reason"):
            lines.append(f"  reason: {selected['reason']}")
        excluded = selected.get("excluded") if isinstance(selected.get("excluded"), Mapping) else {}
        if excluded:
            detail = ", ".join(f"{key} → {value}" for key, value in excluded.items())
            lines.append(f"  exclusions: {detail}")
    else:
        lines.append("Last selected: none")
    block = status.get("last_block") if isinstance(status.get("last_block"), Mapping) else None
    lines.append("")
    if block:
        lines.append(f"Last block: {block.get('reason') or NO_ELIGIBLE_MESSAGE}")
        excluded = block.get("excluded") if isinstance(block.get("excluded"), Mapping) else {}
        if excluded:
            detail = ", ".join(f"{key} → {value}" for key, value in excluded.items())
            lines.append(f"  exclusions: {detail}")
    else:
        lines.append("Last block: none")
    if not config.get("found"):
        lines.extend(["", CONFIG_WRITE_HINT])
    return "\n".join(lines).rstrip() + "\n"


def _middleware_request(*args: Any, **kwargs: Any) -> Mapping[str, Any]:
    """Hermes calls middleware as kwargs (`request`, `original_request`, ...)."""

    request = kwargs.get("request")
    if request is None and args:
        request = args[0]
    return request if isinstance(request, Mapping) else {}


def _middleware_next_call(*args: Any, **kwargs: Any) -> Callable[[Any], Any] | None:
    next_call = kwargs.get("next_call")
    if next_call is None and len(args) >= 2 and callable(args[1]):
        next_call = args[1]
    return next_call if callable(next_call) else None


def _without_request(**kwargs: Any) -> dict[str, Any]:
    return {key: value for key, value in kwargs.items() if key != "request"}


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


def _mark_request_blocked(request: Mapping[str, Any] | None, snapshot: Mapping[str, Any]) -> None:
    if not isinstance(request, dict):
        return
    request[_BLOCK_MARK] = str(snapshot.get("reason") or ROUTING_FAILED_MESSAGE)


def _request_block_reason(request: Mapping[str, Any] | None) -> str | None:
    if not isinstance(request, Mapping):
        return None
    mark = request.get(_BLOCK_MARK)
    if mark:
        return str(mark)
    return None


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
        self._last_route: dict[str, Any] | None = None
        self._last_block: dict[str, Any] | None = None
        self._blocks: dict[str, dict[str, Any]] = {}
        self._unkeyed_outcomes: deque[dict[str, Any] | None] = deque()
        self._sticky_refuse = False

    def last_decision(self) -> dict[str, Any] | None:
        with self._lock:
            return None if self._last_decision is None else dict(self._last_decision)

    def status(self) -> dict[str, Any]:
        config = inspect_config(environ=self._environ, home=self._home)
        with self._lock:
            last_decision = None if self._last_decision is None else dict(self._last_decision)
            last_route = None if self._last_route is None else dict(self._last_route)
            last_block = None if self._last_block is None else dict(self._last_block)
        return build_status(
            config=config,
            last_selected=last_route,
            last_block=last_block,
            last_decision=last_decision,
        )

    def status_text(self) -> str:
        return format_status(self.status())

    def on_llm_request(self, *args: Any, **kwargs: Any) -> dict[str, Any] | None:
        payload = _middleware_request(*args, **kwargs)
        ctx = _without_request(**kwargs)
        try:
            return self._on_llm_request(payload, **ctx)
        except Exception as exc:
            try:
                self._fail_closed(exc, request=payload, **ctx)
            except Exception:
                pass
            return None

    def on_llm_execution(self, *args: Any, **kwargs: Any) -> Any:
        request = _middleware_request(*args, **kwargs)
        next_call = _middleware_next_call(*args, **kwargs)
        ctx = _without_request(**kwargs)
        blocked_reason: str | None = None
        try:
            marked = _request_block_reason(request)
            try:
                block = self._pop_block(**ctx)
            except Exception:
                try:
                    self._fail_closed(
                        RuntimeError("failed to read routing block"),
                        request=request,
                        **ctx,
                    )
                except Exception:
                    pass
                blocked_reason = ROUTING_FAILED_MESSAGE
            else:
                if block is not None:
                    blocked_reason = str(block.get("reason") or NO_ELIGIBLE_MESSAGE)
                elif marked:
                    blocked_reason = marked
        except Exception:
            blocked_reason = ROUTING_FAILED_MESSAGE
        if blocked_reason is not None:
            try:
                return self._refusal(blocked_reason, **ctx)
            except Exception:
                return _chat_completion_refusal(f"{REFUSAL_PREFIX} {NO_ELIGIBLE_MESSAGE}".strip())
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
            self._fail_closed(exc, request=request, **kwargs)
            return None
        try:
            decision = self._choose(router, pqr_request)
            rewritten = apply_candidate(
                request, decision.candidate, extras.get(decision.candidate.id)
            )
        except ValueError as exc:
            excluded = _eligibility_exclusions(candidates, pqr_request)
            snapshot = content_free_block(reason=str(exc) or NO_ELIGIBLE_MESSAGE, excluded=excluded)
            self._record_block(snapshot, request=request, **kwargs)
            return None
        except Exception as exc:
            self._fail_closed(exc, request=request, **kwargs)
            return None
        snapshot = content_free_decision(decision)
        try:
            self._store_decision(snapshot)
        except Exception:
            pass
        try:
            self._clear_block(**kwargs)
        except Exception:
            pass
        return {
            "request": rewritten,
            "source": PLUGIN_NAME,
            "reason": snapshot["explanation"],
        }

    def _fail_closed(
        self,
        exc: BaseException,
        request: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        snapshot = content_free_block(reason=str(exc) or ROUTING_FAILED_MESSAGE)
        self._record_block(snapshot, request=request, **kwargs)

    def _record_block(
        self,
        snapshot: Mapping[str, Any],
        request: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        try:
            self._store_decision(snapshot)
        except Exception:
            pass
        try:
            _mark_request_blocked(request, snapshot)
        except Exception:
            pass
        try:
            self._set_block(snapshot, **kwargs)
            return
        except Exception:
            pass
        try:
            self._store_block_fallback(snapshot, **kwargs)
        except Exception:
            try:
                with self._lock:
                    self._sticky_refuse = True
            except Exception:
                return

    def _refusal(self, message: str, **kwargs: Any) -> Any:
        try:
            return refusal_response(message, api_mode=kwargs.get("api_mode"))
        except Exception:
            try:
                return refusal_response(NO_ELIGIBLE_MESSAGE)
            except Exception:
                return _chat_completion_refusal(f"{REFUSAL_PREFIX} {NO_ELIGIBLE_MESSAGE}".strip())

    def _correlation_key(self, **kwargs: Any) -> str | None:
        for key in ("api_request_id", "turn_id", "task_id"):
            value = kwargs.get(key)
            if isinstance(value, str):
                value = value.strip()
                if value:
                    return f"{key}:{value}"
                continue
            if value is None or isinstance(value, bool):
                continue
            text = str(value).strip()
            if text:
                return f"{key}:{text}"
        return None

    def _store_decision(self, snapshot: Mapping[str, Any]) -> None:
        payload = dict(snapshot)
        with self._lock:
            self._last_decision = payload
            if payload.get("selected"):
                self._last_route = payload
            else:
                self._last_block = payload

    def _set_block(self, snapshot: Mapping[str, Any], **kwargs: Any) -> None:
        payload = dict(snapshot)
        key = self._correlation_key(**kwargs)
        with self._lock:
            if key is None:
                self._unkeyed_outcomes.append(payload)
            else:
                self._blocks[key] = payload

    def _store_block_fallback(self, snapshot: Mapping[str, Any], **kwargs: Any) -> None:
        payload = dict(snapshot)
        try:
            key = self._correlation_key(**kwargs)
        except Exception:
            key = None
        with self._lock:
            if key is None:
                self._unkeyed_outcomes.append(payload)
            else:
                self._blocks[key] = payload

    def _clear_block(self, **kwargs: Any) -> None:
        key = self._correlation_key(**kwargs)
        with self._lock:
            if key is None:
                self._unkeyed_outcomes.append(None)
            else:
                self._blocks.pop(key, None)

    def _pop_block(self, **kwargs: Any) -> dict[str, Any] | None:
        key = self._correlation_key(**kwargs)
        with self._lock:
            if key is None:
                if self._unkeyed_outcomes:
                    return self._unkeyed_outcomes.popleft()
                return self._consume_sticky_refuse()
            block = self._blocks.pop(key, None)
            if block is not None:
                return block
            return self._consume_sticky_refuse()

    def _consume_sticky_refuse(self) -> dict[str, Any] | None:
        if not self._sticky_refuse:
            return None
        self._sticky_refuse = False
        return content_free_block(reason=ROUTING_FAILED_MESSAGE)
