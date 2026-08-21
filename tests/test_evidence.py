import json
from pathlib import Path

import pytest

from llm_pqr.evidence import summarize_metrics

FIXTURE = Path(__file__).parent / "fixtures" / "pre-llm-pqr-evals.jsonl"
ROUTES = frozenset({"minimax", "terra", "qwen", "sol"})
REASONS = frozenset(
    {"routine:ordinary", "complex:code", "private:local-only", "consequential:external-action"}
)


def _summarize(path):
    return summarize_metrics(path, allowed_routes=ROUTES, allowed_reasons=REASONS)


def test_pre_eval_fixture_reports_route_outcomes_and_latency():
    summary = _summarize(FIXTURE)

    assert summary["rows"] == 4
    assert summary["successes"] == 2
    assert summary["success_rate"] == pytest.approx(0.5)
    assert summary["routes"]["terra"]["latency_ms"] == {"p50": 3100.0, "p95": 3100.0}
    assert summary["outcomes"] == {
        "failed": 1,
        "interrupted": 1,
        "success": 2,
    }


def _write_row(path, **overrides):
    row = {
        "route": "terra",
        "reason": "routine:ordinary",
        "latency_ms": 100,
        "outcome": "success",
        **overrides,
    }
    path.write_text(json.dumps(row) + "\n")


def test_summarize_metrics_rejects_content_or_identity_fields(tmp_path):
    path = tmp_path / "unsafe.jsonl"
    _write_row(path, prompt="must not be processed")

    with pytest.raises(ValueError, match="unexpected fields: prompt"):
        _summarize(path)


def test_summarize_metrics_rejects_non_finite_latency(tmp_path):
    path = tmp_path / "invalid.jsonl"
    _write_row(path, latency_ms=float("inf"))

    with pytest.raises(ValueError, match="finite and non-negative"):
        _summarize(path)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("route", "user:dov@example.test/private/prompt"),
        ("route", "contains spaces"),
        ("reason", "private response text"),
        ("reason", "reason\nforged-line"),
    ],
)
def test_summarize_metrics_rejects_malformed_taxonomy_values(tmp_path, field, value):
    path = tmp_path / "unsafe-value.jsonl"
    _write_row(path, **{field: value})

    with pytest.raises(ValueError, match=f"{field} must be a bounded taxonomy token"):
        _summarize(path)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("route", "dXNlckBleGFtcGxlLmNvbQ"),
        ("route", "0123456789abcdef0123456789abcdef"),
        ("reason", "secret:U3VwZXJTZWNyZXRUZXh0MTIz"),
        ("reason", "550e8400-e29b-41d4-a716-446655440000"),
    ],
)
def test_summarize_metrics_rejects_unlisted_encoded_or_identifier_tokens(tmp_path, field, value):
    path = tmp_path / "unlisted-value.jsonl"
    _write_row(path, **{field: value})

    with pytest.raises(ValueError, match=f"{field} is not in the allowed taxonomy"):
        _summarize(path)


def test_summarize_metrics_does_not_emit_reason_values():
    summary = _summarize(FIXTURE)
    serialized = json.dumps(summary)
    assert all(reason not in serialized for reason in REASONS)
