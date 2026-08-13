from llm_pqr import ModelCandidate, Priorities, Request, Router


def candidates():
    return [
        ModelCandidate(
            id="local-fast",
            provider="ollama",
            model="qwen-local",
            local=True,
            quality=0.62,
            latency_ms=700,
            input_cost_per_million=0,
            output_cost_per_million=0,
        ),
        ModelCandidate(
            id="cloud-balanced",
            provider="openai-compatible",
            model="balanced-model",
            quality=0.85,
            latency_ms=1200,
            input_cost_per_million=0.5,
            output_cost_per_million=1.5,
        ),
        ModelCandidate(
            id="cloud-accurate",
            provider="anthropic-compatible",
            model="accurate-model",
            quality=0.97,
            latency_ms=3000,
            input_cost_per_million=3,
            output_cost_per_million=15,
        ),
    ]


def test_cost_priority_prefers_lower_estimated_cost():
    router = Router(candidates(), Priorities(cost=0.8, latency=0.1, quality=0.1))
    decision = router.choose(Request(estimated_input_tokens=1_000, estimated_output_tokens=300))
    assert decision.candidate.id == "local-fast"
    assert decision.reason == "best weighted score"


def test_quality_priority_prefers_highest_quality():
    router = Router(candidates(), Priorities(cost=0, latency=0, quality=1))
    decision = router.choose(Request(estimated_input_tokens=1_000, estimated_output_tokens=300))
    assert decision.candidate.id == "cloud-accurate"


def test_local_only_is_hard_constraint_not_a_preference():
    router = Router(candidates(), Priorities(cost=0, latency=0, quality=1))
    decision = router.choose(Request(local_only=True))
    assert decision.candidate.id == "local-fast"
    assert decision.excluded == {"cloud-balanced": "not local", "cloud-accurate": "not local"}


def test_required_capability_filters_candidates():
    models = candidates()
    models[1] = ModelCandidate(**{**models[1].__dict__, "capabilities": frozenset({"tools"})})
    router = Router(models, Priorities(cost=0.2, latency=0.2, quality=0.6))
    decision = router.choose(Request(required_capabilities=frozenset({"tools"})))
    assert decision.candidate.id == "cloud-balanced"


def test_explanation_contains_scores_and_assumptions():
    decision = Router(candidates(), Priorities()).choose(
        Request(estimated_input_tokens=2_000, estimated_output_tokens=500)
    )
    assert "estimated cost" in decision.explain()
    assert "priority weights" in decision.explain()
