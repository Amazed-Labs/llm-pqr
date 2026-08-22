"""Verify the public-text aggregate from checked-in sanitized rows."""

from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
from itertools import product
from pathlib import Path

SOURCE = Path(__file__).with_name("measured-public-text-20260822.json")
CORPUS = Path(__file__).parents[1] / "evals" / "routing-v1.json"
HEX_64 = re.compile(r"[0-9a-f]{64}")
EXPECTED_PRIVATE_SOURCE_HASH = "0ea4f6c1727863ab678e043c695d9b33b11eb54c4eb78210f8c9d8cfeaf2488b"
EXPECTED_NORMALIZED_ROWS_HASH = "e287be05c73cd8055a4a847a6d642955b095370220c212f6a4247985d2647929"
TOP_KEYS = {
    "schema_version",
    "observed_at",
    "run_id",
    "corpus_id",
    "corpus_sha256",
    "private_source_artifact_sha256",
    "scope",
    "method",
    "ranking_gate",
    "candidates",
    "normalized_rows",
}
SCOPE_KEYS = {"tasks", "repeats_per_task", "excluded", "semantic_rubrics"}
METHOD_KEYS = {"quality", "reliability", "latency_ms", "usage", "cost", "verification"}
GATE_KEYS = {
    "minimum_valid_responses_per_candidate",
    "minimum_comparable_coverage",
    "gate_passed_for_this_slice",
    "whole_corpus_rankable",
    "composite_winner_reported",
    "reason",
}
CANDIDATE_KEYS = {
    "id",
    "provider",
    "model",
    "local",
    "scheduled_rows",
    "valid_responses",
    "reliability",
    "deterministically_scored_responses",
    "passed_rubrics",
    "quality_conditional_on_scored",
    "latency_ms",
    "usage",
    "cost_usd",
}
ROW_KEYS = {
    "task_id",
    "candidate_id",
    "repeat",
    "status",
    "failure_class",
    "latency_ms",
    "response_sha256",
    "usage",
    "usage_source",
    "cost_usd",
    "score",
}
EXPECTED_CANDIDATES = {
    "local-qwen": ("local-qwen", "qwen3.6-35b-a3b-local", True),
    "luna": ("openai-codex", "gpt-5.6-luna", False),
    "sol": ("openai-codex", "gpt-5.6-sol", False),
    "terra": ("openai-codex", "gpt-5.6-terra", False),
}
EXPECTED_METHOD = {
    "quality": "passed strict type-exact deterministic exact, contains_all (including negative constraints), json_exact, and json_fields rubrics / deterministically scored valid responses",
    "reliability": "valid responses / scheduled invocations",
    "latency_ms": "wall-clock; p50 median; p95 linear interpolation",
    "usage": "null because Hermes CLI emitted no machine-readable usage",
    "cost": "null because usage and dated price evidence were unavailable",
    "verification": "python examples/verify_measured_public_text.py",
}


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _require_exact_keys(value: object, expected: set[str], label: str) -> dict:
    if not isinstance(value, dict) or set(value) != expected:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise SystemExit(f"{label} schema mismatch: {actual}")
    return value


def _type_exact_equal(actual: object, expected: object) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict) and isinstance(actual, dict):
        return set(actual) == set(expected) and all(
            _type_exact_equal(actual[key], value) for key, value in expected.items()
        )
    if isinstance(expected, (list, tuple)) and isinstance(actual, (list, tuple)):
        return len(actual) == len(expected) and all(
            _type_exact_equal(left, right) for left, right in zip(actual, expected)
        )
    return actual == expected


def _strict_json_loads(text: str) -> object:
    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def reject_constant(value: str) -> object:
        raise ValueError(f"non-standard JSON constant: {value}")

    return json.loads(
        text,
        object_pairs_hook=reject_duplicates,
        parse_constant=reject_constant,
    )


