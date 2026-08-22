"""Minimal, auditable smoke-runner for the LLM-PQR routing corpus.

It intentionally measures only a bounded slice. It records every scheduled
invocation, including policy blocks and subprocess failures; it does not rank
models or invent usage/cost telemetry.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[2]
DEFAULT_CORPUS = ROOT / "evals" / "routing-v1.json"


def schedule(
    tasks: list[dict[str, Any]], candidates: list[dict[str, Any]], *, repeats: int, seed: int
) -> list[dict[str, Any]]:
    """Create one immutable row per planned call; local-only cloud calls block before execution."""
    if repeats < 1:
        raise ValueError("repeats must be positive")
    rows: list[dict[str, Any]] = []
    for repeat in range(repeats):
        pairs = [(task, candidate) for task in tasks for candidate in candidates]
        random.Random(seed + repeat).shuffle(pairs)
        for task, candidate in pairs:
            blocked = bool(task["local_only"] and not candidate["local"])
            rows.append(
                {
                    "task_id": task["id"],
                    "candidate_id": candidate["id"],
                    "repeat": repeat + 1,
                    "status": "policy_blocked" if blocked else "scheduled",
                    "failure_class": "locality_policy" if blocked else None,
                }
            )
    return rows


def _strict_json_loads(text: str) -> Any:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def reject_constant(value: str) -> Any:
        raise ValueError(f"non-standard JSON constant: {value}")

    return json.loads(
        text,
        object_pairs_hook=reject_duplicates,
        parse_constant=reject_constant,
    )


def _json_type_exact_equal(actual: Any, expected: Any) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(
            _json_type_exact_equal(actual[key], value) for key, value in expected.items()
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            _json_type_exact_equal(left, right) for left, right in zip(actual, expected)
        )
    return actual == expected


def _score(task: dict[str, Any], text: str) -> bool | None:
    """Return deterministic smoke-score where the rubric is mechanically decidable."""
    rubric = task["rubric"]
    if rubric["kind"] == "exact":
        return text.strip() == rubric["expected"]
    if rubric["kind"] == "contains_all":
        lowered = text.lower()
        return all(term.lower() in lowered for term in rubric["required"]) and not any(
            term.lower() in lowered for term in rubric.get("must_not_include", [])
        )
    if rubric["kind"] in {"json_exact", "json_fields"}:
        candidate = text.strip()
        if candidate.startswith("```"):
            lines = candidate.splitlines()
            if len(lines) < 3 or lines[0] not in {"```", "```json"} or lines[-1] != "```":
                return False
            candidate = "\n".join(lines[1:-1]).strip()
        try:
            parsed = _strict_json_loads(candidate)
        except (json.JSONDecodeError, ValueError):
            return False
        if rubric["kind"] == "json_exact":
            return _json_type_exact_equal(parsed, rubric["expected"])
        if not isinstance(parsed, dict):
            return False
        if any(
            key not in parsed or not _json_type_exact_equal(parsed[key], expected)
            for key, expected in rubric["expected"].items()
        ):
            return False
        for key, required in rubric.get("required_contains", {}).items():
            if not isinstance(required, str) or not required or key not in parsed:
                return False
            actual = parsed[key]
            if not isinstance(actual, str) or required.lower() not in actual.lower():
                return False
        return True
    return None


def normalize_cli_output(stdout: str) -> str:
    """Strip known Hermes one-shot wrapper lines without altering model content."""
    return "\n".join(
        line
        for line in stdout.splitlines()
        if not line.startswith("Warning: Unknown toolsets:") and not line.startswith("session_id:")
    ).strip()


def run_row(
    row: dict[str, Any], tasks: dict[str, dict[str, Any]], candidates: dict[str, dict[str, Any]]
) -> None:
    if row["status"] != "scheduled":
        return
    task, candidate = tasks[row["task_id"]], candidates[row["candidate_id"]]
    if task["modality"] != "text":
        row.update(status="not_run", failure_class="unsupported_modality")
        return
    started = time.monotonic()
    # Corpus prompts are synthetic and explicitly non-sensitive. The command
    # record deliberately excludes the prompt so result artifacts remain clean.
    command = [
        "hermes",
        "chat",
        "-Q",
        "-q",
        task["prompt"],
        "--model",
        candidate["model"],
        "--provider",
        candidate["provider"],
        "--toolsets",
        "__pqr_no_tools__",
        "--max-turns",
        "1",
        "--ignore-rules",
        "--source",
        "tool",
    ]
    try:
        completed = subprocess.run(
            command, text=True, capture_output=True, timeout=120, check=False
        )
    except subprocess.TimeoutExpired:
        row.update(
            status="failed",
            failure_class="timeout",
            latency_ms=round((time.monotonic() - started) * 1000, 1),
        )
        return
    response = normalize_cli_output(completed.stdout)
    row.update(
        status="valid_response" if completed.returncode == 0 and response else "failed",
        failure_class=None if completed.returncode == 0 and response else "provider_or_cli",
        exit_code=completed.returncode,
        latency_ms=round((time.monotonic() - started) * 1000, 1),
        response=response[:2000],
        response_sha256=hashlib.sha256(response.encode()).hexdigest(),
        usage=None,
        usage_source=None,
        cost_usd=None,
        command=[item for item in command if item != task["prompt"]],
    )
    if row["status"] == "valid_response":
        row["score"] = _score(task, response)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--task-ids", required=True, help="Comma-separated task ids")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    corpus = json.loads(args.corpus.read_text())
    candidate_data = json.loads(args.candidates.read_text())
    candidates = candidate_data["candidates"]
    wanted = set(args.task_ids.split(","))
    tasks = [task for task in corpus["tasks"] if task["id"] in wanted]
    if {task["id"] for task in tasks} != wanted:
        raise ValueError("unknown task id")
    if any(task["modality"] != "text" for task in tasks):
        raise ValueError("this lean smoke runner supports text tasks only")

    rows = schedule(
        tasks, candidates, repeats=args.repeats, seed=corpus["provenance"]["randomization_seed"]
    )
    task_map, candidate_map = (
        {task["id"]: task for task in tasks},
        {item["id"]: item for item in candidates},
    )
    for row in rows:
        run_row(row, task_map, candidate_map)

    artifact = {
        "schema_version": "1.0",
        "run_id": uuid.uuid4().hex,
        "corpus_id": corpus["corpus_id"],
        "corpus_sha256": hashlib.sha256(args.corpus.read_bytes()).hexdigest(),
        "rows": rows,
        "ranking": "withheld: smoke run below corpus minimum-N",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2) + "\n")
    print(json.dumps({"run_id": artifact["run_id"], "rows": len(rows), "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
