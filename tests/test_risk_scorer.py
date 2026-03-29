from __future__ import annotations

from pathlib import Path

import networkx as nx
import pytest

from engine.parser import VolumeProfile, build_step_graph, parse_workflow
from engine.risk_scorer import (
    classify_checkpoint_level,
    compute_composite,
    score_cascading_risk,
    score_frequency,
    score_workflow,
)

PROJECT_ROOT = Path(__file__).parent.parent
EXAMPLE_YAML = PROJECT_ROOT / "workflows" / "workflow.example.yml"


def test_score_workflow_example() -> None:
    config = parse_workflow(EXAMPLE_YAML)
    graph = build_step_graph(config)
    scores = score_workflow(config, graph)

    score_map = {s.step_id: s for s in scores}
    assert "resolve" in score_map

    resolve = score_map["resolve"]
    # resolve: ai_action, reversible=False, data_sensitivity=high, error_consequence set
    # blast_radius: 1 + 0 (not customer_facing) + 1 (high sensitivity) + 1 (error_consequence) + 0 (standard) = 3.0
    assert resolve.blast_radius >= 3.0, f"Expected blast_radius >= 3, got {resolve.blast_radius}"
    # reversibility: reversible=False, type=ai_action -> 5.0
    assert resolve.reversibility >= 4.0, f"Expected reversibility >= 4, got {resolve.reversibility}"


def test_composite_formula() -> None:
    # blast=4, rev=5, freq=3, ver=3, casc=2 -> (8+10+3+3+2)/8 = 26/8 = 3.25
    result = compute_composite(blast=4.0, reversibility=5.0, frequency=3.0, verifiability=3.0, cascading=2.0)
    assert result == pytest.approx(3.25, abs=1e-9)


def test_checkpoint_classification() -> None:
    assert classify_checkpoint_level(3.4) == "none"
    assert classify_checkpoint_level(3.5) == "none"  # boundary: > 3.5 required, not >=
    assert classify_checkpoint_level(3.6) == "recommended"
    assert classify_checkpoint_level(4.0) == "recommended"  # boundary: > 4.0 required, not >=
    assert classify_checkpoint_level(4.1) == "required"


def test_frequency_bucketing() -> None:
    # Build a trivial graph with a single root node
    graph = nx.DiGraph()
    graph.add_node("root")

    def make_volume(rpd: int) -> VolumeProfile:
        return VolumeProfile(requests_per_day=rpd)

    # Root node (no predecessors) uses base volume directly
    assert score_frequency(make_volume(9), graph, "root") == 1.0
    assert score_frequency(make_volume(10), graph, "root") == 2.0
    assert score_frequency(make_volume(99), graph, "root") == 2.0
    assert score_frequency(make_volume(100), graph, "root") == 3.0
    assert score_frequency(make_volume(999), graph, "root") == 3.0
    assert score_frequency(make_volume(1000), graph, "root") == 4.0
    assert score_frequency(make_volume(9999), graph, "root") == 4.0
    assert score_frequency(make_volume(10000), graph, "root") == 5.0


def test_cascading_risk_counts() -> None:
    # Linear chain: a -> b -> c -> d -> e -> f -> g
    graph = nx.DiGraph()
    graph.add_edges_from([("a", "b"), ("b", "c"), ("c", "d"), ("d", "e"), ("e", "f"), ("f", "g")])

    # a has 6 descendants (b,c,d,e,f,g) -> 5.0
    assert score_cascading_risk(graph, "a") == 5.0
    # d has 3 descendants (e,f,g) -> 3.0
    assert score_cascading_risk(graph, "d") == 3.0
    # f has 1 descendant (g) -> 2.0
    assert score_cascading_risk(graph, "f") == 2.0
    # g has 0 descendants -> 1.0
    assert score_cascading_risk(graph, "g") == 1.0

    # Node with exactly 4 descendants -> 4.0
    small_graph = nx.DiGraph()
    small_graph.add_edges_from([("x", "a1"), ("x", "a2"), ("x", "a3"), ("x", "a4")])
    assert score_cascading_risk(small_graph, "x") == 4.0

    # Node with exactly 2 descendants -> 3.0
    graph2 = nx.DiGraph()
    graph2.add_edges_from([("root", "child1"), ("root", "child2")])
    assert score_cascading_risk(graph2, "root") == 3.0
