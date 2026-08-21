"""Lock the measured public example against silent provenance or behavior drift."""

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EXAMPLE = REPO / "examples" / "models.json"
MEASURED = REPO / "examples" / "measured-smoke-20260814.json"


def _run(*args: str) -> dict:
    proc = subprocess.run(
        [sys.executable, "-m", "llm_pqr.cli", "choose", "--config", str(EXAMPLE), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_example_is_derived_from_checked_in_measured_summary():
    config = json.loads(EXAMPLE.read_text())
    measured = json.loads(MEASURED.read_text())
    by_id = {row["id"]: row for row in measured["candidates"]}

    assert config["_provenance"]["summary"] == MEASURED.name
    assert measured["method"]["ranking_gate"].startswith("withheld")
    assert all(row["rankable"] is False for row in measured["candidates"])
    for model in config["models"]:
        source = by_id[model["id"]]
        assert model["provider"] == source["provider"]
        assert model["model"] == source["model"]
        assert model["quality"] == source["quality"]
        assert model["latency_ms"] == source["latency_ms"]
        assert "input_cost_per_million" not in model
        assert "output_cost_per_million" not in model


def test_measured_summary_has_no_content_identity_or_credential_fields():
    measured = json.loads(MEASURED.read_text())
    forbidden = {"prompt", "response", "command", "access_token", "api_key", "session_id"}

    def keys(value):
        if isinstance(value, dict):
            for key, item in value.items():
                yield key.lower()
                yield from keys(item)
        elif isinstance(value, list):
            for item in value:
                yield from keys(item)

    assert forbidden.isdisjoint(keys(measured))


def test_default_selection_is_reproducible_and_cost_is_unknown():
    first = _run("--input-tokens", "1200", "--output-tokens", "300")
    second = _run("--input-tokens", "1200", "--output-tokens", "300")

    assert first == second
    assert first["selected"]["id"] == "sol"
    assert first["estimated_cost_usd"] is None


def test_local_only_excludes_all_hosted_candidates():
    out = _run("--local-only")
    assert out["selected"]["id"] == "local-qwen"
    assert set(out["excluded"]) == {"luna", "terra", "sol"}
    assert all(reason == "not local" for reason in out["excluded"].values())


def test_require_tools_keeps_only_declared_tool_capable_candidates():
    out = _run("--require", "tools")
    assert out["selected"]["id"] == "sol"
    assert set(out["excluded"]) == {"local-qwen", "luna"}
    assert all(reason == "missing required capabilities" for reason in out["excluded"].values())
