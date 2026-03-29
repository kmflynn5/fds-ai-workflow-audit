from __future__ import annotations

from pathlib import Path

from engine.failure_mapper import (
    FailureMapping,
    FailureType,
    RiskLevel,
    map_failures,
)
from engine.parser import build_step_graph, parse_workflow

PROJECT_ROOT = Path(__file__).parent.parent
EXAMPLE_YAML = PROJECT_ROOT / "workflows" / "workflow.example.yml"


def _load():
    config = parse_workflow(EXAMPLE_YAML)
    graph = build_step_graph(config)
    return config, graph


def test_tool_selection_error_flagged() -> None:
    """resolve has 3 tools — should produce a HIGH tool_selection_error mapping."""
    config, graph = _load()
    failures = map_failures(config, graph)

    resolve_tool_errors = [
        f for f in failures if f.step_id == "resolve" and f.failure_type == FailureType.tool_selection_error
    ]
    assert len(resolve_tool_errors) == 1
    assert resolve_tool_errors[0].risk_level == RiskLevel.high


def test_silent_failure_customer_facing() -> None:
    """respond is ai_generation + customer_facing=True — should produce a HIGH silent_failure mapping."""
    config, graph = _load()
    failures = map_failures(config, graph)

    respond_silent = [f for f in failures if f.step_id == "respond" and f.failure_type == FailureType.silent_failure]
    assert len(respond_silent) == 1
    assert respond_silent[0].risk_level == RiskLevel.high


def test_no_tools_ai_classification_gets_low_tool_error() -> None:
    """classify has no tools but has a model — should produce a LOW tool_selection_error (fix #4)."""
    config, graph = _load()
    failures = map_failures(config, graph)

    classify_tool_errors = [
        f for f in failures if f.step_id == "classify" and f.failure_type == FailureType.tool_selection_error
    ]
    assert len(classify_tool_errors) == 1
    assert classify_tool_errors[0].risk_level == RiskLevel.low


def test_cascading_failure() -> None:
    """escalation_check branches to both resolve and human_handoff, and resolve has further descendants.

    The descendants of escalation_check are: resolve, respond, log, human_handoff — that's 4,
    so it should produce a HIGH cascading_failure mapping.
    """
    config, graph = _load()
    failures = map_failures(config, graph)

    cascade = [
        f for f in failures if f.step_id == "escalation_check" and f.failure_type == FailureType.cascading_failure
    ]
    assert len(cascade) == 1
    assert cascade[0].risk_level == RiskLevel.high


def test_map_failures_returns_all() -> None:
    """map_failures returns a non-empty list; every entry has a valid FailureType and RiskLevel."""
    config, graph = _load()
    failures = map_failures(config, graph)

    assert len(failures) > 0
    valid_failure_types = set(FailureType)
    valid_risk_levels = set(RiskLevel)
    for f in failures:
        assert isinstance(f, FailureMapping)
        assert f.failure_type in valid_failure_types
        assert f.risk_level in valid_risk_levels
        assert f.step_id
        assert f.step_name
        assert f.rationale
        assert f.mitigation


def test_input_step_no_ai_failures() -> None:
    """intake is type=input — it should have no context_degradation or specification_drift mappings."""
    config, graph = _load()
    failures = map_failures(config, graph)

    intake_ai_failures = [
        f
        for f in failures
        if f.step_id == "intake"
        and f.failure_type in {FailureType.context_degradation, FailureType.specification_drift}
    ]
    assert len(intake_ai_failures) == 0
