from __future__ import annotations

from dataclasses import dataclass

import networkx as nx

from engine.parser import (
    DataSensitivity,
    RegulatoryEnvironment,
    RiskProfile,
    StepType,
    VolumeProfile,
    WorkflowConfig,
    WorkflowStep,
)


@dataclass
class RiskScores:
    step_id: str
    step_name: str
    blast_radius: float  # 1-5
    reversibility: float  # 1-5
    frequency: float  # 1-5
    verifiability: float  # 1-5
    cascading_risk: float  # 1-5
    composite: float  # weighted average
    checkpoint_level: str  # "none" | "recommended" | "required"


def score_blast_radius(step: WorkflowStep, risk_profile: RiskProfile) -> float:
    score = 1.0
    if step.customer_facing:
        score += 1.0
    if step.data_sensitivity in (DataSensitivity.high, DataSensitivity.critical):
        score += 1.0
    if step.error_consequence is not None:
        score += 1.0
    if risk_profile.regulatory_environment in (RegulatoryEnvironment.regulated, RegulatoryEnvironment.critical):
        score += 1.0
    return min(score, 5.0)


def score_reversibility(step: WorkflowStep) -> float:
    if step.reversible and not step.tools:
        return 1.0
    if step.reversible and step.tools:
        return 2.0
    # reversible=False cases
    if step.type == StepType.ai_classification:
        return 3.0
    if step.type == StepType.ai_generation:
        return 4.0
    if step.type == StepType.ai_action:
        return 5.0
    return 3.0


def score_frequency(volume: VolumeProfile, graph: nx.DiGraph, step_id: str) -> float:
    base_volume = volume.requests_per_day
    predecessors = list(graph.predecessors(step_id))
    if predecessors:
        # Non-root: estimate depth as length of shortest path from any root
        roots = [n for n in graph.nodes if graph.in_degree(n) == 0]
        min_depth = min(
            (nx.shortest_path_length(graph, root, step_id) for root in roots if nx.has_path(graph, root, step_id)),
            default=1,
        )
        effective_volume = base_volume * (0.8**min_depth)
    else:
        effective_volume = base_volume

    if effective_volume < 10:
        return 1.0
    if effective_volume < 100:
        return 2.0
    if effective_volume < 1000:
        return 3.0
    if effective_volume < 10000:
        return 4.0
    return 5.0


def score_verifiability(step: WorkflowStep) -> float:
    if step.type in (StepType.input, StepType.data_lookup):
        return 1.0
    if step.type == StepType.human_review:
        return 1.0
    if step.type == StepType.ai_classification:
        return 2.0
    if step.type == StepType.external_api:
        return 2.0
    if step.type == StepType.ai_action:
        return 3.0
    if step.type == StepType.ai_generation:
        if step.customer_facing:
            return 5.0
        return 4.0
    return 3.0


def score_cascading_risk(graph: nx.DiGraph, step_id: str) -> float:
    descendant_count = len(nx.descendants(graph, step_id))
    if descendant_count == 0:
        return 1.0
    if descendant_count == 1:
        return 2.0
    if descendant_count <= 3:
        return 3.0
    if descendant_count <= 5:
        return 4.0
    return 5.0


def compute_composite(
    blast: float, reversibility: float, frequency: float, verifiability: float, cascading: float
) -> float:  # noqa: E501
    raw = (blast * 2 + reversibility * 2 + frequency + verifiability + cascading) / 8
    return round(raw, 2)


def classify_checkpoint_level(composite: float) -> str:
    if composite > 4.0:
        return "required"
    if composite > 3.5:
        return "recommended"
    return "none"


def score_workflow(config: WorkflowConfig, graph: nx.DiGraph) -> list[RiskScores]:
    results: list[RiskScores] = []
    for step in config.steps:
        blast = score_blast_radius(step, config.risk)
        rev = score_reversibility(step)
        freq = score_frequency(config.volume, graph, step.id)
        ver = score_verifiability(step)
        casc = score_cascading_risk(graph, step.id)
        composite = compute_composite(blast, rev, freq, ver, casc)
        checkpoint = classify_checkpoint_level(composite)
        results.append(
            RiskScores(
                step_id=step.id,
                step_name=step.name,
                blast_radius=blast,
                reversibility=rev,
                frequency=freq,
                verifiability=ver,
                cascading_risk=casc,
                composite=composite,
                checkpoint_level=checkpoint,
            )
        )
    return results
