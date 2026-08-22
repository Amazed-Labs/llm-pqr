import json
from pathlib import Path

from llm_pqr.eval_runner import DEFAULT_CORPUS, _score, normalize_cli_output, schedule

CORPUS = Path(__file__).parents[1] / "evals" / "routing-v1.json"


def test_normalize_cli_output_removes_wrapper_lines_only():
    raw = "Warning: Unknown toolsets: __pqr_no_tools__\n\nsession_id: abc\nSAFE\n"
    assert normalize_cli_output(raw) == "SAFE"


def test_runner_default_corpus_points_to_checked_in_artifact():
    assert DEFAULT_CORPUS.resolve() == CORPUS.resolve()
    assert DEFAULT_CORPUS.is_file()


def test_schedule_blocks_cloud_candidates_for_local_only_tasks():
    corpus = json.loads(CORPUS.read_text())
    tasks = [task for task in corpus["tasks"] if task["id"] in {"mech-001", "private-001"}]
    candidates = [
        {"id": "local", "provider": "local-qwen", "model": "qwen", "local": True},
        {"id": "cloud", "provider": "openai-codex", "model": "luna", "local": False},
    ]

    rows = schedule(tasks, candidates, repeats=1, seed=7)

    assert len(rows) == 4
    assert sum(row["status"] == "policy_blocked" for row in rows) == 1
    assert all(
        row["candidate_id"] != "cloud"
        or row["task_id"] != "private-001"
        or row["status"] == "policy_blocked"
        for row in rows
    )


def test_schedule_is_reproducible_and_records_every_invocation():
    corpus = json.loads(CORPUS.read_text())
    tasks = corpus["tasks"][:2]
    candidates = [{"id": "local", "provider": "local", "model": "qwen", "local": True}]

    first = schedule(tasks, candidates, repeats=3, seed=20260814)
    second = schedule(tasks, candidates, repeats=3, seed=20260814)

    assert first == second
    assert len(first) == 6
    assert all(row["status"] == "scheduled" for row in first)


def test_score_json_exact_requires_the_exact_parsed_value():
    task = {"rubric": {"kind": "json_exact", "expected": {"accepted": True, "count": 3}}}

    assert _score(task, '{"accepted": true, "count": 3}') is True
    assert _score(task, '```json\n{"accepted": true, "count": 3}\n```') is True
    assert _score(task, '{"accepted": true, "count": 4}') is False
    assert _score(task, "not json") is False
    assert _score(task, '```json {"accepted": true, "count": 3}```') is False


def test_score_json_exact_is_type_sensitive_and_rejects_ambiguous_json():
    assert _score({"rubric": {"kind": "json_exact", "expected": {"x": True}}}, '{"x": 1}') is False
    assert _score({"rubric": {"kind": "json_exact", "expected": {"x": 1}}}, '{"x": 1.0}') is False
    assert (
        _score({"rubric": {"kind": "json_exact", "expected": {"x": 2}}}, '{"x": 1, "x": 2}')
        is False
    )
    assert _score({"rubric": {"kind": "json_exact", "expected": {"x": 1}}}, '{"x": NaN}') is False


def test_score_json_fields_checks_values_and_required_substrings():
    task = {
        "rubric": {
            "kind": "json_fields",
            "expected": {"allow": False},
            "required_contains": {"reason": "confirm"},
        }
    }

    assert _score(task, '{"allow": false, "reason": "Confirm amount and recipient"}') is True
    assert _score(task, '{"allow": false, "reason": "proceed now"}') is False
    assert _score(task, '{"allow": true, "reason": "confirm"}') is False


def test_score_json_fields_requires_present_type_exact_fields():
    missing_null = {"rubric": {"kind": "json_fields", "expected": {"x": None}}}
    empty_contains = {
        "rubric": {"kind": "json_fields", "expected": {}, "required_contains": {"reason": ""}}
    }

    assert _score(missing_null, "{}") is False
    assert _score(missing_null, '{"x": null}') is True
    assert _score(empty_contains, "{}") is False


def test_score_contains_all_enforces_negative_constraints():
    task = {
        "rubric": {
            "kind": "contains_all",
            "required": ["confirm", "backup"],
            "must_not_include": ["delete it now"],
        }
    }

    assert _score(task, "Confirm the backup before proceeding.") is True
    assert _score(task, "Confirm the backup, then delete it now.") is False
