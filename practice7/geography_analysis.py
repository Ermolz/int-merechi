"""Wikidata geography graph analysis for variant 12."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import urllib.error
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import matplotlib
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
import scipy
import SPARQLWrapper as sparql_package
from matplotlib.figure import Figure
from SPARQLWrapper import JSON, POST, SPARQLWrapper

WDQS_ENDPOINT = "https://query.wikidata.org/sparql"
QLEVER_ENDPOINT = "https://qlever.dev/api/wikidata"
USER_AGENT = "GeographyKnowledgeGraphCourse/1.0 (educational notebook)"
LANGUAGES = ("uk", "en", "de", "mul")
SCHEMA = {
    "CityCountry": ("City", "Country", "P17"),
    "CityAdmin": ("City", "AdministrativeTerritory", "P131"),
    "AdminCountry": ("AdministrativeTerritory", "Country", "P17"),
}
QUERY = """PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
SELECT DISTINCT ?city ?population ?admin WHERE {
  {
    SELECT ?city (MAX(?pop) AS ?population) WHERE {
      ?city wdt:P17 wd:Q183 ;
            wdt:P31/wdt:P279* wd:Q515 ;
            wdt:P1082 ?pop .
      FILTER(?pop > 1000)
    }
    GROUP BY ?city
    ORDER BY ?city
    LIMIT 1800
  }
  ?city wdt:P131 ?admin .
  ?admin wdt:P17 wd:Q183 ;
         wdt:P31/wdt:P279* wd:Q56061 .
  FILTER(?admin != ?city && ?admin != wd:Q183)
}
ORDER BY ?city ?admin
"""


@dataclass(frozen=True)
class GraphConfig:
    country: str = "Q183"
    min_population: int = 1000
    min_nodes: int = 1500
    seed: int = 12


DEFAULT_CONFIG = GraphConfig()


@dataclass
class AnalysisResult:
    graph: nx.MultiDiGraph
    sampling: dict[str, int]
    global_metrics: dict[str, Any]
    paths_undirected: dict[str, Any]
    paths_directed: dict[str, Any]
    centrality: pd.DataFrame
    node_distribution: pd.DataFrame
    relation_distribution: pd.DataFrame
    semantics: dict[str, Any]
    degrees: pd.DataFrame


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def versions() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "networkx": nx.__version__,
        "matplotlib": matplotlib.__version__,
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "pandas": pd.__version__,
        "SPARQLWrapper": sparql_package.__version__,
    }


def execute_query(query: str, endpoint: str, *, post: bool = False) -> dict[str, Any]:
    client = SPARQLWrapper(endpoint, agent=USER_AGENT)
    client.setQuery(query)
    client.setReturnFormat(JSON)
    client.setTimeout(90)
    if post:
        client.setMethod(POST)
    try:
        result = client.query().convert()
    except urllib.error.HTTPError as error:
        retry_after = error.headers.get("Retry-After", "unspecified")
        raise RuntimeError(
            f"SPARQL HTTP {error.code}; endpoint={endpoint}; Retry-After={retry_after}"
        ) from error
    if not isinstance(result, dict) or "bindings" not in result.get("results", {}):
        raise ValueError("The endpoint did not return SPARQL SELECT JSON results")
    return result


def download_labels(qids: set[str], endpoint: str) -> dict[str, str]:
    values = " ".join(f"wd:{qid}" for qid in sorted(qids))
    query = (
        "PREFIX wd: <http://www.wikidata.org/entity/>\n"
        "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
        f"SELECT ?item ?label WHERE {{ VALUES ?item {{ {values} }} "
        '?item rdfs:label ?label. FILTER(LANG(?label) IN ("uk", "en", "de", "mul")) }'
    )
    result = execute_query(query, endpoint, post=True)
    candidates: dict[str, dict[str, str]] = {qid: {} for qid in qids}
    for row in result["results"]["bindings"]:
        entity = row["item"]["value"].rsplit("/", 1)[-1]
        label = row["label"]
        if entity in candidates:
            candidates[entity][label.get("xml:lang", "")] = label["value"]
    return {
        qid: next((choices[lang] for lang in LANGUAGES if lang in choices), qid)
        for qid, choices in candidates.items()
    }


def download_snapshot(endpoint: str = WDQS_ENDPOINT) -> dict[str, Any]:
    results = execute_query(QUERY, endpoint)
    qids = {
        row[key]["value"].rsplit("/", 1)[-1]
        for row in results["results"]["bindings"]
        for key in ("city", "admin")
    } | {"Q183"}
    return {
        "results": results,
        "labels": download_labels(qids, endpoint),
        "provenance": {
            "endpoint": endpoint,
            "labels_endpoint": endpoint,
            "retrieved_at_utc": datetime.now(UTC).isoformat(),
            "query_sha256": hashlib.sha256(QUERY.encode()).hexdigest(),
            "mode": "new Wikidata SPARQL response",
        },
    }


def load_snapshot(data_directory: Path) -> dict[str, Any]:
    files = {
        "results": "sparql_results.json",
        "labels": "labels.json",
        "provenance": "retrieval.json",
    }
    snapshot = {
        key: json.loads((data_directory / name).read_text(encoding="utf-8"))
        for key, name in files.items()
    }
    provenance = snapshot["provenance"]
    if provenance["query_sha256"] != hashlib.sha256(QUERY.encode()).hexdigest():
        raise ValueError("The snapshot belongs to a different SPARQL query")
    raw_hash = hashlib.sha256(
        (data_directory / files["results"]).read_bytes()
    ).hexdigest()
    if provenance.get("response_sha256") != raw_hash:
        raise ValueError("The saved SPARQL response checksum does not match")
    return snapshot


def normalize_rows(
    bindings: list[dict[str, Any]], config: GraphConfig
) -> list[dict[str, Any]]:
    rows = []
    for binding in bindings:
        city = binding["city"]["value"].rsplit("/", 1)[-1]
        admin = binding["admin"]["value"].rsplit("/", 1)[-1]
        population = float(binding["population"]["value"])
        if not all(qid.startswith("Q") and qid[1:].isdigit() for qid in (city, admin)):
            raise ValueError("Every entity must have a Wikidata QID")
        if not math.isfinite(population) or population <= config.min_population:
            raise ValueError(f"Population filter violated for {city}")
        rows.append({"city": city, "admin": admin, "population": population})
    if not rows:
        raise ValueError("The query returned no matching cities")
    return rows


def validate_graph(graph: nx.MultiDiGraph, config: GraphConfig) -> None:
    if len(graph) < config.min_nodes:
        raise ValueError(
            f"Only {len(graph)} nodes; required at least {config.min_nodes}"
        )
    if {d["type"] for _, d in graph.nodes(data=True)} != {
        "City",
        "Country",
        "AdministrativeTerritory",
    }:
        raise ValueError("The graph must contain exactly three node types")
    if {d["relation"] for *_, d in graph.edges(data=True)} != set(SCHEMA):
        raise ValueError("The graph must contain exactly three typed relations")
    if nx.number_of_selfloops(graph) or min(dict(graph.degree()).values()) < 2:
        raise ValueError("Self-loops, isolated nodes or degree-one nodes found")
    if not nx.is_weakly_connected(graph) or not nx.is_directed_acyclic_graph(graph):
        raise ValueError("The graph must be weakly connected and directed acyclic")
    for source, target, data in graph.edges(data=True):
        actual = (
            graph.nodes[source]["type"],
            graph.nodes[target]["type"],
            data["property"],
        )
        if actual != SCHEMA[data["relation"]]:
            raise ValueError(f"Invalid edge schema: {source} -> {target}")
    for node, data in graph.nodes(data=True):
        if node != config.country and not graph.has_edge(node, config.country):
            raise ValueError(f"Missing country core edge for {node}")
        if data["type"] == "City" and data["population"] <= config.min_population:
            raise ValueError(f"Population filter violated for {node}")


def build_graph(
    snapshot: dict[str, Any],
    config: GraphConfig = DEFAULT_CONFIG,
) -> tuple[nx.MultiDiGraph, dict[str, int]]:
    rows = normalize_rows(snapshot["results"]["results"]["bindings"], config)
    raw_cities = {row["city"] for row in rows}
    raw_admins = {row["admin"] for row in rows}
    retained = [
        row
        for row in rows
        if row["admin"] not in raw_cities
        and config.country not in (row["city"], row["admin"])
    ]
    labels = snapshot["labels"]
    graph = nx.MultiDiGraph(
        name="Wikidata Geography Variant 12",
        variant=12,
        domain=5,
        numeric_filter=f"P1082 > {config.min_population}",
        source=snapshot["provenance"]["endpoint"],
        retrieved_at_utc=snapshot["provenance"]["retrieved_at_utc"],
    )

    def add_entity(entity: str, node_type: str, class_qid: str, **attrs: Any) -> None:
        graph.add_node(
            entity,
            label=labels.get(entity, entity),
            type=node_type,
            class_qid=class_qid,
            wikidata_uri=f"https://www.wikidata.org/wiki/{entity}",
            **attrs,
        )

    def add_statement(source: str, target: str, prop: str, relation: str) -> None:
        graph.add_edge(
            source,
            target,
            key=prop,
            property=prop,
            relation=relation,
            property_uri=f"http://www.wikidata.org/prop/direct/{prop}",
        )

    add_entity(config.country, "Country", "Q6256")
    for row in retained:
        city, admin = row["city"], row["admin"]
        add_entity(city, "City", "Q515", population=row["population"])
        add_entity(admin, "AdministrativeTerritory", "Q56061")
        add_statement(city, config.country, "P17", "CityCountry")
        add_statement(city, admin, "P131", "CityAdmin")
        add_statement(admin, config.country, "P17", "AdminCountry")
    validate_graph(graph, config)
    sampling = {
        "source_rows": len(rows),
        "source_cities": len(raw_cities),
        "source_administrative_units": len(raw_admins),
        "discarded_role_conflict_rows": len(rows) - len(retained),
    }
    return graph, sampling


def path_statistics(graph: nx.Graph) -> dict[str, Any]:
    """Count exact distances between distinct reachable ordered pairs."""
    histogram: Counter[int] = Counter()
    for source, distances in nx.all_pairs_shortest_path_length(graph):
        histogram.update(
            length for target, length in distances.items() if target != source
        )
    pairs = sum(histogram.values())
    if not pairs:
        raise ValueError("The graph has no reachable pair of distinct nodes")
    possible = len(graph) * (len(graph) - 1)
    return {
        "min": min(histogram),
        "max": max(histogram),
        "mean": sum(length * count for length, count in histogram.items()) / pairs,
        "reachable_ordered_pairs": pairs,
        "possible_ordered_pairs": possible,
        "reachable_fraction": pairs / possible,
        "length_histogram": dict(sorted(histogram.items())),
    }


def calculate_global_metrics(
    graph: nx.MultiDiGraph,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    undirected = nx.Graph(graph)
    degrees = np.array([degree for _, degree in graph.degree()])
    metrics = {
        "nodes": len(graph),
        "edges": graph.number_of_edges(),
        "density_directed": nx.density(graph),
        "density_undirected": nx.density(undirected),
        "degree_mean": float(degrees.mean()),
        "degree_min": int(degrees.min()),
        "degree_max": int(degrees.max()),
        "in_degree_mean": float(np.mean([d for _, d in graph.in_degree()])),
        "out_degree_mean": float(np.mean([d for _, d in graph.out_degree()])),
        "average_clustering_undirected": nx.average_clustering(undirected),
        "transitivity_undirected": nx.transitivity(undirected),
        "weak_components": nx.number_weakly_connected_components(graph),
        "strong_components": nx.number_strongly_connected_components(graph),
        "isolates": len(list(nx.isolates(graph))),
    }
    return metrics, path_statistics(undirected), path_statistics(nx.DiGraph(graph))


def calculate_centrality(graph: nx.MultiDiGraph) -> pd.DataFrame:
    degree = nx.degree_centrality(graph)
    directed_betweenness = nx.betweenness_centrality(
        graph, normalized=True, weight=None
    )
    undirected_betweenness = nx.betweenness_centrality(
        nx.Graph(graph), normalized=True, weight=None
    )
    pagerank = nx.pagerank(graph, alpha=0.85, tol=1e-12, max_iter=1000, weight=None)
    return pd.DataFrame(
        [
            {
                "qid": node,
                "label": data["label"],
                "type": data["type"],
                "degree": graph.degree(node),
                "degree_centrality": degree[node],
                "betweenness_directed": directed_betweenness[node],
                "betweenness_undirected": undirected_betweenness[node],
                "pagerank": pagerank[node],
            }
            for node, data in graph.nodes(data=True)
        ]
    ).set_index("qid")


def distribution(counts: Counter[str]) -> pd.DataFrame:
    total = counts.total()
    if not total:
        raise ValueError("Cannot calculate a distribution from empty counts")
    return pd.DataFrame(
        [
            {
                "Тип": name,
                "Кількість": count,
                "Частка": count / total,
                "Відсоток": 100 * count / total,
            }
            for name, count in sorted(counts.items())
        ]
    )


def diversity(counts: Counter[str], vocabulary_size: int = 3) -> dict[str, float]:
    if (
        vocabulary_size < 2
        or not counts
        or any(count <= 0 for count in counts.values())
    ):
        raise ValueError(
            "Diversity requires positive counts and at least two possible types"
        )
    probabilities = np.array(list(counts.values()), dtype=float)
    probabilities /= probabilities.sum()
    entropy = float(-np.sum(probabilities * np.log2(probabilities)))
    return {
        "entropy_bits": entropy,
        "normalized_entropy": entropy / math.log2(vocabulary_size),
        "simpson_diversity": float(1 - np.sum(probabilities**2)),
    }


def calculate_semantic_metrics(
    graph: nx.MultiDiGraph,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any], dict[str, float]]:
    nodes = Counter(data["type"] for _, data in graph.nodes(data=True))
    relations = Counter(data["relation"] for *_, data in graph.edges(data=True))
    local = {}
    for node in graph:
        counts = Counter(d["relation"] for *_, d in graph.in_edges(node, data=True))
        counts.update(d["relation"] for *_, d in graph.out_edges(node, data=True))
        local[node] = diversity(counts)["normalized_entropy"]
    metrics = {
        "node_types": diversity(nodes),
        "relation_types": diversity(relations),
        "local_relation_diversity_mean": float(np.mean(list(local.values()))),
    }
    return distribution(nodes), distribution(relations), metrics, local


def degree_distribution(graph: nx.MultiDiGraph) -> pd.DataFrame:
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


def plot_graph(graph: nx.MultiDiGraph, config: GraphConfig = DEFAULT_CONFIG) -> Figure:
    cities = {node for node, data in graph.nodes(data=True) if data["type"] == "City"}
    admins = {
        node
        for node, data in graph.nodes(data=True)
        if data["type"] == "AdministrativeTerritory"
    }
    groups: dict[str, list[str]] = defaultdict(list)
    for city in sorted(cities):
        parents = sorted(
            v
            for _, v, d in graph.out_edges(city, data=True)
            if d["relation"] == "CityAdmin"
        )
        groups[parents[0]].append(city)
    positions = {config.country: np.zeros(2)}
    slots = sum(max(len(groups.get(admin, [])), 1) + 1 for admin in admins)
    cursor = 0
    rng = np.random.default_rng(config.seed)
    for admin in sorted(admins):
        members = groups.get(admin, [])
        width = max(len(members), 1)
        angle = 2 * np.pi * (cursor + width / 2) / slots
        positions[admin] = 1.05 * np.array([np.cos(angle), np.sin(angle)])
        for offset, city in enumerate(members):
            angle = 2 * np.pi * (cursor + offset + 0.5) / slots
            positions[city] = rng.uniform(1.8, 2.65) * np.array(
                [np.cos(angle), np.sin(angle)]
            )
        cursor += width + 1
    figure, axes = plt.subplots(figsize=(13, 11))
    for relation, color, alpha in (
        ("CityCountry", "#8493A3", 0.045),
        ("CityAdmin", "#2F80B7", 0.13),
        ("AdminCountry", "#E49A32", 0.28),
    ):
        edges = [
            (u, v) for u, v, d in graph.edges(data=True) if d["relation"] == relation
        ]
        nx.draw_networkx_edges(
            graph,
            positions,
            edgelist=edges,
            edge_color=color,
            alpha=alpha,
            width=0.55,
            arrows=False,
            ax=axes,
        )
    for node_type, color, size in (
        ("City", "#2F80B7", 7),
        ("AdministrativeTerritory", "#E49A32", 30),
        ("Country", "#963C62", 230),
    ):
        nodes = [
            node for node, data in graph.nodes(data=True) if data["type"] == node_type
        ]
        nx.draw_networkx_nodes(
            graph,
            positions,
            nodelist=nodes,
            node_size=size,
            node_color=color,
            alpha=0.9,
            linewidths=0,
            label=f"{node_type} ({len(nodes)})",
            ax=axes,
        )
    nx.draw_networkx_labels(
        graph,
        positions,
        labels={config.country: graph.nodes[config.country]["label"]},
        font_size=11,
        font_weight="bold",
        verticalalignment="bottom",
        ax=axes,
    )
    axes.set_title(
        f"Географічний граф Wikidata · варіант 12\n"
        f"{len(graph)} вузлів · {graph.number_of_edges()} ребер · спільне ядро Q183",
        fontsize=15,
        pad=18,
    )
    axes.legend(loc="lower left", frameon=False, markerscale=1.3)
    axes.text(
        0.99,
        0.015,
        "Стрілки приховано для читабельності.\nНапрямки збережено у GraphML.",
        transform=axes.transAxes,
        ha="right",
        fontsize=9,
        color="#4B5563",
    )
    axes.set_aspect("equal")
    axes.axis("off")
    figure.tight_layout()
    return figure


def plot_degree_distribution(
    graph: nx.MultiDiGraph, frequencies: pd.DataFrame
) -> Figure:
    degrees = np.array([degree for _, degree in graph.degree()])
    low_limit = max(6, min(20, int(np.quantile(degrees, 0.95))))
    figure, axes = plt.subplots(1, 3, figsize=(15, 4.8))
    axes[0].hist(
        degrees[degrees <= low_limit],
        bins=np.arange(0.5, low_limit + 1.5),
        color="#2F80B7",
        edgecolor="white",
        rwidth=0.85,
    )
    axes[0].set(
        title=f"Гістограма степенів k ≤ {low_limit}",
        xlabel="Сумарний степінь k",
        ylabel="Кількість вузлів",
    )
    axes[0].text(
        0.97,
        0.96,
        f"За межами панелі: {int(np.sum(degrees > low_limit))} вузлів",
        ha="right",
        va="top",
        transform=axes[0].transAxes,
        fontsize=9,
    )
    axes[1].scatter(frequencies.degree, frequencies.fraction, s=32, color="#963C62")
    axes[1].set(
        xscale="log",
        yscale="log",
        title="Повний розподіл P(K = k)",
        xlabel="Степінь k · log",
        ylabel="Частка вузлів · log",
    )
    axes[2].step(
        frequencies.degree, frequencies.ccdf, where="post", color="#E49A32", linewidth=2
    )
    axes[2].scatter(frequencies.degree, frequencies.ccdf, s=15, color="#E49A32")
    axes[2].set(
        xscale="log",
        yscale="log",
        title="Повна емпірична CCDF",
        xlabel="Степінь k · log",
        ylabel="P(K ≥ k) · log",
    )
    for axis in axes:
        axis.grid(axis="y", color="#E5E7EB", alpha=0.8)
    figure.suptitle(
        "Розподіл сумарних степенів географічного графа Wikidata", fontsize=14, y=1.03
    )
    figure.tight_layout()
    return figure


def analyze_snapshot(
    snapshot: dict[str, Any], config: GraphConfig = DEFAULT_CONFIG
) -> AnalysisResult:
    graph, sampling = build_graph(snapshot, config)
    metrics, undirected, directed = calculate_global_metrics(graph)
    centrality = calculate_centrality(graph)
    nodes, relations, semantics, local = calculate_semantic_metrics(graph)
    centrality["local_relation_diversity"] = pd.Series(local)
    return AnalysisResult(
        graph,
        sampling,
        metrics,
        undirected,
        directed,
        centrality,
        nodes,
        relations,
        semantics,
        degree_distribution(graph),
    )


def export_results(
    result: AnalysisResult,
    snapshot: dict[str, Any],
    output: Path,
    *,
    plots: bool = True,
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    graph = result.graph
    nx.write_graphml(graph, output / "variant12_geography.graphml")
    write_json(
        output / "variant12_geography.json", nx.node_link_data(graph, edges="edges")
    )
    write_json(output / "wikidata_snapshot.json", snapshot)
    (output / "query.rq").write_text(QUERY, encoding="utf-8", newline="\n")
    for filename, table, index in (
        ("centrality_all_nodes.csv", result.centrality, True),
        ("node_type_distribution.csv", result.node_distribution, False),
        ("relation_type_distribution.csv", result.relation_distribution, False),
        ("degree_distribution.csv", result.degrees, False),
    ):
        table.to_csv(
            output / filename, index=index, encoding="utf-8-sig", lineterminator="\n"
        )
    write_json(
        output / "metrics.json",
        {
            "variant": 12,
            "domain": 5,
            "filter_variant": "A",
            "global": result.global_metrics,
            "paths_undirected": result.paths_undirected,
            "paths_directed_reachable": result.paths_directed,
            "semantic": result.semantics,
            "node_type_counts": dict(
                Counter(d["type"] for _, d in graph.nodes(data=True))
            ),
            "relation_type_counts": dict(
                Counter(d["relation"] for *_, d in graph.edges(data=True))
            ),
            "predicate_counts": dict(
                Counter(d["property"] for *_, d in graph.edges(data=True))
            ),
            "sampling": result.sampling,
            "provenance": snapshot["provenance"],
            "versions": versions(),
        },
    )
    if plots:
        for name, figure in (
            ("graph.png", plot_graph(graph)),
            (
                "degree_distribution.png",
                plot_degree_distribution(graph, result.degrees),
            ),
        ):
            figure.savefig(output / name, dpi=180, bbox_inches="tight")
            plt.close(figure)
    write_json(
        output / "sha256.json",
        {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(output.iterdir())
            if path.is_file() and path.name != "sha256.json"
        },
    )


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=root / "data")
    parser.add_argument("--output", type=Path, default=root / "outputs")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--endpoint", choices=("wdqs", "qlever"), default="wdqs")
    parser.add_argument("--no-plots", action="store_true")
    args = parser.parse_args(argv)
    endpoint = WDQS_ENDPOINT if args.endpoint == "wdqs" else QLEVER_ENDPOINT
    snapshot = (
        download_snapshot(endpoint) if args.refresh else load_snapshot(args.data_dir)
    )
    result = analyze_snapshot(snapshot)
    export_results(result, snapshot, args.output, plots=not args.no_plots)
    print(json.dumps(result.global_metrics, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
