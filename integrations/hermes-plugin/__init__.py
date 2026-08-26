"""Standalone Hermes Agent plugin that consumes LLM-PQR.

Independently maintained by Amazed Labs. This is not an official Nous
Research router. Hermes core does not depend on this package.
"""

from __future__ import annotations

import json
from pathlib import Path

from .adapter import PLUGIN_NAME, RoutingAdapter

_ADAPTER = RoutingAdapter()

PQR_STATUS_SCHEMA = {
    "name": "pqr_status",
    "description": (
        "Check whether unofficial LLM-PQR policy routing is idle or live. "
        "Use when the user asks if routing is on, why a turn was blocked, "
        "or whether a config file was found. Returns content-free status: "
        "config path, last selected id, last block reason. Never sends prompts."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}


def _pqr_command(raw_args: str = "", **_kwargs) -> str:
    del raw_args
    return _ADAPTER.status_text()


def _pqr_status_tool(args=None, **kwargs) -> str:
    """Config/status only. Ignore args so prompt text never reaches Router."""

    del args, kwargs
    try:
        return json.dumps(_ADAPTER.status(), indent=2, sort_keys=True)
    except Exception:
        return json.dumps(
            {
                "plugin": PLUGIN_NAME,
                "state": "idle",
                "headline": "status failed; this tool does not change routing",
            }
        )


def register(ctx) -> None:
    """Wire middleware, /pqr, optional status tool, and the configure skill."""

    ctx.register_middleware("llm_request", _ADAPTER.on_llm_request)
    ctx.register_middleware("llm_execution", _ADAPTER.on_llm_execution)

    ctx.register_command(
        "pqr",
        _pqr_command,
        description=(
            "Show LLM-PQR routing status: idle vs live, config path, "
            "last selected id or block reason (never prompts)"
        ),
    )

    if hasattr(ctx, "register_tool"):
        ctx.register_tool(
            name="pqr_status",
            toolset="llm-pqr",
            schema=PQR_STATUS_SCHEMA,
            handler=_pqr_status_tool,
        )

    skills_dir = Path(__file__).resolve().parent / "skills"
    if skills_dir.is_dir():
        for child in sorted(skills_dir.iterdir()):
            skill_md = child / "SKILL.md"
            if child.is_dir() and skill_md.is_file():
                ctx.register_skill(child.name, skill_md)


__all__ = ["PLUGIN_NAME", "register"]