def main() -> int:
    try:
        decoded = _strict_json_loads(SOURCE.read_text())
    except (json.JSONDecodeError, ValueError) as exc:
        raise SystemExit(f"invalid evidence JSON: {exc}") from exc
    payload = _require_exact_keys(decoded, TOP_KEYS, "top-level")
    if payload["schema_version"] != "1.0":
        raise SystemExit("unsupported measured-public-text schema")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", payload["observed_at"]) is None:
        raise SystemExit("invalid observation date")
    if re.fullmatch(r"[0-9a-f]{32}", payload["run_id"]) is None:
        raise SystemExit("invalid run ID")
    if payload["private_source_artifact_sha256"] != EXPECTED_PRIVATE_SOURCE_HASH:
        raise SystemExit("private-source provenance hash mismatch")

    corpus = json.loads(CORPUS.read_text())
    corpus_hash = hashlib.sha256(CORPUS.read_bytes()).hexdigest()
    if payload["corpus_id"] != corpus["corpus_id"] or payload["corpus_sha256"] != corpus_hash:
        raise SystemExit("corpus identity or hash mismatch")
    eligible_tasks = {
        task["id"]
        for task in corpus["tasks"]
        if task["modality"] == "text" and not task["local_only"]
    }
    if len(eligible_tasks) != 16:
        raise SystemExit("expected exactly 16 eligible public text tasks")
    tasks_by_id = {task["id"]: task for task in corpus["tasks"]}
    deterministic_kinds = {"exact", "contains_all", "json_exact", "json_fields"}

    scope = _require_exact_keys(payload["scope"], SCOPE_KEYS, "scope")
    method = _require_exact_keys(payload["method"], METHOD_KEYS, "method")
    gate = _require_exact_keys(payload["ranking_gate"], GATE_KEYS, "ranking gate")
    expected_scope = {
        "tasks": "16 public, text-only tasks",
        "repeats_per_task": 3,
        "excluded": ["local-only tasks", "vision tasks"],
        "semantic_rubrics": "preserved as unscored",
    }
    if not _type_exact_equal(scope, expected_scope):
        raise SystemExit("scope declaration does not match the bounded slice")
    if not _type_exact_equal(method, EXPECTED_METHOD):
        raise SystemExit("method declaration does not match the verified procedure")

    candidates = payload["candidates"]
    if not isinstance(candidates, list) or not candidates:
        raise SystemExit("candidates must be a non-empty list")
    for candidate in candidates:
        _require_exact_keys(candidate, CANDIDATE_KEYS, "candidate")
        if set(candidate["latency_ms"]) != {"p50", "p95"}:
            raise SystemExit("candidate latency schema mismatch")
        if candidate["usage"] is not None or candidate["cost_usd"] is not None:
            raise SystemExit("candidate usage and cost must remain null")
    declared = {row["id"]: row for row in candidates}
    if len(declared) != len(candidates):
        raise SystemExit("candidate IDs must be unique")
    if set(declared) != set(EXPECTED_CANDIDATES):
        raise SystemExit("candidate identities do not match the measured run")
    for candidate_id, expected_metadata in EXPECTED_CANDIDATES.items():
        candidate = declared[candidate_id]
        actual_metadata = (candidate["provider"], candidate["model"], candidate["local"])
        if not _type_exact_equal(actual_metadata, expected_metadata):
            raise SystemExit(f"candidate metadata mismatch for {candidate_id}")

    rows = payload["normalized_rows"]
    if not isinstance(rows, list) or len(rows) != 192:
        raise SystemExit(
            f"expected 192 normalized rows, found {len(rows) if isinstance(rows, list) else 'invalid'}"
        )
    seen = set()
    for row in rows:
        _require_exact_keys(row, ROW_KEYS, "normalized row")
        key = (row["task_id"], row["candidate_id"], row["repeat"])
        if key in seen:
            raise SystemExit(f"duplicate row key: {key}")
        seen.add(key)
        if row["task_id"] not in eligible_tasks or row["candidate_id"] not in declared:
            raise SystemExit(f"row outside declared task/candidate matrix: {key}")
        if type(row["repeat"]) is not int or row["repeat"] not in {1, 2, 3}:
            raise SystemExit(f"invalid repeat: {key}")
        if row["status"] != "valid_response":
            raise SystemExit(f"invalid repeat or status: {key}")
        if row["failure_class"] is not None:
            raise SystemExit(f"valid row has failure class: {key}")
        if HEX_64.fullmatch(row["response_sha256"]) is None:
            raise SystemExit(f"invalid response hash: {key}")
        if (
            row["usage"] is not None
            or row["usage_source"] is not None
            or row["cost_usd"] is not None
        ):
            raise SystemExit(f"usage/cost must remain null: {key}")
        latency = row["latency_ms"]
        if (
            isinstance(latency, bool)
            or not isinstance(latency, (int, float))
            or not math.isfinite(latency)
            or latency < 0
        ):
            raise SystemExit(f"invalid latency: {key}")
        if row["score"] is not None and not isinstance(row["score"], bool):
            raise SystemExit(f"invalid score: {key}")
        deterministic = tasks_by_id[row["task_id"]]["rubric"]["kind"] in deterministic_kinds
        if deterministic != isinstance(row["score"], bool):
            raise SystemExit(f"score eligibility does not match rubric kind: {key}")

    expected_matrix = set(product(eligible_tasks, declared, (1, 2, 3)))
    if seen != expected_matrix:
        raise SystemExit("rows do not cover the complete task/candidate/repeat matrix")
    rows_hash = hashlib.sha256(
        json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if rows_hash != EXPECTED_NORMALIZED_ROWS_HASH:
        raise SystemExit("normalized-row evidence hash mismatch")

    for candidate_id, summary in declared.items():
        candidate_rows = [row for row in rows if row["candidate_id"] == candidate_id]
        scored = [row for row in candidate_rows if isinstance(row["score"], bool)]
        latencies = [float(row["latency_ms"]) for row in candidate_rows]
        expected = {
            "scheduled_rows": len(candidate_rows),
            "valid_responses": len(candidate_rows),
            "reliability": 1.0,
            "deterministically_scored_responses": len(scored),
            "passed_rubrics": sum(row["score"] for row in scored),
            "quality_conditional_on_scored": round(
                sum(row["score"] for row in scored) / len(scored), 6
            ),
            "latency_ms": {
                "p50": round(statistics.median(latencies), 1),
                "p95": round(_percentile(latencies, 0.95), 1),
            },
        }
        actual = {key: summary[key] for key in expected}
        if not _type_exact_equal(actual, expected):
            raise SystemExit(
                f"aggregate mismatch for {candidate_id}: expected {expected}, found {actual}"
            )

    provenance = corpus["provenance"]
    minimum_n = provenance["minimum_valid_responses_per_candidate"]
    minimum_coverage = provenance["minimum_comparable_coverage"]
    derived_gate = all(
        candidate["valid_responses"] >= minimum_n
        and candidate["reliability"] >= minimum_coverage
        and candidate["deterministically_scored_responses"] >= minimum_n
        for candidate in candidates
    )
    expected_gate = {
        "minimum_valid_responses_per_candidate": minimum_n,
        "minimum_comparable_coverage": minimum_coverage,
        "gate_passed_for_this_slice": derived_gate,
        "whole_corpus_rankable": False,
        "composite_winner_reported": False,
        "reason": "This public text slice meets N and coverage gates, but excludes private/vision tasks, leaves semantic rubrics unscored, and lacks usage/cost plus a declared latency-normalization formula.",
    }
    if not _type_exact_equal(gate, expected_gate):
        raise SystemExit("ranking-gate declaration does not match derived evidence")

    print(f"verified {len(rows)} sanitized rows across {len(declared)} candidates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
