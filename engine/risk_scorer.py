from __future__ import annotations

import re
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


# Fix #6: keywords indicating a step writes/mutates data despite how it's declared
_WRITE_KEYWORDS = frozenset(
    {
        "write",
        "writes",
        "update",
        "updates",
        "create",
        "creates",
        "modify",
        "modifies",
        "insert",
        "inserts",
        "mutate",
        "mutates",
        "upsert",
        "upserts",
        "delete",
        "deletes",
    }
)

# Fix #7: keywords that indicate a batch/loop pattern
_BATCH_KEYWORDS = frozenset(
    {
        "batch",
        "loop",
        "loops",
        "each record",
        "per record",
        "per item",
        "each item",
        "iterate",
        "iterates",
    }
)

_NUMBER_RE = re.compile(r"\b(\d{3,})\b")


def _has_write_signal(step: WorkflowStep) -> bool:
    """Return True if description contains write-indicating words (word-boundary match)."""
    words = set(re.findall(r"\b\w+\b", step.description.lower()))
    return bool(words & _WRITE_KEYWORDS)


def _is_hidden_write(step: WorkflowStep) -> bool:
    """True if a data_lookup step's description reveals it actually writes data."""
    return step.type == StepType.data_lookup and _has_write_signal(step)


def _heuristic_iterations(step: WorkflowStep) -> int:
    """Return effective iterations per request from explicit field or description heuristic.

    When iterations_per_request is explicitly set to 1 in the YAML, the user has declared
    the actual iteration count — the description-based heuristic is suppressed to avoid
    false positives where numbers in the description (e.g. output batch sizes) are
    misread as call multipliers.  Pydantic v2 tracks which fields were supplied via
    model_fields_set, so we can distinguish "user wrote iterations_per_request: 1" from
    "field was omitted and defaulted to 1".
    """
    if step.iterations_per_request > 1:
        return step.iterations_per_request
    # If the user explicitly declared iterations_per_request: 1, trust it and skip heuristic.
    if "iterations_per_request" in step.model_fields_set:
        return 1
    # Field was not declared — fall back to description-based heuristic.
    desc = step.description.lower()
    has_batch_signal = any(kw in desc for kw in _BATCH_KEYWORDS)
    if not has_batch_signal:
        return 1
    numbers = [int(m) for m in _NUMBER_RE.findall(desc) if int(m) >= 100]
    if numbers:
        return max(numbers)
    return 100  # default multiplier when batch signal found but no specific count


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
    # Fix #6: hidden write in a declared data_lookup raises blast
    if _is_hidden_write(step):
        score += 1.0
    # Financial impact bonus: high-value errors on sensitive steps amplify blast
    if risk_profile.financial_impact_per_error >= 5000 and step.data_sensitivity in (
        DataSensitivity.high,
        DataSensitivity.critical,
    ):
        score += 1.0
    return min(score, 5.0)


def score_reversibility(step: WorkflowStep) -> float:
    # Fix #6: data_lookup that secretly writes is treated as an irreversible action
    if _is_hidden_write(step):
        return 5.0
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


def score_frequency(volume: VolumeProfile, graph: nx.DiGraph, step_id: str, step: WorkflowStep) -> float:
    base_volume = volume.requests_per_day
    predecessors = list(graph.predecessors(step_id))
    if predecessors:
        roots = [n for n in graph.nodes if graph.in_degree(n) == 0]
        min_depth = min(
            (nx.shortest_path_length(graph, root, step_id) for root in roots if nx.has_path(graph, root, step_id)),
            default=1,
        )
        effective_volume = base_volume * (0.8**min_depth)
    else:
        effective_volume = base_volume

    # Fix #7: multiply by iterations_per_request (explicit or heuristic)
    effective_volume *= _heuristic_iterations(step)

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
    # Fix #6: hidden write in a declared data_lookup is as hard to verify as an ai_action
    if _is_hidden_write(step):
        return 3.0
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
) -> float:
    # Fix #2: denominator 7 (was 8) allows max ~4.71, enabling scores > 4.5 for high-risk steps
    raw = (blast * 2 + reversibility * 2 + frequency + verifiability + cascading) / 7
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
        freq = score_frequency(config.volume, graph, step.id, step)
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
