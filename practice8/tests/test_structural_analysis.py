import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

import networkx as nx
import pytest

from structural_analysis import (
    AnalysisConfig,
    community_analysis,
    degree_distribution,
    deletion_trace,
    link_prediction_analysis,
    load_graph,
    normalized_mutual_information,
    resilience_analysis,
    semantic_analysis,
    semantic_steps,
    specific_path_evidence,
    undirected_projection,
)


@pytest.fixture
def graph() -> nx.MultiDiGraph:
    graph = nx.MultiDiGraph()
    for qid, kind, label in (
        ("Q183", "Country", "Germany"),
        ("Q101", "City", "City A"),
        ("Q102", "City", "City B"),
        ("Q103", "City", "City C"),
        ("Q201", "AdministrativeTerritory", "Admin X"),
        ("Q202", "AdministrativeTerritory", "Admin Y"),
    ):
        graph.add_node(qid, type=kind, label=label)
    for city, admin in (
        ("Q101", "Q201"),
        ("Q102", "Q201"),
        ("Q102", "Q202"),
        ("Q103", "Q202"),
    ):
        graph.add_edge(city, admin, key="P131", property="P131", relation="CityAdmin")
    for node in sorted(set(graph) - {"Q183"}):
        relation = (
            "CityCountry" if graph.nodes[node]["type"] == "City" else "AdminCountry"
        )
        graph.add_edge(node, "Q183", key="P17", property="P17", relation=relation)
    return graph


def test_projection_deduplicates_without_mutating_source(
    graph: nx.MultiDiGraph,
) -> None:
    graph.add_edge("Q101", "Q201", key="extra", property="P131", relation="CityAdmin")
    before = graph.copy()
    projected = undirected_projection(graph)
    assert len(projected) == 6
    assert projected.number_of_edges() == 9
    assert nx.utils.graphs_equal(graph, before)


def test_literal_nodes_are_rejected(graph: nx.MultiDiGraph) -> None:
    graph = nx.relabel_nodes(graph, {"Q101": "a literal label"})
    payload = json.dumps(nx.node_link_data(graph, edges="edges")).encode()
    with pytest.raises(ValueError, match="Literal nodes"):
        load_graph(payload, minimum_nodes=6)


def test_small_sources_are_rejected(graph: nx.MultiDiGraph) -> None:
    payload = json.dumps(nx.node_link_data(graph, edges="edges")).encode()
    with pytest.raises(ValueError, match="too small"):
        load_graph(payload)


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        ([0, 0, 1, 1], [4, 4, 8, 8], 1),
        ([0, 0, 1, 1], [0, 1, 0, 1], 0),
        ([0, 0], [1, 1], 1),
    ],
)
def test_nmi_invariant_to_label_names(
    first: list, second: list, expected: float
) -> None:
    assert normalized_mutual_information(first, second) == pytest.approx(expected)


def test_communities_use_the_same_resolution_for_modularity(
    graph: nx.MultiDiGraph,
) -> None:
    undirected = undirected_projection(graph)
    config = AnalysisConfig(resolution=0.7)
    communities, scores, tables, metrics = community_analysis(graph, undirected, config)
    assert set().union(*communities) == set(graph)
    assert sum(map(len, communities)) == len(graph)
    assert metrics["modularity"] == pytest.approx(
        nx.community.modularity(undirected, communities, weight=None, resolution=0.7)
    )
    assert scores.pagerank.sum() == pytest.approx(1)
    assert tables["community_composition"].nodes.sum() == len(graph)
    assert len(tables["graph_bridges"]) == 0


def test_semantic_steps_preserve_original_reverse_direction(
    graph: nx.MultiDiGraph,
) -> None:
    steps = semantic_steps(graph, ["Q101", "Q183", "Q103"])
    assert steps.property.tolist() == ["P17", "P17"]
    assert steps.traversal_direction.tolist() == ["along", "against"]
    assert steps.rdf_source.tolist() == ["Q101", "Q103"]
    assert steps.rdf_target.tolist() == ["Q183", "Q183"]


def test_semantic_steps_preserve_parallel_edges(graph: nx.MultiDiGraph) -> None:
    graph.add_edge("Q101", "Q201", key="extra", property="P17", relation="test")
    steps = semantic_steps(graph, ["Q101", "Q201"])
    assert Counter(steps.property) == {"P131": 1, "P17": 1}


