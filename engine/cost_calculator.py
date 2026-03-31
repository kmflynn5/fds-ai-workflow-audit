from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from engine.parser import InfrastructureConfig, StepType, VolumeProfile, WorkflowConfig, WorkflowStep

MODELS_DIR = Path(__file__).parent.parent / "models"


@dataclass
class StepCost:
    step_id: str
    step_name: str
    model: str | None
    tokens_in_per_request: int
    tokens_out_per_request: int
    cost_per_request: float
    daily_cost: float
    monthly_cost: float
    annual_cost: float


@dataclass
class InfraCost:
    snowflake_daily: float
    snowflake_monthly: float
    other_services_monthly: float
    total_infra_monthly: float


@dataclass
class GrowthProjection:
    month: int
    daily_volume: int
    token_monthly_cost: float
    infra_monthly_cost: float
    total_monthly_cost: float


@dataclass
class CostOptimization:
    step_id: str
    step_name: str
    suggestion: str
    estimated_monthly_savings: float
    category: str  # "model_downgrade" | "caching" | "infra_migration"


@dataclass
class CostReport:
    step_costs: list[StepCost]
    total_token_daily: float
    total_token_monthly: float
    total_token_annual: float
    infra_cost: InfraCost
    total_monthly: float
    total_annual: float
    cost_per_request: float
    growth_projections: list[GrowthProjection]
    optimizations: list[CostOptimization]


def load_model_pricing(pricing_path: str | Path | None = None) -> dict[str, dict[str, float]]:
    """Load model_pricing.yml and return a flat dict keyed by model name."""
    if pricing_path is None:
        pricing_path = MODELS_DIR / "model_pricing.yml"
    pricing_path = Path(pricing_path)
    with pricing_path.open("r") as f:
        raw: dict = yaml.safe_load(f)

    flat: dict[str, dict[str, float]] = {}
    for _provider, models in raw.items():
        for model_name, prices in models.items():
            flat[model_name] = {"input": float(prices["input"]), "output": float(prices["output"])}
    return flat


def resolve_model_price(
    model: str,
    pricing: dict[str, dict[str, float]],
    overrides: dict[str, dict[str, float]],
) -> tuple[float, float]:
    """Return (input_price_per_1M, output_price_per_1M) for the given model.

    Checks overrides first (supporting keys input/output or input_per_1m/output_per_1m),
    then falls back to the pricing catalogue.
    Raises ValueError if the model cannot be found in either source.
    """
    if model in overrides:
        ov = overrides[model]
        inp = ov.get("input_per_1m", ov.get("input"))
        out = ov.get("output_per_1m", ov.get("output"))
        if inp is not None and out is not None:
            return float(inp), float(out)

    if model in pricing:
        return float(pricing[model]["input"]), float(pricing[model]["output"])

    raise ValueError(f"Model '{model}' not found in pricing catalogue or overrides.")


def calculate_step_cost(
    step: WorkflowStep,
    daily_volume: int,
    pricing: dict[str, dict[str, float]],
    overrides: dict[str, dict[str, float]],
) -> StepCost | None:
    """Return a StepCost for the given step, or None if no model/token data is available."""
    if step.model is None or step.estimated_tokens_in is None or step.estimated_tokens_out is None:
        return None

    input_price, output_price = resolve_model_price(step.model, pricing, overrides)

    # Fix R2-4: multiply token estimates by iterations_per_request so batch steps
    # reflect their true per-request token spend (e.g. 500 iterations × 1k tokens = 500k tokens).
    effective_tokens_in = step.estimated_tokens_in * step.iterations_per_request
    effective_tokens_out = step.estimated_tokens_out * step.iterations_per_request

    input_cost = (effective_tokens_in / 1_000_000) * input_price
    output_cost = (effective_tokens_out / 1_000_000) * output_price
    cost_per_request = input_cost + output_cost

    daily = cost_per_request * daily_volume
    monthly = daily * 30
    annual = daily * 365

    return StepCost(
        step_id=step.id,
        step_name=step.name,
        model=step.model,
        tokens_in_per_request=effective_tokens_in,
        tokens_out_per_request=effective_tokens_out,
        cost_per_request=cost_per_request,
        daily_cost=daily,
        monthly_cost=monthly,
        annual_cost=annual,
    )


def calculate_infra_cost(infra: InfrastructureConfig) -> InfraCost:
    """Compute infrastructure costs from the InfrastructureConfig."""
    if infra.snowflake.enabled:
        snowflake_daily = infra.snowflake.estimated_credits_per_day * infra.snowflake.credit_price
    else:
        snowflake_daily = 0.0

    snowflake_monthly = snowflake_daily * 30
    other_monthly = sum(svc.monthly_cost for svc in infra.other_services)
    total = snowflake_monthly + other_monthly

    return InfraCost(
        snowflake_daily=snowflake_daily,
        snowflake_monthly=snowflake_monthly,
        other_services_monthly=other_monthly,
        total_infra_monthly=total,
    )


