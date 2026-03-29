from __future__ import annotations

import json
from pathlib import Path

from run_audit import run_audit

PROJECT_ROOT = Path(__file__).parent.parent
EXAMPLE_WORKFLOW = PROJECT_ROOT / "workflows" / "workflow.example.yml"


def test_full_pipeline(tmp_path):
    result = run_audit(EXAMPLE_WORKFLOW, tmp_path)
    assert isinstance(result, dict)

    expected_files = [
        "audit_results.json",
        "risk_scores.csv",
        "failure_matrix.csv",
        "checkpoints.csv",
        "cost_breakdown.csv",
        "growth_projections.csv",
        "workflow_steps.csv",
        "executive_summary.csv",
        "cost_optimizations.csv",
    ]
    for filename in expected_files:
        path = tmp_path / filename
        assert path.exists(), f"Expected output file missing: {filename}"
        assert path.stat().st_size > 0, f"Expected non-empty file: {filename}"


def test_json_output_schema(tmp_path):
    run_audit(EXAMPLE_WORKFLOW, tmp_path)
    data = json.loads((tmp_path / "audit_results.json").read_text())
    for key in [
        "workflow_name",
        "total_steps",
        "risk_scores",
        "failure_mappings",
        "checkpoints",
        "cost_report",
        "executive_summary",
    ]:
        assert key in data, f"Missing top-level key: {key}"


def test_csv_headers(tmp_path):
    run_audit(EXAMPLE_WORKFLOW, tmp_path)

    def first_line(filename):
        return (tmp_path / filename).read_text().splitlines()[0]

    risk_header = first_line("risk_scores.csv")
    assert risk_header.startswith("step_id,step_name,blast_radius")

    failure_header = first_line("failure_matrix.csv")
    assert failure_header.startswith("step_id,step_name,failure_type")

    checkpoints_header = first_line("checkpoints.csv")
    assert checkpoints_header.startswith("step_id,step_name,checkpoint_type")

    cost_header = first_line("cost_breakdown.csv")
    assert cost_header.startswith("step_id,step_name,model")

    summary_header = first_line("executive_summary.csv")
    assert summary_header.startswith("workflow_name,total_steps")


def test_executive_summary_values(tmp_path):
    results = run_audit(EXAMPLE_WORKFLOW, tmp_path)
    summary = results["executive_summary"]
    assert summary["total_steps"] == 8
    assert summary["monthly_cost"] > 0
    assert summary["cost_per_request"] > 0