def test_deletion_trace_includes_initial_state_and_isolates(
    graph: nx.MultiDiGraph,
) -> None:
    undirected = undirected_projection(graph)
    before = undirected.copy()
    trace = deletion_trace(undirected, ["Q183", "Q201"])
    assert trace.step.tolist() == [0, 1, 2]
    assert trace.remaining_nodes.tolist() == [6, 5, 4]
    assert trace.iloc[-1].isolates == 1
    assert trace.iloc[-1].components == 2
    assert nx.utils.graphs_equal(undirected, before)
    with pytest.raises(ValueError, match="distinct"):
        deletion_trace(undirected, ["Q183", "Q183"])


def test_random_baseline_is_reproducible_and_ranking_is_fixed(
    graph: nx.MultiDiGraph,
) -> None:
    undirected = undirected_projection(graph)
    config = AnalysisConfig(attack_steps=2, random_trials=20)
    _, scores, _, _ = community_analysis(graph, undirected, config)
    first, metrics = resilience_analysis(undirected, scores, config)
    second, _ = resilience_analysis(undirected, scores, config)
    assert first["random_attack_trials"].equals(second["random_attack_trials"])
    expected = sorted(
        scores.index, key=lambda node: (-scores.at[node, "pagerank"], node)
    )[:2]
    assert metrics["targeted_order"] == expected
    assert len(first["random_attack_trials"]) == 20 * 3
    assert metrics["random_main_hub_hit_probability"] == pytest.approx(2 / 6)


def test_specific_paths_match_exact_enumeration(graph: nx.MultiDiGraph) -> None:
    evidence = specific_path_evidence(graph)
    assert evidence[("Q101", "Q202")]["paths"] == 1
    tables, _, _ = link_prediction_analysis(graph, undirected_projection(graph))
    selected = (
        tables["link_candidates"]
        .query("city == 'Q101' and candidate_admin == 'Q202'")
        .iloc[0]
    )
    assert not selected.direct_edge_present
    assert selected.paths_length2 == 1
    assert selected.paths_length3 == 4
    assert selected.specific_p131_paths == 1
    assert selected.all_paths_up_to3 == 5


def test_main_ego_can_equal_the_entire_network(graph: nx.MultiDiGraph) -> None:
    undirected = undirected_projection(graph)
    _, scores, _, _ = community_analysis(graph, undirected)
    _, metrics, details, main_ego, _ = semantic_analysis(graph, undirected, scores)
    assert set(main_ego) == set(graph)
    assert metrics["main_ego_fraction"] == 1
    assert metrics["undirected_diameter"] == metrics["shortest_path_length"] == 2
    assert not metrics["directed_reachable"]
    assert details["shortest_path"][1] == "Q183"


def test_degree_distribution_counts_every_node(graph: nx.MultiDiGraph) -> None:
    result = degree_distribution(undirected_projection(graph))
    assert result["count"].sum() == len(graph)
    assert result.fraction.sum() == pytest.approx(1)
    assert result.ccdf.is_monotonic_decreasing


def test_community_tables_are_reproducible_across_hash_seeds() -> None:
    program = """
import json
import networkx as nx
from structural_analysis import community_analysis, semantic_analysis
from structural_analysis import undirected_projection
g = nx.MultiDiGraph()
g.add_node("Q183", type="Country", label="Country")
for i in range(8):
    city, admin = f"Q{1000+i}", f"Q{2000+i}"
    g.add_node(city, type="City", label=city)
    g.add_node(admin, type="AdministrativeTerritory", label=admin)
    g.add_edge(city, admin, property="P131")
    g.add_edge(city, "Q183", property="P17")
    g.add_edge(admin, "Q183", property="P17")
projected = undirected_projection(g)
_, scores, tables, _ = community_analysis(g, projected)
_, _, _, _, local_ego = semantic_analysis(g, projected, scores)
payload = {name: table.to_dict(orient="records") for name, table in tables.items()}
payload["local_ego_order"] = list(local_ego)
print(json.dumps(payload, sort_keys=True))
"""
    outputs = [
        subprocess.check_output(
            [sys.executable, "-c", program],
            cwd=Path(__file__).resolve().parents[1],
            env={**os.environ, "PYTHONHASHSEED": str(seed)},
            text=True,
            encoding="utf-8",
        )
        for seed in (11, 29)
    ]
    assert outputs[0] == outputs[1]
