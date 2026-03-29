"""AI workflow risk and quality assessment tool."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path

from engine.checkpoint_recommender import recommend_checkpoints
from engine.cost_calculator import calculate_costs
from engine.failure_mapper import map_failures
from engine.parser import build_step_graph, parse_workflow
from engine.risk_scorer import score_workflow


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    """Write a CSV file with the given fieldnames and rows."""
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


EVIDENCE_SOURCES_DIR = Path(__file__).parent / "evidence" / "sources" / "audit_results"


def run_audit(workflow_path: str | Path, output_dir: str | Path = "output", *, sync_evidence: bool = True) -> dict:
    """Run the full audit pipeline and return results as a dict."""
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)

    # Run pipeline
    config = parse_workflow(workflow_path)
    graph = build_step_graph(config)
    risk_scores = score_workflow(config, graph)
    failures = map_failures(config, graph)
    checkpoints = recommend_checkpoints(config, graph, risk_scores, failures)
    costs = calculate_costs(config)

    # Build results dict
    results = build_results(config, risk_scores, failures, checkpoints, costs)

    # Write outputs to output dir and optionally Evidence sources
    csv_dirs = [output_dir]
    if sync_evidence and EVIDENCE_SOURCES_DIR.is_dir():
        csv_dirs.append(EVIDENCE_SOURCES_DIR)

    write_json(output_dir, results)
    for d in csv_dirs:
        write_risk_scores_csv(d, risk_scores)
        write_failure_matrix_csv(d, failures)
        write_checkpoints_csv(d, checkpoints)
        write_cost_breakdown_csv(d, costs)
        write_growth_projections_csv(d, costs)
        write_workflow_steps_csv(d, config)
        write_executive_summary_csv(d, config, risk_scores, failures, checkpoints, costs)
        write_cost_optimizations_csv(d, costs)

    return results


def build_results(config, risk_scores, failures, checkpoints, costs) -> dict:
    """Build the full results dictionary."""
    return {
        "workflow_name": config.workflow.name,
        "workflow_description": config.workflow.description,
        "total_steps": len(config.steps),
        "risk_scores": [asdict(rs) for rs in risk_scores],
        "failure_mappings": [asdict(fm) for fm in failures],
        "checkpoints": [asdict(cp) for cp in checkpoints],
        "cost_report": {
            "step_costs": [asdict(sc) for sc in costs.step_costs],
            "total_token_daily": costs.total_token_daily,
            "total_token_monthly": costs.total_token_monthly,
            "total_token_annual": costs.total_token_annual,
            "infra_cost": asdict(costs.infra_cost),
            "total_monthly": costs.total_monthly,
            "total_annual": costs.total_annual,
            "cost_per_request": costs.cost_per_request,
            "growth_projections": [asdict(gp) for gp in costs.growth_projections],
            "optimizations": [asdict(opt) for opt in costs.optimizations],
        },
        "executive_summary": {
            "workflow_name": config.workflow.name,
            "total_steps": len(config.steps),
            "high_risk_steps": sum(1 for rs in risk_scores if rs.checkpoint_level != "none"),
            "checkpoints_required": sum(1 for cp in checkpoints if cp.priority == "required"),
            "checkpoints_recommended": sum(1 for cp in checkpoints if cp.priority == "recommended"),
            "failure_modes_high": sum(1 for fm in failures if fm.risk_level == "high"),
            "monthly_cost": round(costs.total_monthly, 2),
            "annual_cost": round(costs.total_annual, 2),
            "cost_per_request": round(costs.cost_per_request, 6),
        },
    }


def write_json(output_dir: Path, results: dict) -> None:
    """Write audit_results.json."""
    (output_dir / "audit_results.json").write_text(json.dumps(results, indent=2))


def write_risk_scores_csv(output_dir: Path, risk_scores) -> None:
    """Write risk_scores.csv."""
    fieldnames = [
        "step_id",
        "step_name",
        "blast_radius",
        "reversibility",
        "frequency",
        "verifiability",
        "cascading_risk",
        "composite",
        "checkpoint_level",
    ]
    rows = [asdict(rs) for rs in risk_scores]
    _write_csv(output_dir / "risk_scores.csv", fieldnames, rows)


def write_failure_matrix_csv(output_dir: Path, failures) -> None:
    """Write failure_matrix.csv."""
    fieldnames = ["step_id", "step_name", "failure_type", "risk_level", "rationale", "mitigation"]
    rows = [asdict(fm) for fm in failures]
    _write_csv(output_dir / "failure_matrix.csv", fieldnames, rows)


def write_checkpoints_csv(output_dir: Path, checkpoints) -> None:
    """Write checkpoints.csv."""
    fieldnames = [
        "step_id",
        "step_name",
        "checkpoint_type",
        "priority",
        "rationale",
        "implementation_detail",
        "estimated_daily_reviews",
    ]
    rows = [asdict(cp) for cp in checkpoints]
    _write_csv(output_dir / "checkpoints.csv", fieldnames, rows)


def write_cost_breakdown_csv(output_dir: Path, costs) -> None:
    """Write cost_breakdown.csv."""
    fieldnames = [
        "step_id",
        "step_name",
        "model",
        "tokens_in_per_request",
        "tokens_out_per_request",
        "cost_per_request",
        "daily_cost",
        "monthly_cost",
        "annual_cost",
    ]
    rows = [asdict(sc) for sc in costs.step_costs]
    _write_csv(output_dir / "cost_breakdown.csv", fieldnames, rows)


def write_growth_projections_csv(output_dir: Path, costs) -> None:
    """Write growth_projections.csv."""
    fieldnames = ["month", "daily_volume", "token_monthly_cost", "infra_monthly_cost", "total_monthly_cost"]
    rows = [asdict(gp) for gp in costs.growth_projections]
    _write_csv(output_dir / "growth_projections.csv", fieldnames, rows)


def write_workflow_steps_csv(output_dir: Path, config) -> None:
    """Write workflow_steps.csv."""
    fieldnames = ["step_id", "name", "type", "model", "depends_on", "customer_facing", "reversible", "data_sensitivity"]
    rows = [
        {
            "step_id": step.id,
            "name": step.name,
            "type": step.type,
            "model": step.model,
            "depends_on": ";".join(step.depends_on),
            "customer_facing": step.customer_facing,
            "reversible": step.reversible,
            "data_sensitivity": step.data_sensitivity,
        }
        for step in config.steps
    ]
    _write_csv(output_dir / "workflow_steps.csv", fieldnames, rows)


def write_executive_summary_csv(output_dir: Path, config, risk_scores, failures, checkpoints, costs) -> None:
    """Write executive_summary.csv."""
    fieldnames = [
        "workflow_name",
        "total_steps",
        "high_risk_steps",
        "checkpoints_required",
        "checkpoints_recommended",
        "failure_modes_high",
        "monthly_cost",
        "annual_cost",
        "cost_per_request",
    ]
    row = {
        "workflow_name": config.workflow.name,
        "total_steps": len(config.steps),
        "high_risk_steps": sum(1 for rs in risk_scores if rs.checkpoint_level != "none"),
        "checkpoints_required": sum(1 for cp in checkpoints if cp.priority == "required"),
        "checkpoints_recommended": sum(1 for cp in checkpoints if cp.priority == "recommended"),
        "failure_modes_high": sum(1 for fm in failures if fm.risk_level == "high"),
        "monthly_cost": round(costs.total_monthly, 2),
        "annual_cost": round(costs.total_annual, 2),
        "cost_per_request": round(costs.cost_per_request, 6),
    }
    _write_csv(output_dir / "executive_summary.csv", fieldnames, [row])


def write_cost_optimizations_csv(output_dir: Path, costs) -> None:
    """Write cost_optimizations.csv."""
    fieldnames = ["step_id", "step_name", "suggestion", "estimated_monthly_savings", "category"]
    rows = [asdict(opt) for opt in costs.optimizations]
    if not rows:
        rows = [
            {
                "step_id": "-",
                "step_name": "-",
                "suggestion": "No optimizations identified",
                "estimated_monthly_savings": 0,
                "category": "-",
            }
        ]
    _write_csv(output_dir / "cost_optimizations.csv", fieldnames, rows)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="AI workflow risk and quality assessment tool")
    parser.add_argument(
        "workflow", nargs="?", default="workflows/workflow.example.yml", help="Path to workflow YAML file"
    )
    parser.add_argument("-o", "--output", default="output", help="Output directory (default: output)")
    parser.add_argument("--no-evidence", action="store_true", help="Skip syncing CSVs to Evidence sources directory")
    args = parser.parse_args()

    sync_evidence = not args.no_evidence
    results = run_audit(args.workflow, args.output, sync_evidence=sync_evidence)
    print_summary(results, args.output, sync_evidence)


def print_summary(results: dict, output_dir: str, sync_evidence: bool) -> None:
    """Print a human-readable audit summary to the terminal."""
    s = results["executive_summary"]
    print(f"\n{'=' * 60}")
    print(f"  AUDIT: {s['workflow_name']}")
    print(f"{'=' * 60}")
    print(f"  Steps: {s['total_steps']}  |  High-risk failure modes: {s['failure_modes_high']}")
    monthly = f"${s['monthly_cost']:.2f}"
    annual = f"${s['annual_cost']:.2f}"
    per_req = f"${s['cost_per_request']:.4f}"
    print(f"  Monthly cost: {monthly}  |  Annual: {annual}  |  Per request: {per_req}")

    # Checkpoints
    checkpoints = results["checkpoints"]
    required = [cp for cp in checkpoints if cp["priority"] == "required"]
    recommended = [cp for cp in checkpoints if cp["priority"] == "recommended"]
    if required or recommended:
        print(f"\n  CHECKPOINTS ({len(required)} required, {len(recommended)} recommended)")
        print(f"  {'-' * 56}")
        for cp in required + recommended:
            tag = "REQUIRED" if cp["priority"] == "required" else "recommended"
            reviews = f"  ~{cp['estimated_daily_reviews']}/day" if cp.get("estimated_daily_reviews") else ""
            print(f"  [{tag:>11}]  {cp['step_name']}: {cp['checkpoint_type']}{reviews}")

    # High-risk failure modes
    high_failures = [fm for fm in results["failure_mappings"] if fm["risk_level"] == "high"]
    if high_failures:
        print(f"\n  HIGH-RISK FAILURE MODES ({len(high_failures)})")
        print(f"  {'-' * 56}")
        for fm in high_failures:
            print(f"  {fm['step_name']}: {fm['failure_type'].replace('_', ' ')}")
            print(f"    -> {fm['mitigation']}")

    # Cost optimizations
    optimizations = results["cost_report"]["optimizations"]
    if optimizations:
        print(f"\n  COST OPTIMIZATIONS ({len(optimizations)})")
        print(f"  {'-' * 56}")
        for opt in optimizations:
            print(f"  {opt['step_name']}: {opt['suggestion']}")
            print(f"    -> saves ~${opt['estimated_monthly_savings']:.2f}/month")

    # Top risk steps
    risk_scores = sorted(results["risk_scores"], key=lambda r: r["composite"], reverse=True)
    top = [r for r in risk_scores if r["composite"] >= 2.5]
    if top:
        print("\n  TOP RISK STEPS")
        print(f"  {'-' * 56}")
        for r in top[:5]:
            print(f"  {r['composite']:.1f}  {r['step_name']}")

    print(f"\n  Results written to {output_dir}/")
    if sync_evidence and EVIDENCE_SOURCES_DIR.is_dir():
        print("  Evidence sources synced — run: cd evidence && npm run sources && npm run dev")
    print()


if __name__ == "__main__":
    main()