def project_growth(
    base_token_monthly: float,
    infra_monthly: float,
    volume: VolumeProfile,
    months: int = 12,
) -> list[GrowthProjection]:
    """Return a list of GrowthProjection for each month from 0 to months-1."""
    projections: list[GrowthProjection] = []
    for month in range(months):
        growth_factor = (1 + volume.growth_rate_monthly_pct / 100) ** month
        daily_vol = int(volume.requests_per_day * growth_factor)
        token_cost = base_token_monthly * growth_factor
        total = token_cost + infra_monthly
        projections.append(
            GrowthProjection(
                month=month,
                daily_volume=daily_vol,
                token_monthly_cost=token_cost,
                infra_monthly_cost=infra_monthly,
                total_monthly_cost=total,
            )
        )
    return projections


def suggest_optimizations(
    config: WorkflowConfig,
    step_costs: list[StepCost],
    pricing: dict[str, dict[str, float]],
) -> list[CostOptimization]:
    """Generate cost-saving suggestions based on step types and model choices."""
    suggestions: list[CostOptimization] = []

    # Determine cheapest models available in the pricing catalogue
    cheapest_models = {"claude-haiku-4-5", "gpt-4o-mini"}

    step_cost_map = {sc.step_id: sc for sc in step_costs}

    for step in config.steps:
        if step.model is None:
            continue

        sc = step_cost_map.get(step.id)

        # Suggest model downgrade for classification steps using expensive models
        if step.type == StepType.ai_classification and step.model not in cheapest_models and sc is not None:
            # Pick the cheapest available model that has pricing
            candidate = next((m for m in ("claude-haiku-4-5", "gpt-4o-mini") if m in pricing), None)
            if candidate:
                overrides: dict[str, dict[str, float]] = {}
                cheap_in, cheap_out = resolve_model_price(candidate, pricing, overrides)
                cheap_cost_per_req = (sc.tokens_in_per_request / 1_000_000) * cheap_in + (
                    sc.tokens_out_per_request / 1_000_000
                ) * cheap_out
                cheap_monthly = cheap_cost_per_req * config.volume.requests_per_day * 30
                savings = sc.monthly_cost - cheap_monthly
                if savings > 0:
                    suggestions.append(
                        CostOptimization(
                            step_id=step.id,
                            step_name=step.name,
                            suggestion=f"Downgrade model from '{step.model}' to '{candidate}' for classification task.",
                            estimated_monthly_savings=savings,
                            category="model_downgrade",
                        )
                    )

        # Suggest DuckDB migration for data_lookup steps when Snowflake is enabled
        if step.type == StepType.data_lookup and config.infrastructure.snowflake.enabled:
            snowflake_monthly = (
                config.infrastructure.snowflake.estimated_credits_per_day
                * config.infrastructure.snowflake.credit_price
                * 30
            )
            savings = snowflake_monthly * 0.5
            if savings > 0:
                suggestions.append(
                    CostOptimization(
                        step_id=step.id,
                        step_name=step.name,
                        suggestion="Consider migrating data lookups from Snowflake to DuckDB to reduce compute costs.",
                        estimated_monthly_savings=savings,
                        category="infra_migration",
                    )
                )

    suggestions.sort(key=lambda x: x.estimated_monthly_savings, reverse=True)
    return suggestions


def calculate_costs(config: WorkflowConfig, pricing_path: str | Path | None = None) -> CostReport:
    """Compute a full CostReport for the given WorkflowConfig."""
    pricing = load_model_pricing(pricing_path)
    overrides = config.pricing_overrides

    step_costs: list[StepCost] = []
    for step in config.steps:
        sc = calculate_step_cost(step, config.volume.requests_per_day, pricing, overrides)
        if sc is not None:
            step_costs.append(sc)

    total_token_daily = sum(sc.daily_cost for sc in step_costs)
    total_token_monthly = sum(sc.monthly_cost for sc in step_costs)
    total_token_annual = sum(sc.annual_cost for sc in step_costs)

    infra_cost = calculate_infra_cost(config.infrastructure)

    total_monthly = total_token_monthly + infra_cost.total_infra_monthly
    total_annual = total_token_annual + infra_cost.total_infra_monthly * 12

    daily_volume = config.volume.requests_per_day
    cost_per_request = total_monthly / (daily_volume * 30) if daily_volume > 0 else 0.0

    growth_projections = project_growth(total_token_monthly, infra_cost.total_infra_monthly, config.volume)

    optimizations = suggest_optimizations(config, step_costs, pricing)

    return CostReport(
        step_costs=step_costs,
        total_token_daily=total_token_daily,
        total_token_monthly=total_token_monthly,
        total_token_annual=total_token_annual,
        infra_cost=infra_cost,
        total_monthly=total_monthly,
        total_annual=total_annual,
        cost_per_request=cost_per_request,
        growth_projections=growth_projections,
        optimizations=optimizations,
    )
