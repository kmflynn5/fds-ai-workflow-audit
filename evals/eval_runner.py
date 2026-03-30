"""Eval runner — compare audit tool output against expected answer keys.

Usage:
    uv run python evals/eval_runner.py

Prints a per-workflow delta report and a summary scoring table.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Repo root so run_audit is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from run_audit import run_audit  # noqa: E402

# ---------------------------------------------------------------------------
# Answer key definitions
# ---------------------------------------------------------------------------
# Each check is a dict with keys:
#   type: "failure_flag" | "score_threshold" | "checkpoint" | "no_high_flag"
#   step_id: str
#   description: str  (human label)
#   --- for failure_flag ---
#   failure_type: str
#   min_risk: "low" | "medium" | "high"   (any flag at this level or above passes)
#   --- for score_threshold ---
#   dimension: str  (key in risk_scores dict)
#   min_value: float
#   --- for checkpoint ---
#   (no extra fields — just checks a checkpoint entry exists for step_id)
#   --- for no_high_flag ---
#   failure_type: str  (check this type is NOT flagged HIGH for step_id)

_RISK_ORDER = {"low": 0, "medium": 1, "high": 2}


def _risk_ge(actual: str, minimum: str) -> bool:
    return _RISK_ORDER.get(actual, -1) >= _RISK_ORDER.get(minimum, 99)


ANSWER_KEYS: dict[str, dict] = {
    # ------------------------------------------------------------------
    # Tier 1 — CEO Agent
    # ------------------------------------------------------------------
    "ceo_agent": {
        "workflow_path": "evals/workflows/ceo_agent.yml",
        "output_dir": "evals/results/ceo_agent",
        "tier": 1,
        "true_positives": [
            {
                "type": "failure_flag",
                "step_id": "collect_open_brain",
                "description": "Cold-start cascading failure",
                "failure_type": "cascading_failure",
                "min_risk": "high",
            },
            {
                "type": "failure_flag",
                "step_id": "collect_zoho_mail",
                "description": "Silent failure risk HIGH (API returns empty success)",
                "failure_type": "silent_failure",
                "min_risk": "high",
            },
            {
                "type": "failure_flag",
                "step_id": "write_daily_brief",
                "description": "Data quality risk — sycophantic confirmation of upstream lookups",
                "failure_type": "sycophantic_confirmation",
                "min_risk": "medium",
            },
            {
                "type": "failure_flag",
                "step_id": "format_brief",
                "description": "Context degradation risk — long workflow + generation step",
                "failure_type": "context_degradation",
                "min_risk": "high",
            },
            {
                "type": "failure_flag",
                "step_id": "format_brief",
                "description": "Specification drift risk — late-stage generation in long workflow",
                "failure_type": "specification_drift",
                "min_risk": "medium",
            },
            {
                "type": "checkpoint",
                "step_id": "send_email",
                "description": "Irreversibility flag — irreversible customer-facing action needs checkpoint",
            },
            {
                "type": "failure_flag",
                "step_id": "parse_reply",
                "description": "Tool selection risk — model must choose among parse tools",
                "failure_type": "tool_selection_error",
                "min_risk": "low",
            },
            {
                "type": "failure_flag",
                "step_id": "write_decisions",
                "description": "Cascading failure risk — downstream memory corruption if decisions not written",
                "failure_type": "cascading_failure",
                "min_risk": "medium",
            },
        ],
        "false_positive_checks": [
            {
                "type": "no_high_flag",
                "step_id": "collect_github",
                "description": "collect_github should NOT get HIGH cascading flag — proven graceful degradation",
                "failure_type": "cascading_failure",
            },
            {
                "type": "no_high_flag",
                "step_id": "collect_pipeline",
                "description": "collect_pipeline should NOT get HIGH cascading flag — fallback exists",
                "failure_type": "cascading_failure",
            },
            {
                "type": "no_high_flag",
                "step_id": "collect_zoho_calendar",
                "description": "collect_zoho_calendar should NOT get HIGH cascading flag — low blast radius",
                "failure_type": "cascading_failure",
            },
        ],
        "score_thresholds": [
            {
                "step_id": "send_email",
                "description": "send_email reversibility must be 5.0 (irreversible action)",
                "dimension": "reversibility",
                "min_value": 5.0,
            },
        ],
    },

    # ------------------------------------------------------------------
    # Tier 2A — Customer Support Agent
    # ------------------------------------------------------------------
    "customer_support_agent": {
        "workflow_path": "evals/workflows/customer_support_agent.yml",
        "output_dir": "evals/results/customer_support_agent",
        "tier": 2,
        "true_positives": [
            {
                "type": "score_threshold",
                "step_id": "resolve",
                "description": "resolve step composite score > 4.0 (high-stakes account action)",
                "dimension": "composite",
                "min_value": 4.0,
            },
        ],
        "false_positive_checks": [],
        "score_thresholds": [
            {
                "step_id": "resolve",
                "description": "resolve composite > 4.0",
                "dimension": "composite",
                "min_value": 4.0,
            },
        ],
    },

    # ------------------------------------------------------------------
    # Tier 2B — Internal Q&A Bot
    # ------------------------------------------------------------------
    "internal_qa_bot": {
        "workflow_path": "evals/workflows/internal_qa_bot.yml",
        "output_dir": "evals/results/internal_qa_bot",
        "tier": 2,
        "true_positives": [
            {
                "type": "score_threshold",
                "step_id": "generate_answer",
                "description": "generate_answer composite <= 3.0 (low-risk internal tool)",
                "dimension": "composite",
                "min_value": 0.0,
                "max_value": 3.0,
            },
        ],
        "false_positive_checks": [],
        "score_thresholds": [
            {
                "step_id": "_all_",
                "description": "ALL steps must score <= 3.0",
                "dimension": "composite",
                "max_value": 3.0,
            },
        ],
    },

    # ------------------------------------------------------------------
    # Tier 2C — Expense Processor
    # ------------------------------------------------------------------
    "expense_processor": {
        "workflow_path": "evals/workflows/expense_processor.yml",
        "output_dir": "evals/results/expense_processor",
        "tier": 2,
        "true_positives": [
            {
                "type": "score_threshold",
                "step_id": "payment",
                "description": "payment step composite score > 4.5 (financial payment action)",
                "dimension": "composite",
                "min_value": 4.5,
            },
        ],
        "false_positive_checks": [],
        "score_thresholds": [
            {
                "step_id": "payment",
                "description": "payment composite > 4.5 (tests scoring ceiling)",
                "dimension": "composite",
                "min_value": 4.5,
            },
        ],
    },

    # ------------------------------------------------------------------
    # Tier 3A — Hidden Write
    # ------------------------------------------------------------------
    "hidden_write": {
        "workflow_path": "evals/workflows/hidden_write.yml",
        "output_dir": "evals/results/hidden_write",
        "tier": 3,
        "true_positives": [
            {
                "type": "score_threshold",
                "step_id": "enrich_and_update",
                "description": "enrich_and_update must score > 3.0 — irreversible write disguised as read",
                "dimension": "composite",
                "min_value": 3.0,
            },
        ],
        "false_positive_checks": [],
        "score_thresholds": [],
    },

    # ------------------------------------------------------------------
    # Tier 3B — Frequency Bomb
    # ------------------------------------------------------------------
    "frequency_bomb": {
        "workflow_path": "evals/workflows/frequency_bomb.yml",
        "output_dir": "evals/results/frequency_bomb",
        "tier": 3,
        "true_positives": [
            {
                "type": "score_threshold",
                "step_id": "batch_processor",
                "description": "batch_processor frequency dimension must reflect effective 10k/day, scoring >= 4.0",
                "dimension": "frequency",
                "min_value": 4.0,
            },
        ],
        "false_positive_checks": [],
        "score_thresholds": [],
    },

    # ------------------------------------------------------------------
    # Tier 3C — Cascading Chain
    # ------------------------------------------------------------------
    "cascading_chain": {
        "workflow_path": "evals/workflows/cascading_chain.yml",
        "output_dir": "evals/results/cascading_chain",
        "tier": 3,
        "true_positives": [
            {
                "type": "failure_flag",
                "step_id": "step_01",
                "description": "step_01 cascading failure flagged HIGH (9 downstream steps)",
                "failure_type": "cascading_failure",
                "min_risk": "high",
            },
            {
                "type": "failure_flag",
                "step_id": "step_06",
                "description": "step_06 context_degradation flagged (long chain, mid-point generation)",
                "failure_type": "context_degradation",
                "min_risk": "medium",
            },
            {
                "type": "score_threshold",
                "step_id": "step_10",
                "description": "step_10 (publish) must flag as checkpoint_level required or recommended",
                "dimension": "composite",
                "min_value": 3.5,
            },
        ],
        "false_positive_checks": [],
        "score_thresholds": [],
    },
}


# ---------------------------------------------------------------------------
# Check runner
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    description: str
    passed: bool
    detail: str


@dataclass
class WorkflowEvalResult:
    workflow_key: str
    tier: int
    tp_results: list[CheckResult] = field(default_factory=list)
    fp_results: list[CheckResult] = field(default_factory=list)
    score_results: list[CheckResult] = field(default_factory=list)

    @property
    def tp_pass(self) -> int:
        return sum(1 for r in self.tp_results if r.passed)

    @property
    def tp_miss(self) -> int:
        return sum(1 for r in self.tp_results if not r.passed)

    @property
    def fp_count(self) -> int:
        """Number of false positives (checks that should NOT flag but did)."""
        return sum(1 for r in self.fp_results if not r.passed)

    @property
    def score_pass(self) -> int:
        return sum(1 for r in self.score_results if r.passed)

    @property
    def score_miss(self) -> int:
        return sum(1 for r in self.score_results if not r.passed)


def _load_or_run(key: str, ak: dict) -> dict:
    """Return results dict — load cached JSON if exists, else run audit."""
    result_path = Path(ak["output_dir"]) / "audit_results.json"
    if result_path.exists():
        return json.loads(result_path.read_text())
    Path(ak["output_dir"]).mkdir(parents=True, exist_ok=True)
    return run_audit(ak["workflow_path"], ak["output_dir"], sync_evidence=False)


def _check_failure_flag(results: dict, step_id: str, failure_type: str, min_risk: str) -> tuple[bool, str]:
    fms = results["failure_mappings"]
    matches = [fm for fm in fms if fm["step_id"] == step_id and fm["failure_type"] == failure_type]
    if not matches:
        return False, f"No {failure_type} flag found for {step_id}"
    best = max(matches, key=lambda fm: _RISK_ORDER.get(fm["risk_level"], 0))
    if _risk_ge(best["risk_level"], min_risk):
        return True, f"{failure_type} flagged {best['risk_level'].upper()} for {step_id}"
    return False, f"{failure_type} flagged {best['risk_level'].upper()} for {step_id} (need >= {min_risk})"


def _check_score_threshold(results: dict, step_id: str, dimension: str, min_value: float | None, max_value: float | None) -> tuple[bool, str]:
    if step_id == "_all_":
        scores = results["risk_scores"]
        violations = [s for s in scores if max_value is not None and s[dimension] > max_value]
        if violations:
            worst = max(violations, key=lambda s: s[dimension])
            return False, f"Step '{worst['step_id']}' scored {worst[dimension]:.2f} > {max_value} on {dimension}"
        return True, f"All steps <= {max_value} on {dimension}"

    score = next((s for s in results["risk_scores"] if s["step_id"] == step_id), None)
    if score is None:
        return False, f"Step {step_id} not found in risk_scores"
    val = score[dimension]
    checks = []
    if min_value is not None and val < min_value:
        checks.append(f"{val:.2f} < required {min_value}")
    if max_value is not None and val > max_value:
        checks.append(f"{val:.2f} > maximum {max_value}")
    if checks:
        return False, f"{step_id}.{dimension} = {val:.2f}: {'; '.join(checks)}"
    return True, f"{step_id}.{dimension} = {val:.2f}"


def _check_checkpoint(results: dict, step_id: str) -> tuple[bool, str]:
    cps = results["checkpoints"]
    matches = [cp for cp in cps if cp["step_id"] == step_id]
    if matches:
        best = min(matches, key=lambda cp: {"required": 0, "recommended": 1, "suggested": 2}.get(cp["priority"], 99))
        return True, f"Checkpoint '{best['checkpoint_type']}' ({best['priority']}) found for {step_id}"
    return False, f"No checkpoint recommendation found for {step_id}"


def _check_no_high_flag(results: dict, step_id: str, failure_type: str) -> tuple[bool, str]:
    """Returns True (PASSES) if the step does NOT have a high flag — meaning no false positive."""
    fms = results["failure_mappings"]
    high_matches = [fm for fm in fms if fm["step_id"] == step_id and fm["failure_type"] == failure_type and fm["risk_level"] == "high"]
    if high_matches:
        return False, f"FALSE POSITIVE: {step_id} incorrectly flagged {failure_type} HIGH"
    return True, f"Correctly NOT flagged {failure_type} HIGH for {step_id}"


def run_eval(workflow_key: str) -> WorkflowEvalResult:
    ak = ANSWER_KEYS[workflow_key]
    results = _load_or_run(workflow_key, ak)
    ev = WorkflowEvalResult(workflow_key=workflow_key, tier=ak["tier"])

    # True positive checks
    for tp in ak["true_positives"]:
        desc = tp["description"]
        if tp["type"] == "failure_flag":
            passed, detail = _check_failure_flag(results, tp["step_id"], tp["failure_type"], tp["min_risk"])
        elif tp["type"] == "score_threshold":
            passed, detail = _check_score_threshold(
                results,
                tp["step_id"],
                tp["dimension"],
                tp.get("min_value"),
                tp.get("max_value"),
            )
        elif tp["type"] == "checkpoint":
            passed, detail = _check_checkpoint(results, tp["step_id"])
        else:
            passed, detail = False, f"Unknown check type: {tp['type']}"
        ev.tp_results.append(CheckResult(desc, passed, detail))

    # False positive checks
    for fp in ak["false_positive_checks"]:
        passed, detail = _check_no_high_flag(results, fp["step_id"], fp["failure_type"])
        ev.fp_results.append(CheckResult(fp["description"], passed, detail))

    # Extra score threshold checks (separate from TP)
    for st in ak["score_thresholds"]:
        passed, detail = _check_score_threshold(
            results,
            st["step_id"],
            st["dimension"],
            st.get("min_value"),
            st.get("max_value"),
        )
        ev.score_results.append(CheckResult(st["description"], passed, detail))

    return ev


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_delta_report(ev: WorkflowEvalResult) -> None:
    print(f"\n{'=' * 70}")
    print(f"  TIER {ev.tier} | {ev.workflow_key.upper().replace('_', ' ')}")
    print(f"{'=' * 70}")

    if ev.tp_results:
        print(f"\n  TRUE POSITIVE CHECKS ({ev.tp_pass}/{len(ev.tp_results)} hits)")
        print(f"  {'-' * 66}")
        for r in ev.tp_results:
            tag = "HIT  " if r.passed else "MISS "
            print(f"  [{tag}] {r.description}")
            print(f"          -> {r.detail}")

    if ev.fp_results:
        fp_count = ev.fp_count
        fp_pass = len(ev.fp_results) - fp_count
        print(f"\n  FALSE POSITIVE CHECKS ({fp_pass}/{len(ev.fp_results)} correctly not flagged)")
        print(f"  {'-' * 66}")
        for r in ev.fp_results:
            tag = "OK   " if r.passed else "FP   "
            print(f"  [{tag}] {r.description}")
            print(f"          -> {r.detail}")

    if ev.score_results:
        print(f"\n  SCORE THRESHOLD CHECKS ({ev.score_pass}/{len(ev.score_results)} pass)")
        print(f"  {'-' * 66}")
        for r in ev.score_results:
            tag = "PASS " if r.passed else "FAIL "
            print(f"  [{tag}] {r.description}")
            print(f"          -> {r.detail}")


def print_summary_table(eval_results: list[WorkflowEvalResult]) -> None:
    print(f"\n\n{'=' * 70}")
    print("  EVAL SUMMARY TABLE")
    print(f"{'=' * 70}")

    tier_tp = {1: (0, 0), 2: (0, 0), 3: (0, 0)}
    all_fp_pass, all_fp_total = 0, 0
    all_score_pass, all_score_total = 0, 0

    for ev in eval_results:
        p, t = tier_tp[ev.tier]
        tier_tp[ev.tier] = (p + ev.tp_pass, t + len(ev.tp_results))
        all_fp_pass += len(ev.fp_results) - ev.fp_count
        all_fp_total += len(ev.fp_results)
        all_score_pass += ev.score_pass
        all_score_total += len(ev.score_results)

    def pct(p, t):
        return f"{p}/{t} ({100*p//t if t else 0}%)"

    t1p, t1t = tier_tp[1]
    t2p, t2t = tier_tp[2]
    t3p, t3t = tier_tp[3]

    rows = [
        ("True positive rate (Tier 1)", "100%", pct(t1p, t1t)),
        ("True positive rate (Tier 2)", "90%+", pct(t2p, t2t)),
        ("True positive rate (Tier 3)", "90%+", pct(t3p, t3t)),
        ("False positive rate (correctly NOT flagged)", ">90%", pct(all_fp_pass, all_fp_total) if all_fp_total else "N/A"),
        ("Score threshold accuracy", "80%+", pct(all_score_pass, all_score_total) if all_score_total else "N/A"),
    ]

    col_w = [50, 8, 18]
    header = f"  {'Metric':<{col_w[0]}} {'Target':<{col_w[1]}} {'Actual':<{col_w[2]}}"
    print(header)
    print(f"  {'-'*col_w[0]} {'-'*col_w[1]} {'-'*col_w[2]}")
    for metric, target, actual in rows:
        print(f"  {metric:<{col_w[0]}} {target:<{col_w[1]}} {actual:<{col_w[2]}}")


def eval_workflow(workflow_path: str, answer_key_path: str | None = None) -> tuple[int, int, int, dict]:
    """Public API: run audit and compare against answer key.

    Args:
        workflow_path: Path to workflow YAML.
        answer_key_path: Unused — answer keys are defined in this module.

    Returns:
        (pass_count, miss_count, false_positive_count, delta_report)
    """
    # Match workflow_path to a key
    p = Path(workflow_path)
    key = p.stem
    if key not in ANSWER_KEYS:
        raise ValueError(f"No answer key for '{key}'. Available: {list(ANSWER_KEYS)}")
    ev = run_eval(key)
    delta = {
        "workflow": key,
        "tier": ev.tier,
        "tp_hits": ev.tp_pass,
        "tp_misses": ev.tp_miss,
        "false_positives": ev.fp_count,
        "tp_details": [{"description": r.description, "passed": r.passed, "detail": r.detail} for r in ev.tp_results],
        "fp_details": [{"description": r.description, "passed": r.passed, "detail": r.detail} for r in ev.fp_results],
    }
    return ev.tp_pass, ev.tp_miss, ev.fp_count, delta


def main() -> None:
    eval_results = [run_eval(key) for key in ANSWER_KEYS]
    for ev in eval_results:
        print_delta_report(ev)
    print_summary_table(eval_results)


if __name__ == "__main__":
    main()
