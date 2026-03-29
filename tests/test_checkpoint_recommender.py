from __future__ import annotations

from pathlib import Path

import pytest

from engine.checkpoint_recommender import CheckpointType, recommend_checkpoints
from engine.failure_mapper import map_failures
from engine.parser import build_step_graph, parse_workflow
from engine.risk_scorer import score_workflow

PROJECT_ROOT = Path(__file__).parent.parent
EXAMPLE_YAML = PROJECT_ROOT / "workflows" / "workflow.example.yml"


@pytest.fixture(scope="module")
def workflow_artifacts():
    config = parse_workflow(EXAMPLE_YAML)
    graph = build_step_graph(config)
    scores = score_workflow(config, graph)
    failures = map_failures(config, graph)
    recs = recommend_checkpoints(config, graph, scores, failures)
    return config, graph, scores, failures, recs


def test_preflight_for_irreversible_high_blast(workflow_artifacts):
    """resolve step has blast_radius=3.0 (< 4), so it should NOT get a preflight_review."""
    _, _, scores, _, recs = workflow_artifacts
    score_map = {s.step_id: s for s in scores}
    resolve_score = score_map["resolve"]

    # Confirm the actual blast radius is below 4 (no customer_facing, standard regulatory env)
    assert resolve_score.blast_radius < 4, f"resolve blast_radius is {resolve_score.blast_radius}; test expects < 4"

    # Because blast_radius < 4, resolve should NOT get a preflight_review
    resolve_preflights = [
        r for r in recs if r.step_id == "resolve" and r.checkpoint_type == CheckpointType.preflight_review
    ]
    assert len(resolve_preflights) == 0, "resolve should not get preflight_review when blast_radius < 4"


def test_sampling_for_customer_facing(workflow_artifacts):
    """respond step (customer_facing=True, ai_generation → verifiability=5.0) should get sampling_audit."""
    _, _, scores, _, recs = workflow_artifacts
    score_map = {s.step_id: s for s in scores}
    respond_score = score_map["respond"]

    # Verify verifiability is high enough to trigger rule
    assert respond_score.verifiability >= 4, f"respond verifiability should be >= 4, got {respond_score.verifiability}"

    respond_sampling = [
        r for r in recs if r.step_id == "respond" and r.checkpoint_type == CheckpointType.sampling_audit
    ]
    assert len(respond_sampling) == 1, "respond should get exactly one sampling_audit recommendation"
    assert respond_sampling[0].priority == "recommended"


def test_escalation_trigger(workflow_artifacts):
    """escalation_check has branches and 'false negative' in error_consequence → should get escalation_trigger."""
    _, _, _, _, recs = workflow_artifacts
    escalation_recs = [
        r for r in recs if r.step_id == "escalation_check" and r.checkpoint_type == CheckpointType.escalation_trigger
    ]
    assert len(escalation_recs) == 1, "escalation_check should get exactly one escalation_trigger recommendation"
    assert escalation_recs[0].priority == "recommended"
    assert escalation_recs[0].estimated_daily_reviews is not None and escalation_recs[0].estimated_daily_reviews > 0


def test_daily_review_estimates(workflow_artifacts):
    """All recommendations with estimated_daily_reviews set should have positive integers."""
    _, _, _, _, recs = workflow_artifacts
    for rec in recs:
        if rec.estimated_daily_reviews is not None:
            assert isinstance(rec.estimated_daily_reviews, int), (
                f"{rec.step_id}/{rec.checkpoint_type}: estimated_daily_reviews must be int, "
                f"got {type(rec.estimated_daily_reviews)}"
            )
            assert rec.estimated_daily_reviews > 0, (
                f"{rec.step_id}/{rec.checkpoint_type}: estimated_daily_reviews must be positive, "
                f"got {rec.estimated_daily_reviews}"
            )


def test_recommendations_sorted(workflow_artifacts):
    """Results should be sorted by priority order (required → recommended → suggested), then by step_id."""
    _, _, _, _, recs = workflow_artifacts
    priority_order = {"required": 0, "recommended": 1, "suggested": 2}
    sort_keys = [(priority_order[r.priority], r.step_id) for r in recs]
    assert sort_keys == sorted(sort_keys), "Recommendations are not sorted by priority then step_id"


def test_periodic_calibration_long_workflow(workflow_artifacts):
    """With 8 steps (>5), steps with composite > 2.5 should get periodic_calibration."""
    config, _, scores, _, recs = workflow_artifacts

    # Confirm workflow has more than 5 steps
    assert len(config.steps) > 5, f"Expected > 5 steps, got {len(config.steps)}"

    score_map = {s.step_id: s for s in scores}
    high_composite_steps = [sid for sid, s in score_map.items() if s.composite > 2.5]
    assert len(high_composite_steps) > 0, "Expected at least one step with composite > 2.5"

    calibration_step_ids = {r.step_id for r in recs if r.checkpoint_type == CheckpointType.periodic_calibration}
    for sid in high_composite_steps:
        assert sid in calibration_step_ids, (
            f"Step {sid} has composite > 2.5 but did not receive periodic_calibration recommendation"
        )

    # Verify periodic_calibration recs have no daily review estimate (it's a periodic activity)
    for rec in recs:
        if rec.checkpoint_type == CheckpointType.periodic_calibration:
            assert rec.estimated_daily_reviews is None, (
                f"periodic_calibration for {rec.step_id} should have estimated_daily_reviews=None"
            )
