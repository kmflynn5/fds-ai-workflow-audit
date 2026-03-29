from __future__ import annotations

from pathlib import Path

import networkx as nx
import pytest
from pydantic import ValidationError

from engine.parser import (
    DataSensitivity,
    StepType,
    WorkflowConfig,
    build_step_graph,
    parse_workflow,
)

EXAMPLE_YAML = Path(__file__).parent.parent / "workflows" / "workflow.example.yml"


def test_parse_example_workflow() -> None:
    config = parse_workflow(EXAMPLE_YAML)

    assert len(config.steps) == 8

    expected_ids = {"intake", "classify", "sentiment", "escalation_check", "resolve", "respond", "log", "human_handoff"}
    actual_ids = {step.id for step in config.steps}
    assert actual_ids == expected_ids

    assert config.workflow.name == "Tier 1 Customer Support Agent"


def test_build_step_graph() -> None:
    config = parse_workflow(EXAMPLE_YAML)
    graph = build_step_graph(config)

    assert nx.is_directed_acyclic_graph(graph)

    assert graph.number_of_nodes() == 8

    assert graph.has_edge("escalation_check", "resolve")
    assert graph.has_edge("resolve", "respond")
    assert graph.has_edge("respond", "log")
    assert graph.has_edge("escalation_check", "human_handoff")
    assert graph.has_edge("classify", "escalation_check")
    assert graph.has_edge("sentiment", "escalation_check")


def test_step_types_parsed() -> None:
    config = parse_workflow(EXAMPLE_YAML)
    step_map = {step.id: step for step in config.steps}

    assert step_map["intake"].type == StepType.input
    assert step_map["classify"].type == StepType.ai_classification
    assert step_map["sentiment"].type == StepType.ai_classification
    assert step_map["escalation_check"].type == StepType.ai_classification
    assert step_map["resolve"].type == StepType.ai_action
    assert step_map["respond"].type == StepType.ai_generation
    assert step_map["log"].type == StepType.ai_action
    assert step_map["human_handoff"].type == StepType.human_review


def test_invalid_yaml_raises() -> None:
    invalid_data = {
        "workflow": {"description": "Missing name", "owner": "Test", "environment": "production"},
        "steps": [],
        "volume": {"requests_per_day": 100},
    }
    with pytest.raises(ValidationError):
        WorkflowConfig.model_validate(invalid_data)


def test_default_values() -> None:
    config = parse_workflow(EXAMPLE_YAML)
    step_map = {step.id: step for step in config.steps}

    # intake has minimal fields set — check defaults apply
    intake = step_map["intake"]
    assert intake.reversible is True
    assert intake.data_sensitivity == DataSensitivity.low
    assert intake.customer_facing is False
    assert intake.depends_on == []
    assert intake.tools == []
    assert intake.model is None
    assert intake.branches is None

    # human_handoff also has minimal fields
    handoff = step_map["human_handoff"]
    assert handoff.reversible is True
    assert handoff.data_sensitivity == DataSensitivity.low
    assert handoff.customer_facing is False
    assert handoff.tools == []
