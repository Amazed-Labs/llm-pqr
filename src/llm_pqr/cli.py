"""Small, dependency-free CLI for user-declared routing choices."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from . import ModelCandidate, Priorities, Request, Router
from .evidence import summarize_metrics

EXAMPLE: dict[str, Any] = {
    "priorities": {"cost": 0.35, "latency": 0.25, "quality": 0.40},
    "models": [
        {
            "id": "local-model",
            "provider": "your-local-runtime",
            "model": "replace-me",
            "local": True,
            "quality": 0.65,
            "latency_ms": 900,
            "input_cost_per_million": 0,
            "output_cost_per_million": 0,
            "capabilities": ["text"],
        },
        {
            "id": "hosted-model",
            "provider": "your-provider",
            "model": "replace-me",
            "local": False,
            "quality": 0.85,
            "latency_ms": 1400,
            "input_cost_per_million": 1.0,
            "output_cost_per_million": 3.0,
            "capabilities": ["text", "tools"],
        },
    ],
}


def _load_config(path: str) -> tuple[list[ModelCandidate], Priorities]:
    try:
        payload = json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read JSON config: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("models"), list):
        raise TypeError("config requires a 'models' list")
    try:
        priorities = Priorities(**payload.get("priorities", {}))
        candidates = [
            ModelCandidate(**{**row, "capabilities": frozenset(row.get("capabilities", []))})
            for row in payload["models"]
        ]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid model configuration: {exc}") from exc
    return candidates, priorities


def _choose(args: argparse.Namespace) -> int:
    candidates, priorities = _load_config(args.config)
    request = Request(
        local_only=args.local_only,
        required_capabilities=frozenset(args.require or []),
        estimated_input_tokens=args.input_tokens,
        estimated_output_tokens=args.output_tokens,
    )
    decision = Router(candidates, priorities).choose(request)
    print(
        json.dumps(
            {
                "selected": {
                    "id": decision.candidate.id,
                    "provider": decision.candidate.provider,
                    "model": decision.candidate.model,
                    "local": decision.candidate.local,
                },
                "reason": decision.reason,
                "score": round(decision.score, 6),
                "estimated_cost_usd": decision.estimated_cost_usd,
                "excluded": decision.excluded,
                "explanation": decision.explain(),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _init(args: argparse.Namespace) -> int:
    output = Path(args.output)
    if output.exists() and not args.force:
        raise ValueError(f"refusing to overwrite {output}; use --force")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(EXAMPLE, indent=2) + "\n")
    print(f"Wrote editable example: {output}")
    return 0


def _summarize(args: argparse.Namespace) -> int:
    print(json.dumps(summarize_metrics(args.metrics), indent=2, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="llm-pqr", description="Test your models. Pick with evidence."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="write an editable model configuration")
    init.add_argument("--output", default="models.json")
    init.add_argument("--force", action="store_true")
    init.set_defaults(handler=_init)
    choose = sub.add_parser("choose", help="select a model using your priorities")
    choose.add_argument("--config", required=True)
    choose.add_argument("--input-tokens", type=int, default=1000)
    choose.add_argument("--output-tokens", type=int, default=250)
    choose.add_argument("--local-only", action="store_true")
    choose.add_argument("--require", action="append", help="required capability; repeatable")
    choose.set_defaults(handler=_choose)
    summarize = sub.add_parser("summarize", help="summarize content-free route metadata from JSONL")
    summarize.add_argument("metrics", help="content-free JSONL file")
    summarize.set_defaults(handler=_summarize)
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (TypeError, ValueError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
