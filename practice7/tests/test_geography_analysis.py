import json
from collections import Counter
from copy import deepcopy
from pathlib import Path

import networkx as nx
import pytest

from geography_analysis import (
    GraphConfig,
    analyze_snapshot,
    build_graph,
    diversity,
    export_results,
    path_statistics,
)


@pytest.fixture
def snapshot() -> dict:
    return {
        "results": {
            "results": {
                "bindings": [
                    {
                        "city": {"value": f"http://www.wikidata.org/entity/{city}"},
                        "admin": {"value": "http://www.wikidata.org/entity/Q201"},
                        "population": {"value": "2000"},
                    }
                    for city in ("Q101", "Q102")
                ]
            }
        },
        "labels": {
            "Q101": "City A",
            "Q102": "City B",
            "Q201": "District",
            "Q183": "Germany",
        },
        "provenance": {
            "endpoint": "fixture",
            "retrieved_at_utc": "2026-10-26T00:00:00Z",
        },
    }


def test_triangle_schema_and_exact_metrics(snapshot: dict) -> None:
    result = analyze_snapshot(snapshot, GraphConfig(min_nodes=4))
    assert result.graph.number_of_nodes() == 4
    assert result.graph.number_of_edges() == 5
    assert result.paths_undirected["mean"] == pytest.approx(7 / 6)
    assert result.paths_undirected["max"] == 2
    assert result.paths_directed["reachable_ordered_pairs"] == 5
    assert result.paths_directed["mean"] == 1
    assert (result.centrality.betweenness_directed == 0).all()
    assert result.centrality.pagerank.sum() == pytest.approx(1)
    assert result.centrality.degree_centrality.loc["Q183"] == 1


@pytest.mark.parametrize("population", ["1000", "0", "nan", "inf"])
def test_population_filter_cannot_be_bypassed(snapshot: dict, population: str) -> None:
    snapshot["results"]["results"]["bindings"][0]["population"]["value"] = population
    with pytest.raises(ValueError, match="Population filter"):
        build_graph(snapshot, GraphConfig(min_nodes=3))


def test_duplicate_rows_do_not_inflate_edges(snapshot: dict) -> None:
    rows = snapshot["results"]["results"]["bindings"]
    rows.extend(deepcopy(rows))
    graph, _ = build_graph(snapshot, GraphConfig(min_nodes=4))
    assert graph.number_of_edges() == 5


def test_small_graph_is_rejected(snapshot: dict) -> None:
    with pytest.raises(ValueError, match="required at least 1500"):
        build_graph(snapshot)


def test_unreachable_pairs_are_reported_separately() -> None:
    graph = nx.DiGraph([(0, 1), (1, 2)])
    statistics = path_statistics(graph)
    assert statistics["mean"] == pytest.approx(4 / 3)
    assert statistics["reachable_ordered_pairs"] == 3
    assert statistics["possible_ordered_pairs"] == 6
    assert statistics["reachable_fraction"] == 0.5


def test_entropy_bounds() -> None:
    assert diversity(Counter({"a": 10}))["normalized_entropy"] == 0
    assert diversity(Counter({"a": 2, "b": 2, "c": 2}))[
        "normalized_entropy"
    ] == pytest.approx(1)
    with pytest.raises(ValueError):
        diversity(Counter())


def test_graphml_and_json_round_trip(snapshot: dict, tmp_path: Path) -> None:
    result = analyze_snapshot(snapshot, GraphConfig(min_nodes=4))
    export_results(result, snapshot, tmp_path, plots=False)
    restored = nx.read_graphml(
        tmp_path / "variant12_geography.graphml", force_multigraph=True
    )
    assert restored.is_directed() and restored.is_multigraph()
    assert set(restored.edges(keys=True)) == set(result.graph.edges(keys=True))
    assert dict(restored.nodes(data=True)) == dict(result.graph.nodes(data=True))
    serialized = json.loads(
        (tmp_path / "variant12_geography.json").read_text(encoding="utf-8")
    )
    restored_json = nx.node_link_graph(serialized, edges="edges")
    assert nx.utils.graphs_equal(restored_json, result.graph)
