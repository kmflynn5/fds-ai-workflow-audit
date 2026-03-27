from __future__ import annotations

from enum import StrEnum
from pathlib import Path

import networkx as nx
import yaml
from pydantic import BaseModel, Field


class StepType(StrEnum):
    input = "input"
    ai_generation = "ai_generation"
    ai_classification = "ai_classification"
    ai_action = "ai_action"
    human_review = "human_review"
    data_lookup = "data_lookup"
    external_api = "external_api"


class DataSensitivity(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class RegulatoryEnvironment(StrEnum):
    standard = "standard"
    regulated = "regulated"
    critical = "critical"


class BrandRisk(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


class DataClassification(StrEnum):
    public = "public"
    internal = "internal"
    PII = "PII"
    PHI = "PHI"
    financial = "financial"


class WorkflowStep(BaseModel):
    id: str
    name: str
    type: StepType
    description: str
    model: str | None = None
    estimated_tokens_in: int | None = None
    estimated_tokens_out: int | None = None
    error_consequence: str | None = None
    reversible: bool = True
    data_sensitivity: DataSensitivity = DataSensitivity.low
    customer_facing: bool = False
    depends_on: list[str] = Field(default_factory=list)
    branches: dict[str, str] | None = None
    tools: list[str] = Field(default_factory=list)


class WorkflowMetadata(BaseModel):
    name: str
    description: str
    owner: str
    environment: str = "production"


class VolumeProfile(BaseModel):
    requests_per_day: int
    peak_multiplier: float = 1.0
    growth_rate_monthly_pct: float = 0.0


class RiskProfile(BaseModel):
    regulatory_environment: RegulatoryEnvironment = RegulatoryEnvironment.standard
    customer_facing: bool = False
    financial_impact_per_error: float = 0.0
    brand_risk: BrandRisk = BrandRisk.low
    data_classification: DataClassification = DataClassification.public


class OtherService(BaseModel):
    name: str
    monthly_cost: float = 0.0


class SnowflakeConfig(BaseModel):
    enabled: bool = False
    credit_price: float = 3.0
    estimated_credits_per_day: float = 0.0


class InfrastructureConfig(BaseModel):
    snowflake: SnowflakeConfig = Field(default_factory=SnowflakeConfig)
    other_services: list[OtherService] = Field(default_factory=list)


class WorkflowConfig(BaseModel):
    workflow: WorkflowMetadata
    steps: list[WorkflowStep]
    volume: VolumeProfile
    risk: RiskProfile = Field(default_factory=RiskProfile)
    pricing_overrides: dict[str, dict[str, float]] = Field(default_factory=dict)
    infrastructure: InfrastructureConfig = Field(default_factory=InfrastructureConfig)


def parse_workflow(path: str | Path) -> WorkflowConfig:
    """Load a workflow YAML file and validate it with Pydantic."""
    path = Path(path)
    with path.open("r") as f:
        raw = yaml.safe_load(f)
    return WorkflowConfig.model_validate(raw)


def build_step_graph(config: WorkflowConfig) -> nx.DiGraph:
    """Build a DAG from the workflow steps using depends_on and branches."""
    graph = nx.DiGraph()

    for step in config.steps:
        graph.add_node(step.id, step=step)

    for step in config.steps:
        for dep in step.depends_on:
            graph.add_edge(dep, step.id)

        if step.branches:
            for _label, target_id in step.branches.items():
                graph.add_edge(step.id, target_id)

    return graph
