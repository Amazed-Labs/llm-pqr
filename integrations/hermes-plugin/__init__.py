"""Standalone Hermes Agent plugin that consumes LLM-PQR.

Independently maintained by Amazed Labs. This is not an official Nous
Research router. Hermes core does not depend on this package.
"""

from __future__ import annotations

from pathlib import Path

from .adapter import PLUGIN_NAME, RoutingAdapter, format_last_decision

_ADAPTER = RoutingAdapter()


def register(ctx) -> None:
    """Wire middleware, the /pqr command, and the bundled configure skill."""

    ctx.register_middleware("llm_request", _ADAPTER.on_llm_request)
    ctx.register_middleware("llm_execution", _ADAPTER.on_llm_execution)

    def _pqr(_raw_args: str = "", **_kwargs) -> str:
        return format_last_decision(_ADAPTER.last_decision())

    ctx.register_command(
        "pqr",
        _pqr,
        description="Show the last LLM-PQR decision (ids, exclusions, score; never prompts)",
    )

    skills_dir = Path(__file__).resolve().parent / "skills"
    if skills_dir.is_dir():
        for child in sorted(skills_dir.iterdir()):
            skill_md = child / "SKILL.md"
            if child.is_dir() and skill_md.is_file():
                ctx.register_skill(child.name, skill_md)


__all__ = ["PLUGIN_NAME", "register"]
