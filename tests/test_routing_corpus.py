import json
from pathlib import Path

CORPUS = Path(__file__).parents[1] / "evals" / "routing-v1.json"
VALID_RUBRICS = {"exact", "json_exact", "json_fields", "contains_all", "semantic"}


def test_routing_v1_is_synthetic_and_evaluation_ready():
    corpus = json.loads(CORPUS.read_text())
    assert corpus["schema_version"] == "1.0"
    assert corpus["corpus_id"] == "routing-v1"
    assert len(corpus["tasks"]) == 20
    assert len({task["id"] for task in corpus["tasks"]}) == len(corpus["tasks"])
    assert corpus["provenance"]["minimum_repeats_per_task"] >= 3
    assert corpus["scoring"]["privacy_gate"]
    assert corpus["scoring"]["ranking_gate"]


def test_routing_v1_tasks_have_enforceable_labels_and_rubrics():
    corpus = json.loads(CORPUS.read_text())
    for task in corpus["tasks"]:
        assert task["class"] in {
            "mechanical",
            "routine",
            "private",
            "consequential",
            "reasoning",
            "adversarial",
        }
        assert task["modality"] in {"text", "image"}
        assert isinstance(task["local_only"], bool)
        assert task["required_capabilities"]
        assert task["prompt"]
        assert task["rubric"]["kind"] in VALID_RUBRICS
        if task["modality"] == "image":
            assert task["local_only"] is True
            assert "vision" in task["required_capabilities"]
            assert task["fixture"].startswith("fixtures/")


def test_private_tasks_are_technically_local_only():
    corpus = json.loads(CORPUS.read_text())
    private = [task for task in corpus["tasks"] if task["class"] == "private"]
    assert len(private) >= 4
    assert all(task["local_only"] for task in private)
