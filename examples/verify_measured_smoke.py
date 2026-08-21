"""Verify the measured smoke aggregate from its checked-in sanitized rows."""

from __future__ import annotations

import json
import statistics
from pathlib import Path

SOURCE = Path(__file__).with_name("measured-smoke-20260814.json")


def main() -> int:
    payload = json.loads(SOURCE.read_text())
    rows = payload["normalized_rows"]
    declared = {row["id"]: row for row in payload["candidates"]}

    for candidate_id, summary in declared.items():
        candidate_rows = [row for row in rows if row["candidate_id"] == candidate_id]
        valid = [row for row in candidate_rows if row["status"] == "valid_response"]
        scored = [row for row in valid if isinstance(row.get("score"), bool)]
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

    unknown = sorted({row["candidate_id"] for row in rows} - set(declared))
    if unknown:
        raise SystemExit(f"rows reference undeclared candidates: {', '.join(unknown)}")
    print(f"verified {len(rows)} sanitized rows across {len(declared)} candidates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
