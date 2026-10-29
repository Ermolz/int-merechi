"""Community, resilience and semantic analysis of the variant 12 Wikidata graph."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import textwrap
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import matplotlib
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
import scipy
from matplotlib.figure import Figure

INPUT_SHA256 = "5ec861b5967eb325c6dfae0ce7a36993b95d44e8da5a34e86f539d990616561e"
COUNTRY = "Q183"


@dataclass(frozen=True)
class AnalysisConfig:
    seed: int = 12
    resolution: float = 1.0
    attack_steps: int = 5
    random_trials: int = 500
    path_cutoff: int = 3


DEFAULT_CONFIG = AnalysisConfig()


@dataclass
class AnalysisResult:
    graph: nx.MultiDiGraph
    undirected: nx.Graph
    communities: list[set[str]]
    scores: pd.DataFrame
    tables: dict[str, pd.DataFrame]
    metrics: dict[str, Any]
    details: dict[str, Any]
    main_ego: nx.Graph
    local_ego: nx.Graph


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def library_versions() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "networkx": nx.__version__,
        "matplotlib": matplotlib.__version__,
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scipy": scipy.__version__,
    }


def load_graph(payload: bytes, *, minimum_nodes: int = 1500) -> nx.MultiDiGraph:
    graph = nx.node_link_graph(json.loads(payload), edges="edges")
    if not graph.is_directed() or not graph.is_multigraph():
        raise ValueError("The source must be a directed multigraph")
    if len(graph) < minimum_nodes or not nx.is_weakly_connected(graph):
        raise ValueError("The source is too small or weakly disconnected")
    if nx.number_of_selfloops(graph) or list(nx.isolates(graph)):
        raise ValueError("The source contains self-loops or isolated nodes")
    for node, data in graph.nodes(data=True):
        if (
            not isinstance(node, str)
            or not node.startswith("Q")
            or not node[1:].isdigit()
        ):
            raise ValueError("Literal nodes are not allowed")
        if data.get("type") not in {"City", "Country", "AdministrativeTerritory"}:
            raise ValueError(f"Missing or unsupported entity type: {node}")
        if not data.get("label"):
            raise ValueError(f"Missing label: {node}")
    for _, _, data in graph.edges(data=True):
        if data.get("property") not in {"P17", "P131"}:
            raise ValueError("Unexpected geographic predicate")
    return graph


def undirected_projection(graph: nx.Graph) -> nx.Graph:
    projected = nx.Graph()
    projected.add_nodes_from((node, dict(graph.nodes[node])) for node in sorted(graph))
    projected.add_edges_from(sorted({tuple(sorted((u, v))) for u, v in graph.edges()}))
    return projected


def normalized_mutual_information(first: list[Any], second: list[Any]) -> float:
    if len(first) != len(second) or not first:
        raise ValueError("Partitions must have equal nonzero lengths")
    total = len(first)
    left, right = Counter(first), Counter(second)
    information = sum(
        count / total * math.log(count * total / (left[a] * right[b]))
        for (a, b), count in Counter(zip(first, second, strict=True)).items()
    )

    def entropy(counts: Counter[Any]) -> float:
        return -sum(c / total * math.log(c / total) for c in counts.values())

    denominator = entropy(left) + entropy(right)
    return (
        1.0 if denominator == 0 else min(1.0, max(0.0, 2 * information / denominator))
    )


def administrative_index(
    graph: nx.MultiDiGraph,
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    parents: dict[str, set[str]] = defaultdict(set)
    members: dict[str, set[str]] = defaultdict(set)
    for source, target, data in graph.edges(data=True):
        if data["property"] == "P131":
            parents[source].add(target)
            members[target].add(source)
    return dict(parents), dict(members)


def community_analysis(
    graph: nx.MultiDiGraph,
    undirected: nx.Graph,
    config: AnalysisConfig = DEFAULT_CONFIG,
) -> tuple[list[set[str]], pd.DataFrame, dict[str, pd.DataFrame], dict[str, Any]]:
    communities = nx.community.louvain_communities(
        undirected,
        weight=None,
        resolution=config.resolution,
        seed=config.seed,
    )
    communities.sort(key=lambda nodes: (-len(nodes), min(nodes)))
    community_of = {
        node: index for index, nodes in enumerate(communities) for node in nodes
    }
    pagerank = nx.pagerank(
        undirected, alpha=0.85, weight=None, tol=1e-12, max_iter=1000
    )
    degree = nx.degree_centrality(undirected)
    scores = pd.DataFrame(
        [
            {
                "qid": node,
                "label": graph.nodes[node]["label"],
                "type": graph.nodes[node]["type"],
                "degree": undirected.degree(node),
                "degree_centrality": degree[node],
                "pagerank": pagerank[node],
                "community": community_of[node],
            }
            for node in sorted(undirected)
        ]
    ).set_index("qid")
    bridges = {frozenset(edge) for edge in nx.bridges(undirected)}
    parents, _ = administrative_index(graph)
    primary_admin = {city: min(admins) for city, admins in parents.items()}
    rows, centralities, compositions, admin_groups = [], [], [], []
    for index, nodes in enumerate(communities):
        subgraph = undirected_projection(undirected.subgraph(nodes))
        internal_degree = nx.degree_centrality(subgraph)
        internal_between = nx.betweenness_centrality(
            subgraph, weight=None, normalized=True
        )
        degree_order = sorted(nodes, key=lambda node: (-internal_degree[node], node))
        between_order = sorted(nodes, key=lambda node: (-internal_between[node], node))
        boundary = sum(1 for _ in nx.edge_boundary(undirected, nodes))
        counts = Counter(graph.nodes[node]["type"] for node in nodes)
        city_groups = Counter(
            primary_admin[node] for node in sorted(nodes) if node in primary_admin
        )
        dominant_admin, dominant_size = (
            min(city_groups.items(), key=lambda item: (-item[1], item[0]))
            if city_groups
            else ("", 0)
        )
        rows.append(
            {
                "community": index,
                "nodes": len(nodes),
                "edges": subgraph.number_of_edges(),
                "density": nx.density(subgraph),
                "components": nx.number_connected_components(subgraph),
                "boundary_edges": boundary,
                "boundary_fraction": boundary
                / (2 * subgraph.number_of_edges() + boundary),
                "degree_hub": degree_order[0],
                "degree_hub_label": graph.nodes[degree_order[0]]["label"],
                "betweenness_hub": between_order[0],
                "betweenness_hub_label": graph.nodes[between_order[0]]["label"],
                "dominant_primary_admin": dominant_admin,
                "dominant_primary_admin_label": graph.nodes[dominant_admin]["label"]
                if dominant_admin
                else "",
                "dominant_admin_city_count": dominant_size,
            }
        )
        for node_type, count in sorted(counts.items()):
            compositions.append(
                {
                    "community": index,
                    "type": node_type,
                    "nodes": count,
                    "fraction": count / len(nodes),
                }
            )
        for admin, count in sorted(city_groups.items()):
            admin_groups.append(
                {
                    "community": index,
                    "primary_admin": admin,
                    "admin_label": graph.nodes[admin]["label"],
                    "cities": count,
                }
            )
        selected = sorted(set(degree_order[:3]) | set(between_order[:3]))
        for node in selected:
            centralities.append(
                {
                    "community": index,
                    "qid": node,
                    "label": graph.nodes[node]["label"],
                    "type": graph.nodes[node]["type"],
                    "internal_degree": subgraph.degree(node),
                    "degree_centrality": internal_degree[node],
                    "betweenness": internal_between[node],
                }
            )
    cross_edges, pairs = [], Counter()
    for u, v in sorted(undirected.edges()):
        first, second = community_of[u], community_of[v]
        if first != second:
            pairs[tuple(sorted((first, second)))] += 1
            cross_edges.append(
                {
                    "source": u,
                    "source_label": graph.nodes[u]["label"],
                    "source_community": first,
                    "target": v,
                    "target_label": graph.nodes[v]["label"],
                    "target_community": second,
                    "is_graph_bridge": frozenset((u, v)) in bridges,
                }
            )
    anomalies = [
        {
            "city": city,
            "city_label": graph.nodes[city]["label"],
            "admin_count": len(admins),
            "admin_qids": "; ".join(sorted(admins)),
            "admin_labels": "; ".join(
                graph.nodes[admin]["label"] for admin in sorted(admins)
            ),
        }
        for city, admins in sorted(parents.items())
        if len(admins) > 1
    ]
    composition = pd.DataFrame(compositions)
    purity = composition.groupby("community").nodes.max().sum() / len(undirected)
    cities = sorted(primary_admin)
    types = [graph.nodes[node]["type"] for node in sorted(undirected)]
    tables = {
        "community_summary": pd.DataFrame(rows),
        "community_hubs": pd.DataFrame(centralities),
        "community_composition": composition,
        "community_admin_groups": pd.DataFrame(admin_groups),
        "intercommunity_edges": pd.DataFrame(cross_edges),
        "intercommunity_pairs": pd.DataFrame(
            [
                {
                    "first_community": pair[0],
                    "second_community": pair[1],
                    "edges": count,
                }
                for pair, count in pairs.most_common()
            ]
        ),
        "graph_bridges": pd.DataFrame(
            [
                {"source": u, "target": v}
                for u, v in sorted(tuple(sorted(edge)) for edge in bridges)
            ],
            columns=["source", "target"],
        ),
        "multiple_admin_cities": pd.DataFrame(anomalies).sort_values(
            ["admin_count", "city"],
            ascending=[False, True],
        )
        if anomalies
        else pd.DataFrame(
            columns=["city", "city_label", "admin_count", "admin_qids", "admin_labels"]
        ),
    }
    metrics = {
        "count": len(communities),
        "resolution": config.resolution,
        "modularity": nx.community.modularity(
            undirected, communities, weight=None, resolution=config.resolution
        ),
        "type_nmi": normalized_mutual_information(
            types, [community_of[n] for n in sorted(undirected)]
        ),
        "type_purity": float(purity),
        "majority_type_baseline": max(Counter(types).values()) / len(types),
        "city_primary_admin_nmi": normalized_mutual_information(
            [primary_admin[city] for city in cities],
            [community_of[city] for city in cities],
        ),
        "sampling_country_groups": 1,
        "intercommunity_edges": len(cross_edges),
        "intercommunity_predicates": dict(
            Counter(
                data["property"]
                for u, v, data in graph.edges(data=True)
                if community_of[u] != community_of[v]
            )
        ),
        "graph_bridges": len(bridges),
        "articulation_points": sorted(nx.articulation_points(undirected)),
        "multiple_admin_cities": len(anomalies),
    }
    return communities, scores, tables, metrics


def component_statistics(graph: nx.Graph, initial_size: int) -> dict[str, float | int]:
    sizes = [len(nodes) for nodes in nx.connected_components(graph)]
    largest = max(sizes, default=0)
    return {
        "remaining_nodes": len(graph),
        "components": len(sizes),
        "largest_component": largest,
        "largest_fraction_initial": largest / initial_size,
        "largest_fraction_remaining": largest / len(graph) if graph else 0.0,
        "isolates": len(list(nx.isolates(graph))),
    }


def deletion_trace(graph: nx.Graph, order: list[str]) -> pd.DataFrame:
    if len(set(order)) != len(order) or any(node not in graph for node in order):
        raise ValueError("Removal order must contain distinct existing nodes")
    working = graph.copy()
    rows = [
        {
            "step": 0,
            "removed_qid": "",
            "removed_label": "",
            "removed_type": "",
            **component_statistics(working, len(graph)),
        }
    ]
    for step, node in enumerate(order, start=1):
        data = graph.nodes[node]
        working.remove_node(node)
        rows.append(
            {
                "step": step,
                "removed_qid": node,
                "removed_label": data.get("label", node),
                "removed_type": data.get("type", ""),
                **component_statistics(working, len(graph)),
            }
        )
    return pd.DataFrame(rows)


def resilience_analysis(
    graph: nx.Graph,
    scores: pd.DataFrame,
    config: AnalysisConfig = DEFAULT_CONFIG,
) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    if config.attack_steps >= len(graph) or config.random_trials < 1:
        raise ValueError("Choose fewer removals than nodes and a positive trial count")
    ranking = sorted(
        scores.index, key=lambda node: (-scores.at[node, "pagerank"], node)
    )
    order = ranking[: config.attack_steps]
    targeted = deletion_trace(graph, order)
    targeted["initial_pagerank"] = [0.0] + [
        float(scores.at[node, "pagerank"]) for node in order
    ]
    rng = np.random.default_rng(config.seed)
    nodes = np.array(sorted(graph), dtype=object)
    trials = []
    for trial in range(config.random_trials):
        random_order = rng.choice(
            nodes, size=config.attack_steps, replace=False
        ).tolist()
        trace = deletion_trace(graph, random_order)
        trace.insert(0, "trial", trial)
        trials.append(trace)
    random_traces = pd.concat(trials, ignore_index=True)
    random_summary = (
        random_traces.groupby("step")
        .agg(
            components_mean=("components", "mean"),
            components_p025=("components", lambda values: values.quantile(0.025)),
            components_p975=("components", lambda values: values.quantile(0.975)),
            largest_mean=("largest_component", "mean"),
            largest_p025=("largest_component", lambda values: values.quantile(0.025)),
            largest_p975=("largest_component", lambda values: values.quantile(0.975)),
        )
        .reset_index()
    )
    final_random = random_traces[random_traces.step == config.attack_steps]
    final_target = targeted.iloc[-1]
    metrics = {
        "attack_ranking": "PageRank on the initial undirected graph; no recomputation",
        "targeted_order": order,
        "random_trials": config.random_trials,
        "targeted_final_components": int(final_target.components),
        "targeted_final_largest": int(final_target.largest_component),
        "random_final_components_mean": float(final_random.components.mean()),
        "random_final_largest_mean": float(final_random.largest_component.mean()),
        "random_largest_le_targeted_fraction": float(
            (final_random.largest_component <= final_target.largest_component).mean()
        ),
        "random_includes_main_hub_trials": int(
            random_traces.loc[random_traces.removed_qid == order[0], "trial"].nunique()
        ),
        "main_hub_is_universal": graph.degree(order[0]) == len(graph) - 1,
        "random_main_hub_hit_probability": config.attack_steps / len(graph),
        "expected_random_main_hub_hits": config.random_trials
        * config.attack_steps
        / len(graph),
        "probability_no_main_hub_hit_in_trials": (1 - config.attack_steps / len(graph))
        ** config.random_trials,
    }
    return {
        "targeted_attack": targeted,
        "random_attack_trials": random_traces,
        "random_attack_summary": random_summary,
        "initial_top5_pagerank": scores.loc[order].reset_index(),
    }, metrics


def semantic_steps(graph: nx.MultiDiGraph, path: list[str]) -> pd.DataFrame:
    rows = []
    for step, (u, v) in enumerate(zip(path, path[1:], strict=False), start=1):
        found = False
        for source, target, direction in ((u, v, "along"), (v, u, "against")):
            for key, data in sorted(
                graph.get_edge_data(source, target, default={}).items()
            ):
                rows.append(
                    {
                        "step": step,
                        "traversal_from": u,
                        "traversal_to": v,
                        "rdf_source": source,
                        "rdf_source_label": graph.nodes[source]["label"],
                        "rdf_target": target,
                        "rdf_target_label": graph.nodes[target]["label"],
                        "property": data["property"],
                        "relation": data.get("relation", ""),
                        "property_uri": data.get("property_uri", ""),
                        "edge_key": str(key),
                        "traversal_direction": direction,
                    }
                )
                found = True
        if not found:
            raise ValueError(f"Path step has no original RDF edge: {u}, {v}")
    return pd.DataFrame(rows)


def path_text(graph: nx.MultiDiGraph, path: list[str]) -> str:
    steps = semantic_steps(graph, path)
    text = f"{graph.nodes[path[0]]['label']} ({path[0]})"
    for index, node in enumerate(path[1:], start=1):
        links = steps[steps.step == index]
        predicates = ", ".join(sorted(set(links.property)))
        direction = set(links.traversal_direction)
        connector = (
            f" —{predicates}→ " if direction == {"along"} else f" ←{predicates}— "
        )
        if len(direction) > 1:
            connector = f" ←{predicates}→ "
        text += connector + f"{graph.nodes[node]['label']} ({node})"
    return text


def semantic_analysis(
    graph: nx.MultiDiGraph,
    undirected: nx.Graph,
    scores: pd.DataFrame,
) -> tuple[dict[str, pd.DataFrame], dict[str, Any], dict[str, Any], nx.Graph, nx.Graph]:
    parents, _ = administrative_index(graph)
    cities = sorted(parents, key=lambda node: (graph.nodes[node]["label"], node))
    source = cities[0]
    distances = nx.single_source_shortest_path_length(undirected, source)
    candidates = [
        node
        for node in cities
        if node != source and parents[node].isdisjoint(parents[source])
    ]
    if not candidates:
        candidates = [node for node in cities if node != source]
    target = min(
        candidates,
        key=lambda node: (-distances[node], graph.nodes[node]["label"], node),
    )
    path = nx.shortest_path(undirected, source, target)
    hub = min(scores.index, key=lambda node: (-scores.at[node, "pagerank"], node))
    admins = scores[scores.type == "AdministrativeTerritory"]
    local_hub = min(admins.index, key=lambda node: (-admins.at[node, "pagerank"], node))
    main_ego = undirected_projection(nx.ego_graph(undirected, hub, radius=2))
    local_ego = undirected_projection(nx.ego_graph(undirected, local_hub, radius=1))
    ego_table = pd.DataFrame(
        [
            {
                "role": role,
                "center": center,
                "label": graph.nodes[center]["label"],
                "radius": radius,
                "nodes": len(ego),
                "edges": ego.number_of_edges(),
                "node_fraction": len(ego) / len(undirected),
            }
            for role, center, radius, ego in (
                ("main_hub", hub, 2, main_ego),
                ("additional_local_admin", local_hub, 1, local_ego),
            )
        ]
    )
    universal_core = undirected.degree(hub) == len(undirected) - 1
    complete = (
        undirected.number_of_edges() == len(undirected) * (len(undirected) - 1) // 2
    )
    diameter = 2 if universal_core and not complete else nx.diameter(undirected)
    metrics = {
        "source": source,
        "target": target,
        "shortest_path_length": len(path) - 1,
        "undirected_diameter": diameter,
        "directed_reachable": nx.has_path(graph, source, target),
        "main_hub": hub,
        "main_ego_nodes": len(main_ego),
        "main_ego_fraction": len(main_ego) / len(graph),
        "local_hub": local_hub,
        "local_ego_nodes": len(local_ego),
    }
    details = {"shortest_path": path, "shortest_path_text": path_text(graph, path)}
    return (
        {"semantic_path_steps": semantic_steps(graph, path), "ego_graphs": ego_table},
        metrics,
        details,
        main_ego,
        local_ego,
    )


def specific_path_evidence(
    graph: nx.MultiDiGraph,
) -> dict[tuple[str, str], dict[str, Any]]:
    parents, members = administrative_index(graph)
    evidence: dict[tuple[str, str], dict[str, Any]] = {}
    for city, own_admins in sorted(parents.items()):
        peers = set().union(*(members[admin] for admin in own_admins)) - {city}
        local: dict[str, dict[str, Any]] = {}
        for own_admin in sorted(own_admins):
            for peer in sorted(members[own_admin] - {city}):
                for candidate in sorted(parents[peer] - own_admins):
                    record = local.setdefault(
                        candidate,
                        {"paths": 0, "peer_cities": set(), "via_admins": set()},
                    )
                    record["paths"] += 1
                    record["peer_cities"].add(peer)
                    record["via_admins"].add(own_admin)
        for candidate, record in local.items():
            record["jaccard"] = len(peers & members[candidate]) / len(
                peers | members[candidate]
            )
            evidence[(city, candidate)] = record
    return evidence


def path_signature(graph: nx.MultiDiGraph, path: list[str]) -> str:
    steps = semantic_steps(graph, path)
    text = graph.nodes[path[0]]["type"]
    for index, node in enumerate(path[1:], start=1):
        links = steps[steps.step == index]
        predicates = "/".join(sorted(set(links.property)))
        direction = set(links.traversal_direction)
        connector = (
            f" -{predicates}-> " if direction == {"along"} else f" <-{predicates}- "
        )
        text += connector + graph.nodes[node]["type"]
    return text


def link_prediction_analysis(
    graph: nx.MultiDiGraph,
    undirected: nx.Graph,
    config: AnalysisConfig = DEFAULT_CONFIG,
) -> tuple[dict[str, pd.DataFrame], dict[str, Any], dict[str, Any]]:
    if config.path_cutoff != 3:
        raise ValueError(
            "The structural evidence comparison uses paths of length at most 3"
        )
    parents, members = administrative_index(graph)
    evidence = specific_path_evidence(graph)
    ranked = sorted(
        evidence,
        key=lambda pair: (-evidence[pair]["paths"], -evidence[pair]["jaccard"], pair),
    )
    selected = [(pair, "candidate") for pair in ranked[:8]]
    if not selected:
        city = min(parents)
        target = next(
            (admin for admin in sorted(members) if admin not in parents[city]), None
        )
        if target is None:
            raise ValueError(
                "This graph has no missing City–AdministrativeTerritory pair"
            )
        selected = [((city, target), "candidate")]
    first_city = selected[0][0][0]
    control = next(
        (
            admin
            for admin in sorted(members)
            if admin not in parents[first_city] and (first_city, admin) not in evidence
        ),
        None,
    )
    if control is not None:
        selected.append(((first_city, control), "comparison_without_specific_paths"))
    rows, pattern_rows, example_rows = [], [], []
    for (city, admin), role in selected:
        if graph.has_edge(city, admin) or graph.has_edge(admin, city):
            raise ValueError("A candidate already has a direct edge")
        paths = list(
            nx.all_simple_paths(undirected, city, admin, cutoff=config.path_cutoff)
        )
        patterns = Counter()
        specific_paths = 0
        for path in paths:
            kinds = [graph.nodes[node]["type"] for node in path]
            specific = kinds == [
                "City",
                "AdministrativeTerritory",
                "City",
                "AdministrativeTerritory",
            ]
            specific_paths += int(specific)
            patterns[(len(path) - 1, path_signature(graph, path), specific)] += 1
        expected = evidence.get((city, admin), {}).get("paths", 0)
        if specific_paths != expected:
            raise ValueError("Indexed path evidence differs from exact enumeration")
        rows.append(
            {
                "city": city,
                "city_label": graph.nodes[city]["label"],
                "candidate_admin": admin,
                "admin_label": graph.nodes[admin]["label"],
                "role": role,
                "direct_edge_present": False,
                "shortest_length": nx.shortest_path_length(undirected, city, admin),
                "paths_length2": sum(len(path) == 3 for path in paths),
                "paths_length3": sum(len(path) == 4 for path in paths),
                "all_paths_up_to3": len(paths),
                "specific_p131_paths": specific_paths,
                "supporting_cities": len(
                    evidence.get((city, admin), {}).get("peer_cities", set())
                ),
                "jaccard_peer_cities": evidence.get((city, admin), {}).get(
                    "jaccard", 0.0
                ),
            }
        )
        for (length, signature, specific), count in sorted(patterns.items()):
            pattern_rows.append(
                {
                    "city": city,
                    "candidate_admin": admin,
                    "length": length,
                    "typed_path": signature,
                    "count": count,
                    "specific_p131_evidence": specific,
                }
            )
        paths.sort(key=lambda path: (COUNTRY in path, len(path), path))
        for path in paths[:5]:
            example_rows.append(
                {
                    "city": city,
                    "candidate_admin": admin,
                    "length": len(path) - 1,
                    "qids": " > ".join(path),
                    "semantic_path": path_text(graph, path),
                }
            )
    candidates = pd.DataFrame(rows)
    best = candidates.iloc[0]
    metrics = {
        "missing_pairs_with_specific_paths": len(evidence),
        "cutoff_edges": config.path_cutoff,
        "selected_city": str(best.city),
        "selected_admin": str(best.candidate_admin),
        "selected_specific_paths": int(best.specific_p131_paths),
        "selected_all_paths_up_to3": int(best.all_paths_up_to3),
        "positive_prediction_is_verified": False,
    }
    details = {
        "hypothesis": (
            f"{graph.nodes[best.city]['label']} ({best.city}) may have P131 to "
            f"{graph.nodes[best.candidate_admin]['label']} ({best.candidate_admin})."
        ),
        "scope": (
            "Exact enumeration of simple paths with 2 or 3 edges; "
            "longer paths are excluded."
        ),
        "interpretation": (
            "Common country and co-membership paths support structural proximity, "
            "not verified administrative inclusion."
        ),
    }
    return (
        {
            "link_candidates": candidates,
            "link_path_patterns": pd.DataFrame(pattern_rows),
            "link_path_examples": pd.DataFrame(example_rows),
        },
        metrics,
        details,
    )


def degree_distribution(graph: nx.Graph) -> pd.DataFrame:
    degrees = np.array([degree for _, degree in graph.degree()])
    counts = Counter(degrees.tolist())
    return pd.DataFrame(
        [
            {
                "degree": degree,
                "count": counts[degree],
                "fraction": counts[degree] / len(graph),
                "ccdf": float(np.mean(degrees >= degree)),
            }
            for degree in sorted(counts)
        ]
    )


def analyze_graph(
    graph: nx.MultiDiGraph, config: AnalysisConfig = DEFAULT_CONFIG
) -> AnalysisResult:
    undirected = undirected_projection(graph)
    communities, scores, tables, community_metrics = community_analysis(
        graph, undirected, config
    )
    attack_tables, attack_metrics = resilience_analysis(undirected, scores, config)
    semantic_tables, semantic_metrics, semantic_details, main_ego, local_ego = (
        semantic_analysis(graph, undirected, scores)
    )
    link_tables, link_metrics, link_details = link_prediction_analysis(
        graph, undirected, config
    )
    tables.update(attack_tables)
    tables.update(semantic_tables)
    tables.update(link_tables)
    tables["degree_distribution"] = degree_distribution(undirected)
    metrics = {
        "variant": 12,
        "nodes": len(graph),
        "directed_edges": graph.number_of_edges(),
        "undirected_edges": undirected.number_of_edges(),
        "communities": community_metrics,
        "resilience": attack_metrics,
        "semantic": semantic_metrics,
        "link_prediction": link_metrics,
    }
    return AnalysisResult(
        graph,
        undirected,
        communities,
        scores,
        tables,
        metrics,
        {"semantic": semantic_details, "link_prediction": link_details},
        main_ego,
        local_ego,
    )


def plot_communities(
    result: AnalysisResult, config: AnalysisConfig = DEFAULT_CONFIG
) -> Figure:
    graph = result.undirected
    nodes = sorted(graph)
    positions = nx.spring_layout(
        graph, seed=config.seed, weight=None, iterations=90, method="energy"
    )
    ranks = result.scores.pagerank
    colors = [int(result.scores.at[node, "community"]) for node in nodes]
    sizes = [2500 * float(ranks[node]) / float(ranks.max()) for node in nodes]
    figure, axes = plt.subplots(figsize=(14, 11))
    community_of = result.scores.community.to_dict()
    inside = [(u, v) for u, v in graph.edges() if community_of[u] == community_of[v]]
    outside = [(u, v) for u, v in graph.edges() if community_of[u] != community_of[v]]
    nx.draw_networkx_edges(
        graph,
        positions,
        edgelist=outside,
        ax=axes,
        alpha=0.06,
        width=0.45,
        edge_color="#6B7280",
    )
    nx.draw_networkx_edges(
        graph,
        positions,
        edgelist=inside,
        ax=axes,
        alpha=0.25,
        width=0.6,
        edge_color=[
            matplotlib.colormaps["turbo"](
                community_of[u] / max(1, len(result.communities) - 1)
            )
            for u, _ in inside
        ],
    )
    artists = nx.draw_networkx_nodes(
        graph,
        positions,
        ax=axes,
        nodelist=nodes,
        node_size=sizes,
        node_color=colors,
        cmap=matplotlib.colormaps["turbo"],
        vmin=0,
        vmax=max(1, len(result.communities) - 1),
        linewidths=0,
        alpha=0.9,
    )
    leaders = sorted(nodes, key=lambda node: (-ranks[node], node))[:8]
    for index, node in enumerate(leaders):
        x, y = positions[node]
        label = textwrap.fill(graph.nodes[node]["label"], 24)
        axes.annotate(
            label,
            (x, y),
            xytext=(12 if x >= 0 else -12, 14 + 11 * (index % 2)),
            textcoords="offset points",
            ha="left" if x >= 0 else "right",
            fontsize=8,
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.82},
            arrowprops={"arrowstyle": "-", "color": "#6B7280", "lw": 0.5},
        )
    colorbar = figure.colorbar(artists, ax=axes, shrink=0.65, pad=0.02)
    colorbar.set_label("Номер спільноти Louvain")
    colorbar.set_ticks(
        np.unique(
            np.linspace(
                0,
                len(result.communities) - 1,
                min(10, len(result.communities)),
                dtype=int,
            )
        )
    )
    axes.set_title(
        f"Спільноти географічного графа Wikidata · варіант 12\n"
        f"Вузлів: {len(graph)} · спільнот: {len(result.communities)} · "
        f"Q = {result.metrics['communities']['modularity']:.4f}",
        fontsize=15,
        pad=18,
    )
    axes.text(
        0.01,
        0.01,
        "Площа вузла пропорційна PageRank початкового неорієнтованого графа.\n"
        "Розташування: spring_layout, method=energy. Показано всі вузли й ребра.",
        transform=axes.transAxes,
        fontsize=9,
        color="#4B5563",
    )
    axes.axis("off")
    figure.tight_layout()
    return figure


def plot_composition(result: AnalysisResult) -> Figure:
    composition = result.tables["community_composition"]
    wide = (
        composition.pivot(index="community", columns="type", values="nodes")
        .fillna(0)
        .head(15)
    )
    wide = wide.reindex(
        columns=["City", "AdministrativeTerritory", "Country"], fill_value=0
    )
    proportions = wide.div(wide.sum(axis=1), axis=0) * 100
    figure, axes = plt.subplots(1, 2, figsize=(15, 5.2))
    for axis, data, title, ylabel in (
        (axes[0], wide, "Кількість сутностей", "Вузлів"),
        (axes[1], proportions, "Частки типів усередині спільноти", "Частка, %"),
    ):
        data.plot.bar(
            stacked=True,
            ax=axis,
            color=["#2F80B7", "#E49A32", "#963C62"],
            width=0.8,
            legend=False,
        )
        axis.set(title=title, xlabel="Номер спільноти", ylabel=ylabel)
        axis.tick_params(axis="x", rotation=0)
    coverage = wide.to_numpy().sum() / len(result.graph)
    figure.suptitle(
        f"Склад найбільших {len(wide)} спільнот · {coverage:.1%} вузлів",
        fontsize=13,
    )
    handles, labels = axes[0].get_legend_handles_labels()
    figure.legend(handles, labels, ncol=3, loc="lower center", frameon=False)
    figure.tight_layout(rect=(0, 0.08, 1, 0.94))
    return figure


def plot_degree_distribution(result: AnalysisResult) -> Figure:
    data = result.tables["degree_distribution"]
    degrees = np.array([degree for _, degree in result.undirected.degree()])
    bins = np.geomspace(
        max(0.5, float(degrees.min()) - 0.5), float(degrees.max()) + 0.5, 24
    )
    counts, boundaries = np.histogram(degrees, bins=bins)
    widths = np.diff(boundaries)
    nonzero = counts > 0
    figure, axes = plt.subplots(1, 3, figsize=(15, 4.7))
    axes[0].bar(
        boundaries[:-1][nonzero],
        counts[nonzero] / (len(degrees) * widths[nonzero]),
        width=widths[nonzero],
        align="edge",
        color="#2F80B7",
        edgecolor="white",
    )
    axes[0].set(
        xscale="log",
        yscale="log",
        title="Логарифмічна гістограма",
        xlabel="Степінь k",
        ylabel="Щільність частоти",
    )
    axes[1].scatter(data.degree, data.fraction, color="#963C62", s=30)
    axes[1].set(
        xscale="log",
        yscale="log",
        title="Точний розподіл P(K = k)",
        xlabel="Степінь k",
        ylabel="Частка вузлів",
    )
    axes[2].step(data.degree, data.ccdf, where="post", color="#E49A32", linewidth=2)
    axes[2].scatter(data.degree, data.ccdf, color="#E49A32", s=15)
    axes[2].set(
        xscale="log",
        yscale="log",
        title="Емпірична CCDF",
        xlabel="Степінь k",
        ylabel="P(K ≥ k)",
    )
    for axis in axes:
        axis.grid(axis="y", color="#E5E7EB", alpha=0.7)
    figure.suptitle("Степені неорієнтованого графа · усі вузли", fontsize=14, y=1.03)
    figure.tight_layout()
    return figure


def plot_resilience(result: AnalysisResult) -> Figure:
    targeted = result.tables["targeted_attack"]
    random = result.tables["random_attack_summary"]
    figure, axes = plt.subplots(1, 2, figsize=(13, 4.8))
    for axis, column, prefix, ylabel in (
        (axes[0], "components", "components", "Кількість компонент"),
        (axes[1], "largest_component", "largest", "Вузлів у найбільшій компоненті"),
    ):
        axis.fill_between(
            random.step,
            random[f"{prefix}_p025"],
            random[f"{prefix}_p975"],
            color="#2F80B7",
            alpha=0.18,
            label="Випадкові: 2.5–97.5 перцентилі",
        )
        axis.plot(
            random.step,
            random[f"{prefix}_mean"],
            color="#2F80B7",
            marker="s",
            label="Випадкові: середнє",
        )
        axis.plot(
            targeted.step,
            targeted[column],
            color="#963C62",
            marker="o",
            linewidth=2,
            label="Атака за початковим PageRank",
        )
        axis.set(xlabel="Кількість видалених вузлів", ylabel=ylabel)
        axis.set_xticks(targeted.step)
        axis.grid(axis="y", color="#E5E7EB")
    axes[0].set_title("Фрагментація")
    axes[1].set_title("Розмір найбільшої компоненти")
    axes[1].legend(fontsize=8, frameon=False, loc="center right")
    figure.suptitle(
        "Цілеспрямоване видалення хабів та "
        f"{result.metrics['resilience']['random_trials']} випадкових випробувань",
        fontsize=13,
    )
    figure.tight_layout()
    return figure


def plot_local_ego(
    result: AnalysisResult, config: AnalysisConfig = DEFAULT_CONFIG
) -> Figure:
    graph = result.local_ego
    positions = nx.spring_layout(
        graph, seed=config.seed, weight=None, iterations=100, method="force"
    )
    colors = {
        "City": "#2F80B7",
        "AdministrativeTerritory": "#E49A32",
        "Country": "#963C62",
    }
    figure, axes = plt.subplots(figsize=(11, 8))
    nx.draw_networkx_edges(
        graph, positions, ax=axes, edge_color="#94A3B8", alpha=0.35, width=0.7
    )
    for kind, color in colors.items():
        nodes = sorted(node for node in graph if graph.nodes[node]["type"] == kind)
        nx.draw_networkx_nodes(
            graph,
            positions,
            ax=axes,
            nodelist=nodes,
            node_color=color,
            node_size=[80 + 15 * graph.degree(node) for node in nodes],
            label=kind,
            alpha=0.9,
            linewidths=0,
        )
    leaders = sorted(graph, key=lambda node: (-graph.degree(node), node))[:8]
    labels = {node: textwrap.fill(graph.nodes[node]["label"], 24) for node in leaders}
    nx.draw_networkx_labels(
        graph,
        positions,
        labels=labels,
        font_size=8,
        ax=axes,
        verticalalignment="bottom",
        bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.8},
    )
    center = result.metrics["semantic"]["local_hub"]
    axes.set_title(
        f"Додатковий локальний его-граф r = 1\n"
        f"{result.graph.nodes[center]['label']} ({center}) · {len(graph)} вузлів",
        fontsize=13,
    )
    axes.legend(frameon=False, loc="lower left")
    axes.axis("off")
    figure.tight_layout()
    return figure


def export_results(
    result: AnalysisResult,
    output: Path,
    config: AnalysisConfig = DEFAULT_CONFIG,
    *,
    plots: bool = True,
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    result.scores.to_csv(
        output / "node_scores.csv", encoding="utf-8-sig", lineterminator="\n"
    )
    for name, table in result.tables.items():
        table.to_csv(
            output / f"{name}.csv",
            index=False,
            encoding="utf-8-sig",
            lineterminator="\n",
        )
    write_json(
        output / "metrics.json",
        {
            **result.metrics,
            "config": asdict(config),
            "versions": library_versions(),
            "input_sha256": INPUT_SHA256,
        },
    )
    write_json(output / "semantic_details.json", result.details)
    nx.write_graphml(result.main_ego, output / "ego_main_radius2.graphml")
    nx.write_graphml(result.local_ego, output / "ego_local_admin_radius1.graphml")
    graph = result.graph.copy()
    for node in graph:
        graph.nodes[node]["community"] = int(result.scores.at[node, "community"])
        graph.nodes[node]["undirected_pagerank"] = float(
            result.scores.at[node, "pagerank"]
        )
    nx.write_graphml(graph, output / "variant12_community_graph.graphml")
    if plots:
        for filename, draw in (
            ("communities.png", plot_communities),
            ("community_composition.png", plot_composition),
            ("degree_distribution.png", plot_degree_distribution),
            ("resilience.png", plot_resilience),
            ("ego_local.png", plot_local_ego),
        ):
            figure = (
                draw(result, config)
                if draw in (plot_communities, plot_local_ego)
                else draw(result)
            )
            figure.savefig(output / filename, dpi=180, bbox_inches="tight")
            plt.close(figure)
    write_json(
        output / "sha256.json",
        {
            file.name: hashlib.sha256(file.read_bytes()).hexdigest()
            for file in sorted(output.iterdir())
            if file.is_file() and file.name != "sha256.json"
        },
    )


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path, default=root / "data/geography_graph.json"
    )
    parser.add_argument("--output", type=Path, default=root / "outputs")
    parser.add_argument("--no-plots", action="store_true")
    args = parser.parse_args(argv)
    payload = args.input.read_bytes()
    if hashlib.sha256(payload).hexdigest() != INPUT_SHA256:
        raise ValueError("The source graph differs from the saved practice 7 snapshot")
    result = analyze_graph(load_graph(payload))
    export_results(result, args.output, plots=not args.no_plots)
    print(json.dumps(result.metrics, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
