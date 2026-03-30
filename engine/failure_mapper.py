from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

import networkx as nx

from engine.parser import DataSensitivity, StepType, WorkflowConfig, WorkflowStep

_AI_TYPES = {StepType.ai_generation, StepType.ai_classification, StepType.ai_action}

# Fix #6: words that indicate mutation/write behaviour
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


def _has_write_signal(step: WorkflowStep) -> bool:
    words = set(re.findall(r"\b\w+\b", step.description.lower()))
    return bool(words & _WRITE_KEYWORDS)


class FailureType(StrEnum):
    context_degradation = "context_degradation"
    specification_drift = "specification_drift"
    sycophantic_confirmation = "sycophantic_confirmation"
    tool_selection_error = "tool_selection_error"
    cascading_failure = "cascading_failure"
    silent_failure = "silent_failure"
    metadata_inconsistency = "metadata_inconsistency"


class RiskLevel(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


@dataclass
class FailureMapping:
    step_id: str
    step_name: str
    failure_type: FailureType
    risk_level: RiskLevel
    rationale: str
    mitigation: str


def assess_context_degradation(step: WorkflowStep, workflow_length: int) -> FailureMapping | None:
    """Assess risk of context window saturation degrading output quality."""
    if step.type not in _AI_TYPES:
        return None

    if workflow_length > 5 and step.type == StepType.ai_generation:
        risk = RiskLevel.high
        rationale = "Long workflow with generation step risks context window saturation"
        mitigation = "Implement context summarization between steps; re-inject critical context at each generation step"
    elif workflow_length > 5:
        risk = RiskLevel.medium
        rationale = "Multi-step workflow may degrade context quality"
        mitigation = "Monitor output quality metrics across session length"
    else:
        risk = RiskLevel.low
        rationale = "Short workflow; context degradation risk is minimal"
        mitigation = "Standard context monitoring is sufficient"

    return FailureMapping(
        step_id=step.id,
        step_name=step.name,
        failure_type=FailureType.context_degradation,
        risk_level=risk,
        rationale=rationale,
        mitigation=mitigation,
    )


def assess_specification_drift(
    step: WorkflowStep,
    workflow_length: int,
    graph: nx.DiGraph,
    step_id: str,
) -> FailureMapping | None:
    """Assess risk of the model drifting from original task specification at depth."""
    if step.type not in _AI_TYPES:
        return None

    roots = [n for n, d in graph.in_degree() if d == 0]
    if roots:
        depths = [nx.shortest_path_length(graph, root, step_id) for root in roots if nx.has_path(graph, root, step_id)]
        depth = min(depths) if depths else 0
    else:
        depth = 0

    if workflow_length > 5 and depth >= 3:
        risk = RiskLevel.high
        rationale = "Late-stage step in long workflow prone to forgetting original specification"
        mitigation = "Periodic spec re-injection; compare outputs against original requirements at this checkpoint"
    elif workflow_length > 5 or depth >= 2:
        risk = RiskLevel.medium
        rationale = "Step depth or workflow length increases specification drift risk"
        mitigation = "Re-state task objective in system prompt at this step; add output diff against spec baseline"
    else:
        risk = RiskLevel.low
        rationale = "Step is near the workflow root; specification drift is unlikely"
        mitigation = "Include original task specification in system prompt as a precaution"

    return FailureMapping(
        step_id=step.id,
        step_name=step.name,
        failure_type=FailureType.specification_drift,
        risk_level=risk,
        rationale=rationale,
        mitigation=mitigation,
    )


def assess_sycophantic_confirmation(step: WorkflowStep, graph: nx.DiGraph) -> FailureMapping | None:
    """Assess risk of the model confirming incorrect upstream data rather than challenging it."""
    if step.type not in {StepType.ai_generation, StepType.ai_action}:
        return None

    ancestor_ids = nx.ancestors(graph, step.id)
    ancestor_steps: list[WorkflowStep] = [graph.nodes[a]["step"] for a in ancestor_ids if "step" in graph.nodes[a]]
    upstream_has_lookup_or_classification = any(
        s.type in {StepType.data_lookup, StepType.ai_classification} for s in ancestor_steps
    )

    if upstream_has_lookup_or_classification and step.type == StepType.ai_generation:
        risk = RiskLevel.high
        rationale = "Generation step builds on classified/looked-up data — may confirm incorrect upstream data"
        mitigation = (
            "Cross-reference generated output against raw source data; "
            "add validation gate between lookup and generation"
        )
    elif upstream_has_lookup_or_classification and step.type == StepType.ai_action:
        risk = RiskLevel.medium
        rationale = "Action step builds on classified/looked-up data — may propagate upstream errors without challenge"
        mitigation = "Assert expected data shape before executing action; log action parameters for post-hoc review"
    else:
        risk = RiskLevel.low
        rationale = "No upstream classified or looked-up data to blindly confirm"
        mitigation = "Ensure prompt instructs the model to flag uncertainty rather than assume correctness"

    return FailureMapping(
        step_id=step.id,
        step_name=step.name,
        failure_type=FailureType.sycophantic_confirmation,
        risk_level=risk,
        rationale=rationale,
        mitigation=mitigation,
    )


def assess_tool_selection_error(step: WorkflowStep) -> FailureMapping | None:
    """Assess risk of the model choosing the wrong tool from those available."""
    n = len(step.tools)
    if n == 0:
        # Fix #4: AI classification/action/generation with a model but no tools still has
        # tool-selection risk — the model must structure its output entirely without constraints.
        if step.model is not None and step.type in _AI_TYPES:
            return FailureMapping(
                step_id=step.id,
                step_name=step.name,
                failure_type=FailureType.tool_selection_error,
                risk_level=RiskLevel.low,
                rationale="AI step has no tool constraints — output format entirely model-guided",
                mitigation="Define explicit output schema (Pydantic, JSON Schema) and validate against it",
            )
        return None

    if n >= 3:
        risk = RiskLevel.high
        rationale = f"Step has {n} tools available — high risk of selecting wrong tool"
        mitigation = (
            "Add tool-call logging; implement expected-tool assertions; consider restricting available tools per intent"
        )
    elif n == 2:
        risk = RiskLevel.medium
        rationale = "Step has 2 tools — moderate tool selection risk"
        mitigation = "Log tool-call decisions; include explicit selection criteria in system prompt"
    else:
        risk = RiskLevel.low
        rationale = "Step has 1 tool — minimal selection ambiguity"
        mitigation = "Verify the single tool is invoked with correct parameters via parameter schema validation"

    return FailureMapping(
        step_id=step.id,
        step_name=step.name,
        failure_type=FailureType.tool_selection_error,
        risk_level=risk,
        rationale=rationale,
        mitigation=mitigation,
    )


def assess_cascading_failure(step: WorkflowStep, graph: nx.DiGraph) -> FailureMapping | None:
    """Assess how many downstream steps would be affected by a failure here."""
    n = len(nx.descendants(graph, step.id))

    # Fix #5: terminal steps with cross-workflow dependency still have cascading risk
    if n == 0 and not step.cross_workflow_dependency:
        return None

    effective_n = n if n > 0 else 2  # cross-workflow dependency floor

    if effective_n >= 4:
        # Fix #3: downgrade to MEDIUM for steps with documented graceful degradation
        if step.has_graceful_fallback:
            risk = RiskLevel.medium
            rationale = f"Failure cascades to {n} downstream steps; documented graceful degradation limits blast radius"
            mitigation = "Verify fallback path is tested and monitored; track fallback activation rate"
        else:
            risk = RiskLevel.high
            rationale = f"Failure cascades to {n} downstream steps"
            mitigation = "Add per-step validation gate; implement circuit breaker pattern"
    elif effective_n >= 2:
        risk = RiskLevel.medium
        if n == 0:
            rationale = "Terminal step with cross-workflow dependency — failure corrupts future workflow runs"
            mitigation = "Add write-confirmation check; monitor downstream workflow input quality"
        else:
            rationale = f"Failure propagates to {n} downstream steps"
            mitigation = "Add output validation at this step; define a fallback branch for failure cases"
    else:
        risk = RiskLevel.low
        rationale = f"Failure affects {effective_n} downstream step"
        mitigation = "Ensure the downstream step handles missing or malformed input gracefully"

    return FailureMapping(
        step_id=step.id,
        step_name=step.name,
        failure_type=FailureType.cascading_failure,
        risk_level=risk,
        rationale=rationale,
        mitigation=mitigation,
    )


def assess_silent_failure(step: WorkflowStep) -> FailureMapping | None:
    """Assess risk of a failure that produces plausible but incorrect output with no error signal."""
    if step.type == StepType.ai_generation and step.customer_facing:
        risk = RiskLevel.high
        rationale = "Customer-facing generated content may be plausible but functionally incorrect"
        mitigation = "Implement functional correctness evals (not just semantic); add sampling audit for human review"
    elif step.type == StepType.ai_generation:
        risk = RiskLevel.medium
        rationale = "Generated content may appear correct but contain factual errors"
        mitigation = "Add automated factual-consistency checks; route edge-case outputs to human review queue"
    elif step.type == StepType.ai_action:
        risk = RiskLevel.medium
        rationale = "Action may complete successfully but with incorrect parameters"
        mitigation = "Log all action parameters with expected vs. actual diff; add post-action state validation"
    elif step.type == StepType.ai_classification and step.customer_facing:
        risk = RiskLevel.low
        rationale = "Customer-facing classification may silently misroute without visible error"
        mitigation = "Expose classification confidence scores; alert when confidence falls below threshold"
    # Fix #1: data_lookup with high/critical sensitivity can return valid-looking empty/stale data
    elif step.type == StepType.data_lookup and step.data_sensitivity in (
        DataSensitivity.high,
        DataSensitivity.critical,
    ):
        risk = RiskLevel.high
        rationale = "High-sensitivity data source may return valid-looking empty or stale data with no error signal"
        mitigation = "Add non-empty validation gate; alert on unexpectedly low record counts vs. baseline"
    else:
        return None

    return FailureMapping(
        step_id=step.id,
        step_name=step.name,
        failure_type=FailureType.silent_failure,
        risk_level=risk,
        rationale=rationale,
        mitigation=mitigation,
    )


def assess_metadata_inconsistency(step: WorkflowStep) -> FailureMapping | None:
    """Flag steps whose description contradicts their declared type or reversibility.

    Fix #6: detects hidden writes in steps declared as data_lookup or reversible=True.
    """
    if not _has_write_signal(step):
        return None

    if step.type == StepType.data_lookup:
        return FailureMapping(
            step_id=step.id,
            step_name=step.name,
            failure_type=FailureType.metadata_inconsistency,
            risk_level=RiskLevel.high,
            rationale=(
                "Description contains write/mutation keywords but step type is data_lookup — "
                "possible hidden write that bypasses risk controls"
            ),
            mitigation=(
                "Audit step implementation; reclassify as ai_action if state-mutating; "
                "add write-confirmation logging and rollback capability"
            ),
        )

    if step.reversible and step.type in _AI_TYPES:
        return FailureMapping(
            step_id=step.id,
            step_name=step.name,
            failure_type=FailureType.metadata_inconsistency,
            risk_level=RiskLevel.medium,
            rationale=(
                "Step is marked reversible=true but description contains write/mutation keywords — "
                "reversibility claim may be incorrect"
            ),
            mitigation=(
                "Verify that a genuine rollback path exists; add automated rollback test; "
                "set reversible=false if rollback is not implemented"
            ),
        )

    return None


def map_failures(config: WorkflowConfig, graph: nx.DiGraph) -> list[FailureMapping]:
    """Run all failure assessments across all workflow steps and return a sorted flat list."""
    workflow_length = len(config.steps)
    results: list[FailureMapping] = []

    for step in config.steps:
        assessments = [
            assess_context_degradation(step, workflow_length),
            assess_specification_drift(step, workflow_length, graph, step.id),
            assess_sycophantic_confirmation(step, graph),
            assess_tool_selection_error(step),
            assess_cascading_failure(step, graph),
            assess_silent_failure(step),
            assess_metadata_inconsistency(step),
        ]
        results.extend(a for a in assessments if a is not None)

    results.sort(key=lambda m: (m.step_id, m.failure_type))
    return results
