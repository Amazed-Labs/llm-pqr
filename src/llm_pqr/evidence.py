"""Privacy-safe summaries for local LLM-PQR route metadata."""

from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

_ALLOWED_FIELDS = frozenset({"route", "reason", "latency_ms", "outcome"})
_ALLOWED_OUTCOMES = frozenset(
    {"success", "empty", "failed", "interrupted", "failed_closed", "policy_blocked"}
)
_ROUTE_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
_REASON_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:;,+-]{0,255}")


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _validated_row(
    raw: Any,
    line_number: int,
    allowed_routes: frozenset[str],
    allowed_reasons: frozenset[str],
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise TypeError(f"line {line_number}: expected a JSON object")
    unexpected = sorted(set(raw) - _ALLOWED_FIELDS)
    if unexpected:
        raise ValueError(f"line {line_number}: unexpected fields: {', '.join(unexpected)}")
    missing = sorted(_ALLOWED_FIELDS - set(raw))
    if missing:
        raise ValueError(f"line {line_number}: missing fields: {', '.join(missing)}")
    if not isinstance(raw["route"], str):
        raise TypeError(f"line {line_number}: route must be a string")
    if _ROUTE_TOKEN.fullmatch(raw["route"]) is None:
        raise ValueError(f"line {line_number}: route must be a bounded taxonomy token")
    if raw["route"] not in allowed_routes:
        raise ValueError(f"line {line_number}: route is not in the allowed taxonomy")
    if not isinstance(raw["reason"], str):
        raise TypeError(f"line {line_number}: reason must be a string")
    if _REASON_TOKEN.fullmatch(raw["reason"]) is None:
        raise ValueError(f"line {line_number}: reason must be a bounded taxonomy token")
    if raw["reason"] not in allowed_reasons:
        raise ValueError(f"line {line_number}: reason is not in the allowed taxonomy")
    if raw["outcome"] not in _ALLOWED_OUTCOMES:
        raise ValueError(f"line {line_number}: invalid outcome")
    latency = raw["latency_ms"]
    if isinstance(latency, bool) or not isinstance(latency, (int, float)):
        raise TypeError(f"line {line_number}: latency_ms must be numeric")
    latency = float(latency)
    if not math.isfinite(latency) or latency < 0:
        raise ValueError(f"line {line_number}: latency_ms must be finite and non-negative")
    return {**raw, "route": raw["route"].strip(), "latency_ms": latency}


def summarize_metrics(
    path: str | Path,
    *,
    allowed_routes: frozenset[str],
    allowed_reasons: frozenset[str],
) -> dict[str, Any]:
    """Summarize JSONL only when every taxonomy value is explicitly allowed."""
    if not allowed_routes or not allowed_reasons:
        raise ValueError("allowed route and reason taxonomies must be non-empty")
    if any(_ROUTE_TOKEN.fullmatch(value) is None for value in allowed_routes):
        raise ValueError("allowed routes contain a malformed taxonomy token")
    if any(_REASON_TOKEN.fullmatch(value) is None for value in allowed_reasons):
        raise ValueError("allowed reasons contain a malformed taxonomy token")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(Path(path).read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {line_number}: invalid JSON") from exc
        rows.append(_validated_row(raw, line_number, allowed_routes, allowed_reasons))
    if not rows:
        raise ValueError("metrics file contains no rows")

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["route"]].append(row)

    routes: dict[str, Any] = {}
    for route in sorted(grouped):
        route_rows = grouped[route]
        successes = sum(row["outcome"] == "success" for row in route_rows)
        latencies = [row["latency_ms"] for row in route_rows]
        routes[route] = {
            "rows": len(route_rows),
            "successes": successes,
            "success_rate": successes / len(route_rows),
            "latency_ms": {
                "p50": round(_percentile(latencies, 0.50), 1),
                "p95": round(_percentile(latencies, 0.95), 1),
            },
        }

    successes = sum(row["outcome"] == "success" for row in rows)
    return {
        "rows": len(rows),
        "successes": successes,
        "success_rate": successes / len(rows),
        "outcomes": dict(sorted(Counter(row["outcome"] for row in rows).items())),
        "routes": routes,
    }
