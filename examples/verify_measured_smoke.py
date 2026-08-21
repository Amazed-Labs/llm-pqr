"""Verify the measured smoke aggregate from its checked-in sanitized rows."""

from __future__ import annotations

import json
import statistics
from pathlib import Path

SOURCE = Path(__file__).with_name("measured-smoke-20260814.json")


def main() -> int:
    payload = json.loads(SOURCE.read_text())
    if payload.get("schema_version") != "1.0":
        raise SystemExit("unsupported measured-smoke schema")
    rows = payload["normalized_rows"]
    declared = {row["id"]: row for row in payload["candidates"]}
    if len(rows) != 24:
        raise SystemExit(f"expected 24 normalized rows, found {len(rows)}")
    if len(declared) != len(payload["candidates"]):
        raise SystemExit("candidate IDs must be unique")
    allowed_statuses = {"valid_response", "policy_blocked"}
    seen = set()
    for row in rows:
        key = (row.get("task_id"), row.get("candidate_id"), row.get("repeat"))
        if None in key or key in seen:
            raise SystemExit(f"invalid or duplicate row key: {key}")
        seen.add(key)
        if row.get("status") not in allowed_statuses:
            raise SystemExit(f"invalid row status: {row.get('status')}")
        if row["candidate_id"] not in declared:
            raise SystemExit(f"row references undeclared candidate: {row['candidate_id']}")

    for candidate_id, summary in declared.items():
        candidate_rows = [row for row in rows if row["candidate_id"] == candidate_id]
        valid = [row for row in candidate_rows if row["status"] == "valid_response"]
        scored = [row for row in valid if isinstance(row.get("score"), bool)]
        if not scored:
            raise SystemExit(f"candidate has no scored valid responses: {candidate_id}")
        latencies = [float(row["latency_ms"]) for row in valid]
        expected = {
            "scheduled_rows": len(candidate_rows),
            "valid_responses": len(valid),
            "policy_blocks": sum(row["status"] == "policy_blocked" for row in candidate_rows),
            "passed_rubrics": sum(row["score"] for row in scored),
            "quality": round(sum(row["score"] for row in scored) / len(scored), 6),
            "latency_ms": round(statistics.median(latencies), 1),
        }
        actual = {key: summary[key] for key in expected}
        if actual != expected:
            raise SystemExit(
                f"aggregate mismatch for {candidate_id}: expected {expected}, found {actual}"
            )

    print(f"verified {len(rows)} sanitized rows across {len(declared)} candidates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
