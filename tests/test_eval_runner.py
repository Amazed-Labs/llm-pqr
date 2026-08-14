import json
from pathlib import Path

from llm_pqr.eval_runner import schedule

CORPUS = Path(__file__).parents[1] / "evals" / "routing-v1.json"


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
