"""Provider-neutral, explainable model selection."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ModelCandidate:
    """A user-declared model capability and cost profile.

    Quality is a user benchmark score from 0 to 1. Cost is optional rate data in
    USD per million tokens; absent rates are not fabricated and are treated as
    unavailable for cost comparison.
    """

    id: str
    provider: str
    model: str
    local: bool = False
    quality: float = 0.5
    latency_ms: float | None = None
    input_cost_per_million: float | None = None
    output_cost_per_million: float | None = None
    capabilities: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not self.id or not self.provider or not self.model:
            raise ValueError("candidate id, provider, and model are required")
        if not 0 <= self.quality <= 1:
            raise ValueError("quality must be between 0 and 1")
        for value in (self.latency_ms, self.input_cost_per_million, self.output_cost_per_million):
            if value is not None and value < 0:
                raise ValueError("latency and token rates cannot be negative")


@dataclass(frozen=True)
class Priorities:
    """Relative importance of cost, latency, and measured quality."""

    cost: float = 1 / 3
    latency: float = 1 / 3
    quality: float = 1 / 3

    def __post_init__(self) -> None:
        if any(value < 0 for value in (self.cost, self.latency, self.quality)):
            raise ValueError("priority weights cannot be negative")
        if self.cost + self.latency + self.quality == 0:
            raise ValueError("at least one priority weight must be positive")

    def normalized(self) -> Mapping[str, float]:
        total = self.cost + self.latency + self.quality
        return {
            "cost": self.cost / total,
            "latency": self.latency / total,
            "quality": self.quality / total,
        }


@dataclass(frozen=True)
class Request:
    local_only: bool = False
    required_capabilities: frozenset[str] = frozenset()
    unavailable_providers: frozenset[str] = frozenset()
    estimated_input_tokens: int = 1_000
    estimated_output_tokens: int = 250

    def __post_init__(self) -> None:
        if self.estimated_input_tokens < 0 or self.estimated_output_tokens < 0:
            raise ValueError("estimated token counts cannot be negative")


@dataclass(frozen=True)
class Decision:
    candidate: ModelCandidate
    reason: str
    excluded: Mapping[str, str] = field(default_factory=dict)
    estimated_cost_usd: float | None = None
    score: float = 0.0
    priorities: Mapping[str, float] = field(default_factory=dict)

    def explain(self) -> str:
        cost = (
            "unknown (supply token rates)"
            if self.estimated_cost_usd is None
            else f"${self.estimated_cost_usd:.6f}"
        )
        weights = ", ".join(f"{name}={value:.2f}" for name, value in self.priorities.items())
        return f"Selected {self.candidate.id}: {self.reason}; estimated cost: {cost}; priority weights: {weights}."


class Router:
    def __init__(self, candidates: list[ModelCandidate], priorities: Priorities | None = None):
        if not candidates:
            raise ValueError("at least one candidate is required")
        if len({candidate.id for candidate in candidates}) != len(candidates):
            raise ValueError("candidate ids must be unique")
        self.candidates = candidates
        self.priorities = priorities or Priorities()

    @staticmethod
    def _cost(candidate: ModelCandidate, request: Request) -> float | None:
        if candidate.input_cost_per_million is None or candidate.output_cost_per_million is None:
            return None
        return (
            (request.estimated_input_tokens * candidate.input_cost_per_million)
            + (request.estimated_output_tokens * candidate.output_cost_per_million)
        ) / 1_000_000

    def choose(self, request: Request) -> Decision:
        eligible: list[ModelCandidate] = []
        excluded: dict[str, str] = {}
        for candidate in self.candidates:
            if candidate.provider in request.unavailable_providers:
                excluded[candidate.id] = "provider unavailable"
            elif request.local_only and not candidate.local:
                excluded[candidate.id] = "not local"
            elif not request.required_capabilities.issubset(candidate.capabilities):
                excluded[candidate.id] = "missing required capabilities"
            else:
                eligible.append(candidate)
        if not eligible:
            raise ValueError("no eligible candidates; relax requirements or add a compatible model")

        costs = {candidate.id: self._cost(candidate, request) for candidate in eligible}
        latencies = {candidate.id: candidate.latency_ms for candidate in eligible}
        known_costs = [value for value in costs.values() if value is not None]
        known_latencies = [value for value in latencies.values() if value is not None]
        max_cost = max(known_costs, default=0.0)
        max_latency = max(known_latencies, default=0.0)
        weights = self.priorities.normalized()

        def score(candidate: ModelCandidate) -> float:
            cost = costs[candidate.id]
            latency = latencies[candidate.id]
            cost_score = 1.0 if max_cost == 0 or cost is None else 1 - (cost / max_cost)
            latency_score = (
                1.0 if max_latency == 0 or latency is None else 1 - (latency / max_latency)
            )
            return (
                weights["cost"] * cost_score
                + weights["latency"] * latency_score
                + weights["quality"] * candidate.quality
            )

        winner = max(
            eligible, key=lambda candidate: (score(candidate), candidate.quality, candidate.id)
        )
        return Decision(
            winner, "best weighted score", excluded, costs[winner.id], score(winner), weights
        )


__all__ = ["Decision", "ModelCandidate", "Priorities", "Request", "Router"]
