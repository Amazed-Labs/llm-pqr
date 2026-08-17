"""Lock the public examples/models.json against silent behavior drift.

These tests use the real CLI to confirm the documented invariants:
- the config loads, has expected providers, and produces the expected
  selection under default weights
- --local-only eliminates hosted candidates
- --require tools narrows to a single capable candidate
- selection is reproducible across runs

They also assert the example's first-line comment warns that values are not
v ranking.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EXAMPLE = REPO / "examples" / "models.json"


def _run(*args: str) -> dict:
    proc = subprocess.run(
        [sys.executable, "-m", "llm_pqr.cli", "choose", "--config", str(EXAMPLE), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_example_carries_illustrative_only_disclaimer():
    text = EXAMPLE.read_text()
    assert "_comment" in text, "example must declare _comment that values are illustrative"
    assert "illustrative" in text.lower()
    assert "not" in text.lower() and "ranking" in text.lower()


def test_example_has_no_real_vendor_labels():
    text = EXAMPLE.read_text()
    payload = json.loads(re.sub(r'"_comment"\s*:\s*"[^"]*"\s*,\s*', "", text, count=1))
    ids = {m["id"] for m in payload["models"]}
    providers = {m["provider"] for m in payload["models"]}
    for value in ids | providers:
        # Reject any vendor product name patterns: only generic placeholders allowed.
        assert re.search(r"your-", value) or "illustrative" in value, (
            f"example exposes a real-looking label: {value!r}; replace with placeholder"
        )


def test_default_selection_is_local_illustrative_with_documented_score():
    out = _run("--input-tokens", "1200", "--output-tokens", "300")
    assert out["selected"]["id"] == "local-illustrative"
    assert round(out["score"], 6) == 0.797619
    assert out["estimated_cost_usd"] == 0.0


def test_local_only_excludes_all_hosted_candidates():
    out = _run("--local-only")
    assert out["selected"]["id"] == "local-illustrative"
    assert set(out["excluded"]) == {"economy-illustrative", "frontier-illustrative"}
    assert all(reason == "not local" for reason in out["excluded"].values())


def test_require_tools_filters_to_capable_candidate_only():
    out = _run("--require", "tools")
    assert out["selected"]["id"] == "frontier-illustrative"
    assert set(out["excluded"]) == {"economy-illustrative", "local-illustrative"}
    assert all(reason == "missing required capabilities" for reason in out["excluded"].values())


def test_selection_is_reproducible_across_runs():
    a = _run("--input-tokens", "1200", "--output-tokens", "300")
    b = _run("--input-tokens", "1200", "--output-tokens", "300")
    assert a == b
