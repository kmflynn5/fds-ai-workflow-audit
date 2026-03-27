from __future__ import annotations

from pathlib import Path

import pytest

from run_audit import run_audit

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
PROJECT_ROOT = Path(__file__).parent.parent

_example_files = sorted(EXAMPLES_DIR.glob("*.yml"))
_all_files = [str(PROJECT_ROOT / "workflow.example.yml")] + [str(f) for f in _example_files]
_all_ids = ["workflow.example"] + [f.stem for f in _example_files]


@pytest.fixture(params=_all_files, ids=_all_ids)
def example_path(request):
    return request.param


def test_all_examples_parse(example_path):
    """Each example YAML parses without error."""
    from engine.parser import parse_workflow

    config = parse_workflow(example_path)
    assert len(config.steps) > 0


def test_all_examples_full_pipeline(example_path, tmp_path):
    """Each example runs through the full audit pipeline."""
    results = run_audit(example_path, tmp_path)
    assert results["total_steps"] > 0
    assert results["executive_summary"]["monthly_cost"] >= 0
    assert len(results["risk_scores"]) > 0
    assert len(results["failure_mappings"]) > 0
