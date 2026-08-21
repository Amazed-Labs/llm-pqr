import json
from pathlib import Path

import pytest

from llm_pqr.evidence import summarize_metrics

FIXTURE = Path(__file__).parent / "fixtures" / "pre-llm-pqr-evals.jsonl"


def test_pre_eval_fixture_reports_route_outcomes_and_latency():
    summary = summarize_metrics(FIXTURE)

    assert summary["rows"] == 4
    assert summary["successes"] == 2
    assert summary["success_rate"] == pytest.approx(0.5)
    assert summary["routes"]["terra"]["latency_ms"] == {"p50": 3100.0, "p95": 3100.0}
    assert summary["outcomes"] == {
        "failed": 1,
        "interrupted": 1,
        "success": 2,
    }


def test_summarize_metrics_rejects_content_or_identity_fields(tmp_path):
    path = tmp_path / "unsafe.jsonl"
    path.write_text(
        json.dumps(
            {
                "route": "terra",
                "reason": "routine:ordinary",
                "latency_ms": 100,
                "outcome": "success",
                "prompt": "must not be processed",
            }
        )
        + "\n"
    )

    with pytest.raises(ValueError, match="unexpected fields: prompt"):
        summarize_metrics(path)


def test_summarize_metrics_rejects_non_finite_latency(tmp_path):
    path = tmp_path / "invalid.jsonl"
    path.write_text(
        json.dumps(
            {
                "route": "terra",
                "reason": "routine:ordinary",
                "latency_ms": float("inf"),
                "outcome": "success",
            }
        )
        + "\n"
    )

    with pytest.raises(ValueError, match="finite and non-negative"):
        summarize_metrics(path)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("route", "user:dov@example.test/private/prompt"),
        ("route", "contains spaces"),
        ("reason", "private response text"),
        ("reason", "reason\nforged-line"),
    ],
)
def test_summarize_metrics_rejects_content_shaped_taxonomy_values(tmp_path, field, value):
    path = tmp_path / "unsafe-value.jsonl"
    row = {
        "route": "terra",
        "reason": "routine:ordinary",
        "latency_ms": 100,
        "outcome": "success",
    }
    row[field] = value
    path.write_text(json.dumps(row) + "\n")

    with pytest.raises(ValueError, match=f"{field} must be a bounded taxonomy token"):
        summarize_metrics(path)
