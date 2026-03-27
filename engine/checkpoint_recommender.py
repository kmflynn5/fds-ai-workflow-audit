from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import networkx as nx

from engine.failure_mapper import FailureMapping
from engine.parser import WorkflowConfig
from engine.risk_scorer import RiskScores


class CheckpointType(StrEnum):
    preflight_review = "pre-flight review"
    sampling_audit = "sampling audit"
    escalation_trigger = "escalation trigger"
    post_action_verification = "post-action verification"
    periodic_calibration = "periodic calibration"


@dataclass
class CheckpointRecommendation:
    step_id: str
    step_name: str
    checkpoint_type: CheckpointType
    priority: str  # "required" | "recommended" | "suggested"
    rationale: str
    implementation_detail: str
    estimated_daily_reviews: int | None = None


_PRIORITY_ORDER = {"required": 0, "recommended": 1, "suggested": 2}


def recommend_checkpoints(
    config: WorkflowConfig,
    graph: nx.DiGraph,
    risk_scores: list[RiskScores],
    failure_mappings: list[FailureMapping],
) -> list[CheckpointRecommendation]:
    """Generate checkpoint recommendations for each workflow step based on risk scores and step properties."""
    score_map: dict[str, RiskScores] = {rs.step_id: rs for rs in risk_scores}
    volume = config.volume
    results: list[CheckpointRecommendation] = []

    for step in config.steps:
        rs = score_map.get(step.id)
        if rs is None:
            continue

        step_recs: list[CheckpointRecommendation] = []
        got_preflight = False

        # Rule 1: Pre-flight review
        if rs.blast_radius >= 4 and not step.reversible:
            step_recs.append(
                CheckpointRecommendation(
                    step_id=step.id,
                    step_name=step.name,
                    checkpoint_type=CheckpointType.preflight_review,
                    priority="required",
                    rationale="High blast radius with irreversible action requires human pre-approval",
                    implementation_detail="Human must approve before step executes; add approval queue with SLA target",
                    estimated_daily_reviews=volume.requests_per_day,
                )
            )
            got_preflight = True

        # Rule 2: Sampling audit
        if step.customer_facing and rs.verifiability >= 4:
            step_recs.append(
                CheckpointRecommendation(
                    step_id=step.id,
                    step_name=step.name,
                    checkpoint_type=CheckpointType.sampling_audit,
                    priority="recommended",
                    rationale="Customer-facing output with low verifiability needs regular human sampling",
                    implementation_detail="Review 5-10% sample of outputs daily; flag anomalies for full review",
                    estimated_daily_reviews=int(volume.requests_per_day * 0.075),
                )
            )

        # Rule 3: Escalation trigger
        if (
            step.branches is not None
            and step.error_consequence is not None
            and "false negative" in step.error_consequence.lower()
        ):
            step_recs.append(
                CheckpointRecommendation(
                    step_id=step.id,
                    step_name=step.name,
                    checkpoint_type=CheckpointType.escalation_trigger,
                    priority="recommended",
                    rationale="Branch point with false negative risk needs confidence threshold gate",
                    implementation_detail=(
                        "Add confidence threshold (suggest 0.8); route below-threshold cases to human review"
                    ),
                    estimated_daily_reviews=int(volume.requests_per_day * 0.1),
                )
            )

        # Rule 4: Post-action verification
        if step.customer_facing and not step.reversible and rs.blast_radius < 4:
            step_recs.append(
                CheckpointRecommendation(
                    step_id=step.id,
                    step_name=step.name,
                    checkpoint_type=CheckpointType.post_action_verification,
                    priority="recommended",
                    rationale="Irreversible customer-facing output should be verified post-action",
                    implementation_detail="Review flagged interactions within 1 hour; prioritize by sentiment score",
                    estimated_daily_reviews=int(volume.requests_per_day * 0.05),
                )
            )

        # Rule 5: Periodic calibration
        if len(config.steps) > 5 and rs.composite > 2.5:
            step_recs.append(
                CheckpointRecommendation(
                    step_id=step.id,
                    step_name=step.name,
                    checkpoint_type=CheckpointType.periodic_calibration,
                    priority="suggested",
                    rationale="Long workflow benefits from periodic specification re-injection",
                    implementation_detail=(
                        "Weekly eval review; monthly spec refresh; compare output drift against baseline"
                    ),
                    estimated_daily_reviews=None,
                )
            )

        # Rule 6: General checkpoint from composite score
        if rs.checkpoint_level == "required" and not got_preflight:
            step_recs.append(
                CheckpointRecommendation(
                    step_id=step.id,
                    step_name=step.name,
                    checkpoint_type=CheckpointType.post_action_verification,
                    priority="required",
                    rationale="High composite risk score requires mandatory post-action verification",
                    implementation_detail="Review flagged interactions within 1 hour; prioritize by sentiment score",
                    estimated_daily_reviews=int(volume.requests_per_day * 0.05),
                )
            )
        elif rs.checkpoint_level == "recommended" and not step_recs:
            step_recs.append(
                CheckpointRecommendation(
                    step_id=step.id,
                    step_name=step.name,
                    checkpoint_type=CheckpointType.sampling_audit,
                    priority="recommended",
                    rationale="Composite risk score indicates regular sampling is warranted",
                    implementation_detail="Review 5-10% sample of outputs daily; flag anomalies for full review",
                    estimated_daily_reviews=int(volume.requests_per_day * 0.075),
                )
            )

        results.extend(step_recs)

    results.sort(key=lambda r: (_PRIORITY_ORDER.get(r.priority, 99), r.step_id))
    return results
