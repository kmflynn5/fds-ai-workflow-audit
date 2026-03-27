from __future__ import annotations

from pathlib import Path

import pytest

from engine.cost_calculator import (
    calculate_costs,
    calculate_infra_cost,
    calculate_step_cost,
    load_model_pricing,
    project_growth,
    suggest_optimizations,
)
from engine.parser import (
    InfrastructureConfig,
    OtherService,
    SnowflakeConfig,
    StepType,
    VolumeProfile,
    WorkflowStep,
    parse_workflow,
)

PROJECT_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_step(
    step_id: str,
    step_type: StepType,
    model: str,
    tokens_in: int,
    tokens_out: int,
) -> WorkflowStep:
    return WorkflowStep(
        id=step_id,
        name=step_id,
        type=step_type,
        description="test step",
        model=model,
        estimated_tokens_in=tokens_in,
        estimated_tokens_out=tokens_out,
    )


def _make_infra(
    snowflake_enabled: bool = True,
    credit_price: float = 3.0,
    credits_per_day: float = 5.0,
    other_monthly: float = 20.0,
) -> InfrastructureConfig:
    return InfrastructureConfig(
        snowflake=SnowflakeConfig(
            enabled=snowflake_enabled,
            credit_price=credit_price,
            estimated_credits_per_day=credits_per_day,
        ),
        other_services=[OtherService(name="other", monthly_cost=other_monthly)],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_load_model_pricing() -> None:
    pricing = load_model_pricing()
    assert "claude-haiku-4-5" in pricing
    assert pricing["claude-haiku-4-5"]["input"] == pytest.approx(0.80)
    assert pricing["claude-haiku-4-5"]["output"] == pytest.approx(4.00)


def test_step_cost_haiku() -> None:
    """classify step: 500 in, 50 out at haiku prices. cost_per_request = 0.0006. daily = 3.0"""
    pricing = load_model_pricing()
    step = _make_step("classify", StepType.ai_classification, "claude-haiku-4-5", 500, 50)
    sc = calculate_step_cost(step, 5000, pricing, {})
    assert sc is not None
    # (500/1M)*0.80 + (50/1M)*4.00 = 0.0004 + 0.0002 = 0.0006
    assert sc.cost_per_request == pytest.approx(0.0006)
    assert sc.daily_cost == pytest.approx(3.0)


def test_step_cost_sonnet() -> None:
    """resolve step: 1500 in, 500 out at sonnet prices. cost_per_request = 0.012. daily = 60.0"""
    pricing = load_model_pricing()
    step = _make_step("resolve", StepType.ai_action, "claude-sonnet-4-20250514", 1500, 500)
    sc = calculate_step_cost(step, 5000, pricing, {})
    assert sc is not None
    # (1500/1M)*3.00 + (500/1M)*15.00 = 0.0045 + 0.0075 = 0.012
    assert sc.cost_per_request == pytest.approx(0.012)
    assert sc.daily_cost == pytest.approx(60.0)


def test_infra_cost() -> None:
    """Snowflake: 5 credits/day @ $3 = $15/day, $450/month. Other = $20/month. Total = $470/month."""
    infra = _make_infra(snowflake_enabled=True, credit_price=3.0, credits_per_day=5.0, other_monthly=20.0)
    ic = calculate_infra_cost(infra)
    assert ic.snowflake_daily == pytest.approx(15.0)
    assert ic.snowflake_monthly == pytest.approx(450.0)
    assert ic.other_services_monthly == pytest.approx(20.0)
    assert ic.total_infra_monthly == pytest.approx(470.0)


def test_growth_projection() -> None:
    """With 10% monthly growth, 12 entries, monotonically increasing, month 11 ≈ 5000*1.1^11."""
    volume = VolumeProfile(requests_per_day=5000, growth_rate_monthly_pct=10.0)
    projections = project_growth(base_token_monthly=1000.0, infra_monthly=200.0, volume=volume, months=12)

    assert len(projections) == 12
    assert projections[0].daily_volume == 5000
    assert projections[0].month == 0

    # month 11 = 5000 * 1.1^11
    expected_vol_11 = int(5000 * (1.1**11))
    assert projections[11].daily_volume == expected_vol_11

    # Monotonically increasing total costs
    totals = [p.total_monthly_cost for p in projections]
    assert all(totals[i] <= totals[i + 1] for i in range(len(totals) - 1))


def test_full_cost_report() -> None:
    """Run calculate_costs on the example workflow and verify non-zero totals."""
    config = parse_workflow(PROJECT_ROOT / "workflow.example.yml")
    report = calculate_costs(config)

    assert len(report.step_costs) > 0
    assert report.total_token_monthly > 0
    assert report.total_monthly > 0
    assert report.total_annual > 0
    assert report.cost_per_request > 0
    assert len(report.growth_projections) == 12


def test_optimization_suggestions() -> None:
    """Verify suggest_optimizations runs and any suggestions have positive savings."""
    config = parse_workflow(PROJECT_ROOT / "workflow.example.yml")
    pricing = load_model_pricing()

    # Build step_costs the same way calculate_costs does
    from engine.cost_calculator import calculate_step_cost as _csc

    step_costs = []
    for step in config.steps:
        sc = _csc(step, config.volume.requests_per_day, pricing, config.pricing_overrides)
        if sc is not None:
            step_costs.append(sc)

    suggestions = suggest_optimizations(config, step_costs, pricing)

    # All suggestions must have positive savings
    for s in suggestions:
        assert s.estimated_monthly_savings > 0

    # Suggestions should be sorted descending by savings
    savings = [s.estimated_monthly_savings for s in suggestions]
    assert savings == sorted(savings, reverse=True)
