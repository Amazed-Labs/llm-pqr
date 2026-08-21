import json

from llm_pqr.cli import main


def test_choose_reads_user_models_and_priorities(tmp_path, capsys):
    config = {
        "priorities": {"cost": 0, "latency": 0, "quality": 1},
        "models": [
            {
                "id": "economy",
                "provider": "local",
                "model": "small",
                "local": True,
                "quality": 0.5,
                "latency_ms": 300,
            },
            {
                "id": "best",
                "provider": "api",
                "model": "large",
                "quality": 0.95,
                "latency_ms": 1500,
            },
        ],
    }
    path = tmp_path / "models.json"
    path.write_text(json.dumps(config))

    assert (
        main(["choose", "--config", str(path), "--input-tokens", "100", "--output-tokens", "20"])
        == 0
    )
    output = json.loads(capsys.readouterr().out)
    assert output["selected"]["id"] == "best"
    assert output["reason"] == "best weighted score"


def test_init_writes_editable_example_without_secrets(tmp_path):
    target = tmp_path / "models.json"
    assert main(["init", "--output", str(target)]) == 0
    payload = json.loads(target.read_text())
    assert payload["models"]
    assert "api_key" not in target.read_text().lower()


def test_summarize_prints_privacy_safe_metrics_summary(tmp_path, capsys):
    target = tmp_path / "metrics.jsonl"
    target.write_text(
        json.dumps(
            {
                "route": "terra",
                "reason": "routine:ordinary",
                "latency_ms": 125.0,
                "outcome": "success",
            }
        )
        + "\n"
    )
    taxonomy = tmp_path / "taxonomy.json"
    taxonomy.write_text(json.dumps({"routes": ["terra"], "reasons": ["routine:ordinary"]}) + "\n")

    assert main(["summarize", str(target), "--taxonomy", str(taxonomy)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["rows"] == 1
    assert output["routes"]["terra"]["latency_ms"]["p95"] == 125.0
