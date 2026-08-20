"""Add invariant tests for the Router, init CLI roundtrip, and runner-side rubric.

These tests assert behavior contracts, not value snapshots (per AGENTS.md).
Tie-break order is asserted only as an invariant (deterministic by `id`),
not as a specific winner.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from llm_pqr import ModelCandidate, Priorities, Request, Router

REPO = Path(__file__).resolve().parents[1]


def _candidate(**overrides):
    base: dict[str, object] = {
        "id": "c",
        "provider": "p",
        "model": "m",
        "local": False,
        "quality": 0.5,
        "latency_ms": 1000,
        "input_cost_per_million": 1.0,
        "output_cost_per_million": 2.0,
        "capabilities": frozenset({"text"}),
    }
    base.update(overrides)
    return ModelCandidate(**base)  # type: ignore[arg-type]


# --- Router invariants ------------------------------------------------------


def test_router_rejects_empty_candidate_list():
    with pytest.raises(ValueError, match="at least one candidate is required"):
        Router([], Priorities())


def test_router_rejects_duplicate_candidate_ids():
    with pytest.raises(ValueError, match="unique"):
        Router([_candidate(id="dup"), _candidate(id="dup")], Priorities())


def test_router_rejects_invalid_quality_outside_zero_one():
    with pytest.raises(ValueError, match="quality must be between 0 and 1"):
        _candidate(quality=1.5)
    with pytest.raises(ValueError, match="quality must be between 0 and 1"):
        _candidate(quality=-0.1)


def test_router_rejects_negative_latency_or_token_rates():
    with pytest.raises(ValueError, match="cannot be negative"):
        _candidate(latency_ms=-1)
    with pytest.raises(ValueError, match="cannot be negative"):
        _candidate(input_cost_per_million=-0.1)
    with pytest.raises(ValueError, match="cannot be negative"):
        _candidate(output_cost_per_million=-0.1)


def test_router_rejects_empty_required_id_or_model():
    with pytest.raises(ValueError, match="required"):
        _candidate(id="")


def test_priorities_rejects_all_zero():
    with pytest.raises(ValueError, match="at least one priority weight must be positive"):
        Priorities(cost=0, latency=0, quality=0)


def test_priorities_rejects_negative_weight():
    with pytest.raises(ValueError, match="cannot be negative"):
        Priorities(cost=-1, latency=0, quality=0)


def test_priorities_normalization_is_sum_one():
    p = Priorities(cost=2, latency=3, quality=5)
    norm = p.normalized()
    assert abs(sum(norm.values()) - 1.0) < 1e-9
    assert norm == {"cost": 0.2, "latency": 0.3, "quality": 0.5}


def test_request_rejects_negative_token_counts():
    with pytest.raises(ValueError, match="cannot be negative"):
        Request(estimated_input_tokens=-1)


def test_router_chooses_reproducibly_for_identical_inputs():
    a = Router(
        [_candidate(id="a", quality=0.6), _candidate(id="b", quality=0.6)],
        Priorities(),
    ).choose(Request())
    b = Router(
        [_candidate(id="a", quality=0.6), _candidate(id="b", quality=0.6)],
        Priorities(),
    ).choose(Request())
    # Determinism with equal scores: the same `id` wins across runs.
    assert a.candidate.id == b.candidate.id


def test_router_reports_missing_capability_with_clear_reason():
    decision = Router(
        [
            _candidate(id="has-tools", capabilities=frozenset({"text", "tools"})),
            _candidate(id="plain", capabilities=frozenset({"text"})),
        ],
        Priorities(),
    ).choose(Request(required_capabilities=frozenset({"tools"})))
    assert decision.candidate.id == "has-tools"
    assert decision.excluded == {"plain": "missing required capabilities"}


def test_router_handles_missing_cost_data_without_fabricating():
    candidate = ModelCandidate(
        id="no-cost",
        provider="p",
        model="m",
        local=False,
        quality=0.7,
        latency_ms=900,
        input_cost_per_million=None,
        output_cost_per_million=None,
    )
    decision = Router([candidate], Priorities(cost=1, latency=0, quality=0)).choose(Request())
    assert decision.estimated_cost_usd is None
    assert "unknown" in decision.explain().lower()


def test_router_no_eligible_candidates_raises_clear_error():
    with pytest.raises(ValueError, match="no eligible candidates"):
        Router(
            [_candidate(id="cloudy")],
            Priorities(),
        ).choose(Request(local_only=True))


def test_router_excludes_candidates_from_rate_limited_provider():
    decision = Router(
        [
            _candidate(id="limited", provider="provider-a", quality=1.0),
            _candidate(id="healthy", provider="provider-b", quality=0.6),
        ],
        Priorities(quality=1, cost=0, latency=0),
    ).choose(Request(unavailable_providers=frozenset({"provider-a"})))

    assert decision.candidate.provider == "provider-b"
    assert decision.excluded == {"limited": "provider unavailable"}


# --- CLI roundtrip (init -> load -> choose) ----------------------------------


def test_init_cli_writes_loadable_example_and_round_trips(tmp_path):
    output = tmp_path / "models.json"
    proc = subprocess.run(
        [sys.executable, "-m", "llm_pqr.cli", "init", "--output", str(output), "--force"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert output.is_file()

    payload = json.loads(output.read_text())
    assert "priorities" in payload
    assert "models" in payload
    assert payload["models"], "init example must seed at least one model"

    proc2 = subprocess.run(
        [
            sys.executable,
            "-m",
            "llm_pqr.cli",
            "choose",
            "--config",
            str(output),
            "--input-tokens",
            "500",
            "--output-tokens",
            "100",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc2.returncode == 0, proc2.stderr
    decision = json.loads(proc2.stdout)
    assert "selected" in decision
    assert decision["selected"]["id"] in {m["id"] for m in payload["models"]}


def test_init_cli_refuses_to_overwrite_without_force(tmp_path):
    output = tmp_path / "models.json"
    output.write_text("{}")
    proc = subprocess.run(
        [sys.executable, "-m", "llm_pqr.cli", "init", "--output", str(output)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    assert "refusing to overwrite" in proc.stderr or "refusing to overwrite" in proc.stdout


# --- Runner-side rubric invariants -----------------------------------------


def test_runner_score_exact_matches_stripped_text():
    from llm_pqr.eval_runner import _score

    task = {"rubric": {"kind": "exact", "expected": "17"}}
    assert _score(task, "17") is True
    assert _score(task, " 17  ") is True
    assert _score(task, "17.") is False


def test_runner_score_contains_all_is_case_insensitive():
    from llm_pqr.eval_runner import _score

    task = {"rubric": {"kind": "contains_all", "required": ["Deployment", "TOMORROW"]}}
    assert _score(task, "deployment is delayed until tomorrow") is True
    assert _score(task, "deployment is delayed") is False


def test_runner_score_unsupported_rubric_returns_none():
    from llm_pqr.eval_runner import _score

    task = {"rubric": {"kind": "semantic", "must_include_any": ["x"]}}
    assert _score(task, "x") is None


def test_runner_schedule_rejects_non_positive_repeats():
    from llm_pqr.eval_runner import schedule

    with pytest.raises(ValueError, match="repeats must be positive"):
        schedule([], [], repeats=0, seed=1)
    with pytest.raises(ValueError, match="repeats must be positive"):
        schedule([], [], repeats=-1, seed=1)


def test_runner_schedule_marks_every_invocation():
    from llm_pqr.eval_runner import schedule

    tasks = [{"id": "t", "local_only": False}, {"id": "p", "local_only": True}]
    candidates = [
        {"id": "local", "provider": "p", "model": "m", "local": True},
        {"id": "cloud", "provider": "p", "model": "m", "local": False},
    ]
    rows = schedule(tasks, candidates, repeats=2, seed=1)
    # 2 tasks × 2 candidates × 2 repeats = 8 rows.
    assert len(rows) == 8
    assert all(row["status"] in {"scheduled", "policy_blocked"} for row in rows)
    assert any(row["status"] == "policy_blocked" for row in rows)
