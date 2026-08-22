"""Lock the measured public example against silent provenance or behavior drift."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
EXAMPLE = REPO / "examples" / "models.json"
MEASURED = REPO / "examples" / "measured-smoke-20260814.json"
PUBLIC_MEASURED = REPO / "examples" / "measured-public-text-20260822.json"
_VERIFY_SPEC = importlib.util.spec_from_file_location(
    "verify_measured_public_text",
    REPO / "examples" / "verify_measured_public_text.py",
)
assert _VERIFY_SPEC is not None and _VERIFY_SPEC.loader is not None
verify_public_text = importlib.util.module_from_spec(_VERIFY_SPEC)
_VERIFY_SPEC.loader.exec_module(verify_public_text)


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
        assert model["local"] == source["local"]
        assert model["capabilities"] == source["capabilities"]
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


def test_measured_aggregate_rebuilds_from_sanitized_rows():
    proc = subprocess.run(
        [sys.executable, str(REPO / "examples" / "verify_measured_smoke.py")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "verified 24 sanitized rows across 4 candidates" in proc.stdout


def test_public_text_aggregate_rebuilds_from_sanitized_rows():
    proc = subprocess.run(
        [sys.executable, str(REPO / "examples" / "verify_measured_public_text.py")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "verified 192 sanitized rows across 4 candidates" in proc.stdout


def test_public_text_verifier_rejects_duplicate_json_keys(monkeypatch, tmp_path):
    text = PUBLIC_MEASURED.read_text().replace(
        '"schema_version": "1.0",',
        '"schema_version": "bad",\n  "schema_version": "1.0",',
        1,
    )
    mutated = tmp_path / "duplicate-key.json"
    mutated.write_text(text)
    monkeypatch.setattr(verify_public_text, "SOURCE", mutated)

    with pytest.raises(SystemExit, match="duplicate JSON key"):
        verify_public_text.main()


def test_public_text_verifier_binds_scores_to_rubric_kind(monkeypatch, tmp_path):
    payload = json.loads(PUBLIC_MEASURED.read_text())
    deterministic = next(
        row for row in payload["normalized_rows"] if isinstance(row["score"], bool)
    )
    semantic = next(row for row in payload["normalized_rows"] if row["score"] is None)
    deterministic["score"], semantic["score"] = semantic["score"], deterministic["score"]
    mutated = tmp_path / "score-swap.json"
    mutated.write_text(json.dumps(payload))
    monkeypatch.setattr(verify_public_text, "SOURCE", mutated)

    with pytest.raises(SystemExit, match="score eligibility"):
        verify_public_text.main()


@pytest.mark.parametrize("location", ["top", "row"])
def test_public_text_verifier_rejects_unexpected_privacy_fields(monkeypatch, tmp_path, location):
    payload = json.loads(PUBLIC_MEASURED.read_text())
    if location == "top":
        payload["raw_responses"] = ["must not be accepted"]
    else:
        payload["normalized_rows"][0]["response_text"] = "must not be accepted"
    mutated = tmp_path / f"privacy-{location}.json"
    mutated.write_text(json.dumps(payload))
    monkeypatch.setattr(verify_public_text, "SOURCE", mutated)

    with pytest.raises(SystemExit, match="schema mismatch"):
        verify_public_text.main()


@pytest.mark.parametrize(
    "case",
    [
        "row-repeat-float",
        "candidate-local-int",
        "candidate-reliability-bool",
        "candidate-scheduled-float",
        "scope-repeats-float",
        "gate-whole-int",
        "gate-minimum-float",
    ],
)
def test_public_text_verifier_rejects_type_confusion(monkeypatch, tmp_path, case):
    payload = json.loads(PUBLIC_MEASURED.read_text())
    if case == "row-repeat-float":
        payload["normalized_rows"][0]["repeat"] = 1.0
    elif case == "candidate-local-int":
        payload["candidates"][0]["local"] = 1
    elif case == "candidate-reliability-bool":
        payload["candidates"][0]["reliability"] = True
    elif case == "candidate-scheduled-float":
        payload["candidates"][0]["scheduled_rows"] = 48.0
    elif case == "scope-repeats-float":
        payload["scope"]["repeats_per_task"] = 3.0
    elif case == "gate-whole-int":
        payload["ranking_gate"]["whole_corpus_rankable"] = 0
    elif case == "gate-minimum-float":
        payload["ranking_gate"]["minimum_valid_responses_per_candidate"] = 36.0
    mutated = tmp_path / f"type-{case}.json"
    mutated.write_text(json.dumps(payload))
    monkeypatch.setattr(verify_public_text, "SOURCE", mutated)

    with pytest.raises(SystemExit):
        verify_public_text.main()


@pytest.mark.parametrize("location", ["private-source", "response-row"])
def test_public_text_verifier_binds_valid_format_hashes(monkeypatch, tmp_path, location):
    payload = json.loads(PUBLIC_MEASURED.read_text())
    if location == "private-source":
        payload["private_source_artifact_sha256"] = "f" * 64
        message = "private-source provenance hash mismatch"
    else:
        payload["normalized_rows"][0]["response_sha256"] = "f" * 64
        message = "normalized-row evidence hash mismatch"
    mutated = tmp_path / f"hash-{location}.json"
    mutated.write_text(json.dumps(payload))
    monkeypatch.setattr(verify_public_text, "SOURCE", mutated)

    with pytest.raises(SystemExit, match=message):
        verify_public_text.main()


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
