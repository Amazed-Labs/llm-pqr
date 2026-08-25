"""Hermes plugin adapter tests. Hermes Agent is not imported or installed."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from llm_pqr import ModelCandidate, Request

REPO = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO / "integrations" / "hermes-plugin"


def _load_adapter():
    spec = importlib.util.spec_from_file_location(
        "hermes_llm_pqr_adapter",
        PLUGIN_ROOT / "adapter.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hermes_adapter = _load_adapter()


CANARY = "SECRET_PROMPT_DO_NOT_ROUTE"
CONFIG = {
    "local_only": False,
    "require": [],
    "unavailable_providers": [],
    "priorities": {"cost": 0, "latency": 0, "quality": 1},
    "models": [
        {
            "id": "local-fast",
            "provider": "local-runtime",
            "model": "local-model",
            "local": True,
            "quality": 0.4,
            "latency_ms": 100,
            "capabilities": ["text"],
            "base_url": "http://127.0.0.1:9/v1",
        },
        {
            "id": "hosted-tools",
            "provider": "cloud",
            "model": "hosted-model",
            "local": False,
            "quality": 0.99,
            "latency_ms": 200,
            "capabilities": ["text", "tools"],
        },
    ],
}


def _write_config(path: Path, **overrides) -> Path:
    payload = json.loads(json.dumps(CONFIG))
    payload.update(overrides)
    path.write_text(json.dumps(payload))
    return path


def _request(**overrides):
    payload = {
        "model": "original-model",
        "messages": [{"role": "user", "content": CANARY}],
        "tools": [{"type": "function", "function": {"name": "keep_me"}}],
        "temperature": 0.2,
        "max_tokens": 80,
    }
    payload.update(overrides)
    return payload


def _adapter(tmp_path: Path, monkeypatch, **config_overrides) -> hermes_adapter.RoutingAdapter:
    config = _write_config(tmp_path / "llm-pqr.json", **config_overrides)
    monkeypatch.setenv("LLM_PQR_CONFIG", str(config))
    return hermes_adapter.RoutingAdapter(environ={"LLM_PQR_CONFIG": str(config)})


class FakeCtx:
    def __init__(self) -> None:
        self.middleware: list[tuple[str, object]] = []
        self.commands: list[tuple[str, object, str]] = []
        self.skills: list[tuple[str, Path]] = []

    def register_middleware(self, kind, callback):
        self.middleware.append((kind, callback))

    def register_command(self, name, handler, description=""):
        self.commands.append((name, handler, description))

    def register_skill(self, name, path):
        self.skills.append((name, Path(path)))


def _assert_skips_next_call(adapter, *, api_request_id="blocked"):
    called = []

    def next_call(request):
        called.append(request)
        raise AssertionError("hosted model must not be invoked")

    assert adapter.on_llm_request(_request(), api_request_id=api_request_id) is None
    response = adapter.on_llm_execution(
        _request(), next_call=next_call, api_request_id=api_request_id
    )
    assert called == []
    assert CANARY not in str(response.choices[0].message.content)
    snapshot = adapter.last_decision()
    assert snapshot is not None
    assert snapshot["selected"] is None
    return response


def test_missing_config_is_noop(monkeypatch):
    monkeypatch.delenv("LLM_PQR_CONFIG", raising=False)
    adapter = hermes_adapter.RoutingAdapter(
        environ={"HERMES_HOME": "/tmp/missing-hermes-home-llm-pqr"},
        home=Path("/tmp/missing-home-llm-pqr"),
    )
    result = adapter.on_llm_request(_request())
    assert result is None
    called = []

    def next_call(request):
        called.append(request)
        return SimpleNamespace(ok=True)

    out = adapter.on_llm_execution(_request(), next_call=next_call)
    assert out.ok is True
    assert len(called) == 1


def test_hermes_home_config_is_used(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_PQR_CONFIG", raising=False)
    hermes_home = tmp_path / "hermes-home"
    hermes_home.mkdir()
    _write_config(hermes_home / "llm-pqr.json")
    adapter = hermes_adapter.RoutingAdapter(
        environ={"HERMES_HOME": str(hermes_home)},
        home=tmp_path / "unused-home",
    )
    result = adapter.on_llm_request(_request())
    assert result is not None
    assert result["request"]["model"] == "hosted-model"


def test_rewrites_model_and_preserves_tools_and_messages(tmp_path, monkeypatch):
    adapter = _adapter(tmp_path, monkeypatch, local_only=True)
    original = _request()
    assert "provider" not in original
    assert "base_url" not in original
    result = adapter.on_llm_request(original)

    assert result["source"] == "llm-pqr"
    assert original["messages"][0]["content"] == CANARY
    rewritten = result["request"]
    assert rewritten["model"] == "local-model"
    assert rewritten["provider"] == "local-runtime"
    assert rewritten["base_url"] == "http://127.0.0.1:9/v1"
    assert rewritten["tools"] == original["tools"]
    assert rewritten["messages"] == original["messages"]
    assert rewritten["temperature"] == 0.2


def test_overwrites_provider_and_base_url_when_already_present(tmp_path, monkeypatch):
    adapter = _adapter(tmp_path, monkeypatch, local_only=True)
    result = adapter.on_llm_request(
        _request(provider="keep-shape", base_url="http://example.invalid/v1")
    )
    rewritten = result["request"]
    assert rewritten["model"] == "local-model"
    assert rewritten["provider"] == "local-runtime"
    assert rewritten["base_url"] == "http://127.0.0.1:9/v1"


def test_hosted_rewrite_may_only_change_model(tmp_path, monkeypatch):
    adapter = _adapter(tmp_path, monkeypatch)
    rewritten = adapter.on_llm_request(_request())["request"]
    assert rewritten["model"] == "hosted-model"
    assert "provider" not in rewritten
    assert "base_url" not in rewritten


def test_apply_candidate_local_without_inbound_keys_writes_provider_and_base_url():
    candidate = ModelCandidate(
        id="local-fast",
        provider="local-runtime",
        model="local-model",
        local=True,
    )
    original = {
        "model": "gpt-5-hosted",
        "messages": [{"role": "user", "content": CANARY}],
        "tools": [{"type": "function", "function": {"name": "keep_me"}}],
        "temperature": 0.2,
    }
    rewritten = hermes_adapter.apply_candidate(
        original, candidate, {"base_url": "http://127.0.0.1:11434/v1"}
    )
    assert rewritten["model"] == "local-model"
    assert rewritten["provider"] == "local-runtime"
    assert rewritten["base_url"] == "http://127.0.0.1:11434/v1"
    assert rewritten["messages"] == original["messages"]
    assert rewritten["tools"] == original["tools"]
    assert rewritten["temperature"] == 0.2
    assert original.get("provider") is None
    assert original.get("base_url") is None


def test_apply_candidate_local_without_base_url_raises():
    candidate = ModelCandidate(
        id="local-fast",
        provider="local-runtime",
        model="local-model",
        local=True,
    )
    try:
        hermes_adapter.apply_candidate({"model": "gpt-5-hosted"}, candidate, {})
    except ValueError as exc:
        assert str(exc) == hermes_adapter.LOCAL_MISSING_BASE_URL_MESSAGE
    else:
        raise AssertionError("local rewrite without base_url must fail closed")


def test_apply_candidate_local_whitespace_base_url_raises():
    candidate = ModelCandidate(
        id="local-fast",
        provider="local-runtime",
        model="local-model",
        local=True,
    )
    try:
        hermes_adapter.apply_candidate({"model": "gpt-5-hosted"}, candidate, {"base_url": "   "})
    except ValueError as exc:
        assert str(exc) == hermes_adapter.LOCAL_MISSING_BASE_URL_MESSAGE
    else:
        raise AssertionError("whitespace base_url must not rewrite model-only")


def test_local_candidate_without_base_url_skips_next_call(tmp_path, monkeypatch):
    models = [
        {
            "id": "local-fast",
            "provider": "local-runtime",
            "model": "local-model",
            "local": True,
            "quality": 0.4,
            "latency_ms": 100,
            "capabilities": ["text"],
        }
    ]
    adapter = _adapter(tmp_path, monkeypatch, local_only=True, models=models)
    response = _assert_skips_next_call(adapter, api_request_id="no-base")
    assert hermes_adapter.LOCAL_MISSING_BASE_URL_MESSAGE in response.choices[0].message.content


def test_local_candidate_blank_base_url_skips_next_call(tmp_path, monkeypatch):
    models = [
        {
            "id": "local-fast",
            "provider": "local-runtime",
            "model": "local-model",
            "local": True,
            "quality": 0.4,
            "latency_ms": 100,
            "capabilities": ["text"],
            "base_url": " \t ",
        }
    ]
    adapter = _adapter(tmp_path, monkeypatch, local_only=True, models=models)
    response = _assert_skips_next_call(adapter, api_request_id="blank-base")
    assert hermes_adapter.LOCAL_MISSING_BASE_URL_MESSAGE in response.choices[0].message.content


def test_router_never_receives_prompt_or_identity(tmp_path, monkeypatch):
    seen: list[Request] = []

    def choose(router, request):
        seen.append(request)
        return router.choose(request)

    config = _write_config(tmp_path / "llm-pqr.json")
    adapter = hermes_adapter.RoutingAdapter(
        environ={"LLM_PQR_CONFIG": str(config)},
        choose=choose,
    )
    adapter.on_llm_request(
        _request(
            session_id="sess-secret",
            api_key="sk-secret",
            input=[{"role": "user", "content": CANARY}],
        )
    )

    assert len(seen) == 1
    payload = seen[0]
    assert isinstance(payload, Request)
    dumped = json.dumps(payload.__dict__, default=str)
    assert CANARY not in dumped
    assert "sess-secret" not in dumped
    assert "sk-secret" not in dumped
    assert payload.estimated_input_tokens == max(1, len(CANARY) // 4)
    assert payload.estimated_output_tokens == 80


def test_no_eligible_candidate_skips_next_call(tmp_path, monkeypatch):
    adapter = _adapter(tmp_path, monkeypatch, local_only=True, require=["vision"])
    called = []

    def next_call(request):
        called.append(request)
        raise AssertionError("hosted model must not be invoked")

    assert adapter.on_llm_request(_request(), api_request_id="t1") is None
    response = adapter.on_llm_execution(_request(), next_call=next_call, api_request_id="t1")

    assert called == []
    assert response.choices[0].finish_reason == "stop"
    assert "no eligible" in response.choices[0].message.content
    assert CANARY not in response.choices[0].message.content
    snapshot = adapter.last_decision()
    assert snapshot["selected"] is None
    assert snapshot["excluded"]["local-fast"] == "missing required capabilities"


def test_middleware_swallows_router_exceptions(tmp_path, monkeypatch):
    def choose(_router, _request):
        raise RuntimeError("boom")

    config = _write_config(tmp_path / "llm-pqr.json")
    adapter = hermes_adapter.RoutingAdapter(
        environ={"LLM_PQR_CONFIG": str(config)},
        choose=choose,
    )
    response = _assert_skips_next_call(adapter, api_request_id="boom")
    assert "boom" in response.choices[0].message.content


def test_invalid_json_config_skips_next_call(tmp_path, monkeypatch):
    config = tmp_path / "llm-pqr.json"
    config.write_text("{not-json")
    monkeypatch.setenv("LLM_PQR_CONFIG", str(config))
    adapter = hermes_adapter.RoutingAdapter(environ={"LLM_PQR_CONFIG": str(config)})
    _assert_skips_next_call(adapter, api_request_id="bad-json")


def test_config_missing_models_skips_next_call(tmp_path, monkeypatch):
    config = tmp_path / "llm-pqr.json"
    config.write_text(json.dumps({"priorities": {"quality": 1}}))
    monkeypatch.setenv("LLM_PQR_CONFIG", str(config))
    adapter = hermes_adapter.RoutingAdapter(environ={"LLM_PQR_CONFIG": str(config)})
    _assert_skips_next_call(adapter, api_request_id="no-models")


def test_empty_models_list_skips_next_call(tmp_path, monkeypatch):
    adapter = _adapter(tmp_path, monkeypatch, models=[])
    _assert_skips_next_call(adapter, api_request_id="empty-models")


def test_malformed_models_list_skips_next_call(tmp_path, monkeypatch):
    adapter = _adapter(tmp_path, monkeypatch, models=["not-an-object", None])
    _assert_skips_next_call(adapter, api_request_id="bad-models")


def test_bad_priorities_skip_next_call(tmp_path, monkeypatch):
    adapter = _adapter(tmp_path, monkeypatch, priorities={"cost": 0, "latency": 0, "quality": 0})
    _assert_skips_next_call(adapter, api_request_id="bad-priorities")


def test_unreadable_config_skips_next_call(tmp_path, monkeypatch):
    config = _write_config(tmp_path / "llm-pqr.json")
    adapter = hermes_adapter.RoutingAdapter(environ={"LLM_PQR_CONFIG": str(config)})
    original = Path.read_text

    def boom(self, *args, **kwargs):
        if Path(self) == config:
            raise PermissionError("unreadable")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", boom)
    _assert_skips_next_call(adapter, api_request_id="unreadable")


def test_block_pop_error_skips_next_call(tmp_path, monkeypatch):
    adapter = _adapter(tmp_path, monkeypatch, local_only=True, require=["vision"])
    called = []

    def next_call(request):
        called.append(request)
        raise AssertionError("hosted model must not be invoked")

    assert adapter.on_llm_request(_request(), api_request_id="pop") is None

    def boom(**_kwargs):
        raise RuntimeError("pop failed")

    adapter._pop_block = boom
    response = adapter.on_llm_execution(_request(), next_call=next_call, api_request_id="pop")
    assert called == []
    assert CANARY not in str(response.choices[0].message.content)


def test_set_block_failure_skips_next_call(tmp_path, monkeypatch):
    adapter = _adapter(tmp_path, monkeypatch, local_only=True, require=["vision"])

    def boom(*_args, **_kwargs):
        raise RuntimeError("cannot store block")

    adapter._set_block = boom
    _assert_skips_next_call(adapter, api_request_id="set-block-fail")


def test_store_decision_failure_still_skips_next_call(tmp_path, monkeypatch):
    adapter = _adapter(tmp_path, monkeypatch, local_only=True, require=["vision"])

    def boom(*_args, **_kwargs):
        raise RuntimeError("cannot store decision")

    adapter._store_decision = boom
    called = []

    def next_call(request):
        called.append(request)
        raise AssertionError("hosted model must not be invoked")

    assert adapter.on_llm_request(_request(), api_request_id="store-fail") is None
    response = adapter.on_llm_execution(
        _request(), next_call=next_call, api_request_id="store-fail"
    )
    assert called == []
    assert CANARY not in str(response.choices[0].message.content)
    assert adapter.last_decision() is None


def test_unkeyed_success_does_not_clear_other_turn_block(tmp_path, monkeypatch):
    n = {"count": 0}

    def choose(router, request):
        n["count"] += 1
        if n["count"] == 1:
            raise ValueError(hermes_adapter.NO_ELIGIBLE_MESSAGE)
        return router.choose(request)

    config = _write_config(tmp_path / "llm-pqr.json")
    adapter = hermes_adapter.RoutingAdapter(
        environ={"LLM_PQR_CONFIG": str(config)},
        choose=choose,
    )
    assert adapter.on_llm_request(_request()) is None
    allowed = adapter.on_llm_request(_request())
    assert allowed is not None

    called = []

    def next_call(request):
        called.append(request)
        raise AssertionError("blocked unkeyed turn must not invoke provider")

    response = adapter.on_llm_execution(_request(), next_call=next_call)
    assert called == []
    assert CANARY not in str(response.choices[0].message.content)

    marker = SimpleNamespace(ok=True)
    out = adapter.on_llm_execution(allowed["request"], next_call=lambda request: marker)
    assert out is marker


def test_two_unkeyed_blocks_both_skip_next_call(tmp_path, monkeypatch):
    adapter = _adapter(tmp_path, monkeypatch, local_only=True, require=["vision"])
    assert adapter.on_llm_request(_request()) is None
    assert adapter.on_llm_request(_request()) is None

    def refuse_without_provider():
        called = []

        def next_call(request):
            called.append(request)
            raise AssertionError("hosted model must not be invoked")

        response = adapter.on_llm_execution(_request(), next_call=next_call)
        assert called == []
        assert CANARY not in str(response.choices[0].message.content)

    refuse_without_provider()
    refuse_without_provider()


def test_refusal_builder_error_still_skips_next_call(tmp_path, monkeypatch):
    adapter = _adapter(tmp_path, monkeypatch, local_only=True, require=["vision"])
    called = []

    def next_call(request):
        called.append(request)
        raise AssertionError("hosted model must not be invoked")

    assert adapter.on_llm_request(_request(), api_request_id="refusal-boom") is None

    def boom(*_args, **_kwargs):
        raise RuntimeError("cannot build refusal")

    monkeypatch.setattr(hermes_adapter, "refusal_response", boom)
    response = adapter.on_llm_execution(
        _request(), next_call=next_call, api_request_id="refusal-boom"
    )
    assert called == []
    assert response is not None
    assert CANARY not in str(response)


def test_execution_passthrough_calls_next_once(tmp_path, monkeypatch):
    adapter = _adapter(tmp_path, monkeypatch)
    marker = SimpleNamespace(ok=True)
    calls = []

    def next_call(request):
        calls.append(request)
        return marker

    request = _request()
    result = adapter.on_llm_request(request)
    assert result is not None
    out = adapter.on_llm_execution(result["request"], next_call=next_call)
    assert out is marker
    assert calls == [result["request"]]


def test_last_decision_and_slash_output_are_content_free(tmp_path, monkeypatch):
    adapter = _adapter(tmp_path, monkeypatch)
    adapter.on_llm_request(_request())
    snapshot = adapter.last_decision()
    text = hermes_adapter.format_last_decision(snapshot)
    assert snapshot["selected"]["id"] == "hosted-tools"
    assert CANARY not in text
    assert "messages" not in snapshot
    assert "input" not in snapshot


def test_register_wires_middleware_skill_and_command_without_hermes():
    spec = importlib.util.spec_from_file_location(
        "hermes_llm_pqr_plugin",
        PLUGIN_ROOT / "__init__.py",
        submodule_search_locations=[str(PLUGIN_ROOT)],
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["hermes_llm_pqr_plugin"] = module
    spec.loader.exec_module(module)

    ctx = FakeCtx()
    module.register(ctx)
    kinds = [kind for kind, _ in ctx.middleware]
    assert kinds == ["llm_request", "llm_execution"]
    assert ctx.commands[0][0] == "pqr"
    assert ctx.skills[0][0] == "configure"
    assert ctx.skills[0][1].name == "SKILL.md"
    assert CANARY not in ctx.commands[0][2]


def test_example_config_matches_llm_pqr_models_shape():
    example = json.loads((PLUGIN_ROOT / "examples" / "llm-pqr.json").read_text())
    repo_example = json.loads((REPO / "examples" / "models.json").read_text())
    assert "priorities" in example and "models" in example
    by_id = {row["id"]: row for row in example["models"]}
    for row in repo_example["models"]:
        plugin_row = by_id[row["id"]]
        for key in ("provider", "model", "local", "quality", "latency_ms", "capabilities"):
            assert plugin_row[key] == row[key]
    note = example["_provenance"]["note"]
    assert "already has base_url" not in note
    assert "always written" in note
    hermes_adapter.candidates_from_config(example)
    hermes_adapter.request_from_config(
        example, estimated_input_tokens=10, estimated_output_tokens=5
    )


def test_plugin_version_is_independent_of_package():
    yaml_text = (PLUGIN_ROOT / "plugin.yaml").read_text()
    assert "version: 0.1.1" in yaml_text
    assert hermes_adapter.PLUGIN_VERSION == "0.1.1"
    pyproject = (REPO / "pyproject.toml").read_text()
    assert 'version = "0.3.1"' in pyproject


def test_anthropic_and_codex_refusal_shapes_skip_provider():
    response = hermes_adapter.refusal_response(
        "no eligible candidates", api_mode="anthropic_messages"
    )
    assert response.content[0].text.startswith(hermes_adapter.REFUSAL_PREFIX)
    codex = hermes_adapter.refusal_response("no eligible candidates", api_mode="codex_responses")
    assert "no eligible" in codex.output_text
    assert isinstance(codex.output, list) and codex.output
