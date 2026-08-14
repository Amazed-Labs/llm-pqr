"""Compatibility entry point for running the checked-in smoke evaluator."""

from llm_pqr.eval_runner import main

if __name__ == "__main__":
    raise SystemExit(main())
