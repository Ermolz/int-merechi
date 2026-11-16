"""Node2Vec and TransE for the saved Wikidata geography graph."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import random
import textwrap
import warnings
import zlib
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
import torch
from gensim.models import Word2Vec
from matplotlib.figure import Figure
from pykeen.losses import MarginRankingLoss
from pykeen.models import TransE
from pykeen.sampling.filtering import PythonSetFilterer
from pykeen.training import SLCWATrainingLoop
from pykeen.triples import TriplesFactory
from scipy.stats import spearmanr
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE, trustworthiness

INPUT_SHA256 = "5ec861b5967eb325c6dfae0ce7a36993b95d44e8da5a34e86f539d990616561e"
COUNTRY = "Q183"
PARAMETERS = ((1.0, 1.0), (0.5, 2.0), (2.0, 0.5))
QUERIES = ("Q253696", "Q59564401", "Q6339", "Q15852582")
COLORS = {"City": "#2878B5", "AdministrativeTerritory": "#E49A32", "Country": "#B83B5E"}


@dataclass(frozen=True)
class Config:
    seed: int = 12
    dimensions: int = 32
    walk_length: int = 20
    num_walks: int = 8
    window: int = 5
    word2vec_epochs: int = 10
    transe_epochs: int = 100
    batch_size: int = 256
    learning_rate: float = 0.01
    negatives: int = 5


DEFAULT_CONFIG = Config()


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def prepare_graph(payload: bytes) -> tuple[nx.DiGraph, np.ndarray, pd.DataFrame]:
    if hashlib.sha256(payload).hexdigest() != INPUT_SHA256:
        raise ValueError("The input differs from the saved geography graph")
    original = nx.node_link_graph(json.loads(payload), edges="edges")
    graph = nx.DiGraph()
    graph.add_nodes_from((node, dict(original.nodes[node])) for node in sorted(original))
    triples = []
    for subject, target, data in sorted(original.edges(data=True)):
        predicate = data["property"]
        if predicate not in {"P17", "P131"}:
            raise ValueError("Unexpected Wikidata predicate")
        graph.add_edge(subject, target, property=predicate, relation=data["relation"])
        triples.append((subject, predicate, target))
    entities = pd.DataFrame(
        [
            {"id": node, "class": data["type"], "label": data["label"]}
            for node, data in graph.nodes(data=True)
        ]
    ).set_index("id", drop=False)
    assert len(graph) == 2389 and len(triples) == 4402
    assert nx.is_weakly_connected(graph) and not list(nx.isolates(graph))
    assert set(entities["class"]) == set(COLORS)
    return graph, np.asarray(triples, dtype=str), entities


def transition_probabilities(
    graph: nx.Graph, previous: str, current: str, p: float, q: float
) -> tuple[list[str], np.ndarray]:
    if p <= 0 or q <= 0:
        raise ValueError("p and q must be positive")
    neighbors = sorted(graph.neighbors(current))
    weights = np.array(
        [
            1 / p if node == previous else 1.0 if graph.has_edge(node, previous) else 1 / q
            for node in neighbors
        ]
    )
    return neighbors, weights / weights.sum() if len(weights) else weights


def biased_walks(
    graph: nx.Graph, config: Config, p: float, q: float
) -> tuple[list[list[str]], dict[str, float]]:
    rng = np.random.default_rng(config.seed)
    nodes = sorted(graph)
    adjacency = {node: sorted(graph.neighbors(node)) for node in nodes}
    cache = {}
    walks = []
    for _ in range(config.num_walks):
        for start in rng.permutation(nodes):
            walk = [str(start)]
            while len(walk) < config.walk_length and adjacency[walk[-1]]:
                current = walk[-1]
                if len(walk) == 1:
                    following = adjacency[current][rng.integers(len(adjacency[current]))]
                else:
                    key = (walk[-2], current)
                    if key not in cache:
                        neighbors, probabilities = transition_probabilities(graph, *key, p, q)
                        cumulative = probabilities.cumsum()
                        cumulative[-1] = 1.0
                        cache[key] = (neighbors, cumulative)
                    neighbors, cumulative = cache[key]
                    following = neighbors[np.searchsorted(cumulative, rng.random())]
                walk.append(following)
            walks.append(walk)
    opportunities = sum(max(0, len(walk) - 2) for walk in walks)
    returns = sum(walk[i] == walk[i - 2] for walk in walks for i in range(2, len(walk)))
    return walks, {
        "mean_walk_length": float(np.mean([len(walk) for walk in walks])),
        "return_fraction": returns / opportunities if opportunities else 0.0,
        "mean_unique_fraction": float(np.mean([len(set(walk)) / len(walk) for walk in walks])),
    }


def stable_hash(value: str) -> int:
    return zlib.crc32(value.encode("utf-8"))


def train_node2vec(
    graph: nx.Graph, config: Config, p: float, q: float
) -> tuple[np.ndarray, dict[str, float]]:
    walks, statistics = biased_walks(graph, config, p, q)
    model = Word2Vec(
        sentences=walks,
        vector_size=config.dimensions,
        window=config.window,
        min_count=1,
        sg=1,
        negative=config.negatives,
        sample=0,
        epochs=config.word2vec_epochs,
        workers=1,
        seed=config.seed,
        hashfxn=stable_hash,
        shrink_windows=False,
    )
    matrix = np.stack([model.wv[node] for node in sorted(graph)])
    assert matrix.shape == (len(graph), config.dimensions) and np.isfinite(matrix).all()
    return matrix, statistics


def normalized(matrix: np.ndarray) -> np.ndarray:
    lengths = np.linalg.norm(matrix, axis=1, keepdims=True)
    return np.divide(matrix, lengths, out=np.zeros_like(matrix), where=lengths > 0)


def shared_context(graph: nx.Graph, first: str, second: str) -> tuple[int, float]:
    left = set(graph[first]) - {COUNTRY}
    right = set(graph[second]) - {COUNTRY}
    common = len(left & right)
    return common, common / len(left | right) if left | right else 0.0


def nearest_neighbors(
    matrix: np.ndarray,
    entities: pd.DataFrame,
    graph: nx.Graph,
    query: str,
    top_k: int = 5,
    same_class: bool = True,
) -> pd.DataFrame:
    ids = entities.id.to_numpy()
    if query not in entities.index:
        raise ValueError("Unknown query entity")
    unit = normalized(matrix)
    scores = unit @ unit[entities.index.get_loc(query)]
    candidates = [
        i
        for i, node in enumerate(ids)
        if node != query
        and (not same_class or entities.at[node, "class"] == entities.at[query, "class"])
    ]
    ranked = sorted(candidates, key=lambda i: (-float(scores[i]), ids[i]))[:top_k]
    return pd.DataFrame(
        [
            {
                "query": query,
                "query_label": entities.at[query, "label"],
                "neighbor": ids[i],
                "label": entities.at[ids[i], "label"],
                "class": entities.at[ids[i], "class"],
                "cosine": float(scores[i]),
                "shared_specific": shared_context(graph, query, ids[i])[0],
                "jaccard_specific": shared_context(graph, query, ids[i])[1],
            }
            for i in ranked
        ]
    )


def comparison_pairs(graph: nx.Graph, entities: pd.DataFrame, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    records = []
    for kind in ("City", "AdministrativeTerritory"):
        nodes = sorted(entities.index[entities["class"] == kind])
        for strategy in ("random", "shared_neighbor"):
            accepted = set()
            attempts = 0
            while len(accepted) < 500 and attempts < 20000:
                attempts += 1
                first = str(rng.choice(nodes))
                if strategy == "random":
                    second = str(rng.choice(nodes))
                else:
                    specific = sorted(set(graph[first]) - {COUNTRY})
                    if not specific:
                        continue
                    bridge = str(rng.choice(specific))
                    peers = sorted(
                        node
                        for node in graph[bridge]
                        if entities.at[node, "class"] == kind and node != first
                    )
                    if not peers:
                        continue
                    second = str(rng.choice(peers))
                if first == second:
                    continue
                accepted.add(tuple(sorted((first, second))))
            for first, second in sorted(accepted):
                common, jaccard = shared_context(graph, first, second)
                records.append(
                    {
                        "first": first,
                        "second": second,
                        "class": kind,
                        "sample": strategy,
                        "shared_specific": common,
                        "jaccard_specific": jaccard,
                    }
                )
    return pd.DataFrame(records)


def similarity_correlation(
    matrix: np.ndarray, entities: pd.DataFrame, pairs: pd.DataFrame
) -> float:
    unit = normalized(matrix)
    indices = {node: i for i, node in enumerate(entities.index)}
    cosine = np.array(
        [float(unit[indices[row.first]] @ unit[indices[row.second]]) for row in pairs.itertuples()]
    )
    if np.ptp(cosine) == 0 or pairs.jaccard_specific.nunique() < 2:
        return 0.0
    return float(spearmanr(cosine, pairs.jaccard_specific).statistic)


def node2vec_experiments(
    graph: nx.DiGraph, entities: pd.DataFrame, config: Config
) -> tuple[dict[str, np.ndarray], pd.DataFrame, pd.DataFrame]:
    undirected = graph.to_undirected()
    pairs = comparison_pairs(undirected, entities, config.seed)
    matrices, records = {}, []
    for direction, topology in (("U", undirected), ("D", graph)):
        for p, q in PARAMETERS:
            name = f"{direction}_p{p:g}_q{q:g}"
            matrix, statistics = train_node2vec(topology, config, p, q)
            matrices[name] = matrix
            matches = [nearest_neighbors(matrix, entities, undirected, query) for query in QUERIES]
            fraction = float(pd.concat(matches).shared_specific.gt(0).mean())
            records.append(
                {
                    "model": name,
                    "direction": direction,
                    "p": p,
                    "q": q,
                    **statistics,
                    "spearman_specific": similarity_correlation(matrix, entities, pairs),
                    "shared_context_at5": fraction,
                }
            )
    return matrices, pd.DataFrame(records), pairs


def train_transe(
    triples: np.ndarray, entities: pd.DataFrame, config: Config
) -> tuple[np.ndarray, np.ndarray, TriplesFactory, list[float]]:
    random.seed(config.seed)
    np.random.seed(config.seed)
    torch.manual_seed(config.seed)
    torch.set_num_threads(2)
    torch.use_deterministic_algorithms(True)
    logging.getLogger("pykeen").setLevel(logging.ERROR)
    factory = TriplesFactory.from_labeled_triples(
        triples,
        entity_to_id={node: i for i, node in enumerate(entities.index)},
        relation_to_id={relation: i for i, relation in enumerate(sorted(set(triples[:, 1])))},
    )
    model = TransE(
        triples_factory=factory,
        embedding_dim=config.dimensions,
        scoring_fct_norm=1,
        loss=MarginRankingLoss(margin=1.0),
        random_seed=config.seed,
    ).to("cpu")
    optimizer = torch.optim.Adam(model.get_grad_params(), lr=config.learning_rate)
    loop = SLCWATrainingLoop(
        model=model,
        triples_factory=factory,
        optimizer=optimizer,
        negative_sampler="basic",
        negative_sampler_kwargs={
            "num_negs_per_pos": config.negatives,
            "filtered": True,
            "filterer": PythonSetFilterer,
        },
        automatic_memory_optimization=False,
    )
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", message="Training instances are always shuffled.", category=DeprecationWarning
        )
        losses = loop.train(
            triples_factory=factory,
            num_epochs=config.transe_epochs,
            batch_size=config.batch_size,
            use_tqdm=False,
            use_tqdm_batch=False,
            num_workers=0,
            pin_memory=False,
        )
    model.eval()
    with torch.no_grad():
        entity_matrix = model.entity_representations[0]().cpu().numpy().copy()
        relation_matrix = model.relation_representations[0]().cpu().numpy().copy()
    assert entity_matrix.shape == (len(entities), config.dimensions)
    assert relation_matrix.shape == (len(set(triples[:, 1])), config.dimensions)
    assert np.isfinite(entity_matrix).all() and np.isfinite(relation_matrix).all()
    assert factory.entity_to_id == {node: i for i, node in enumerate(entities.index)}
    return entity_matrix, relation_matrix, factory, [float(loss) for loss in losses]


def translation_examples(
    graph: nx.DiGraph,
    entities: pd.DataFrame,
    vectors: np.ndarray,
    relations: np.ndarray,
    factory: TriplesFactory,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    records = []
    for subject, target, data in sorted(graph.edges(data=True)):
        head = vectors[factory.entity_to_id[subject]]
        relation = relations[factory.relation_to_id[data["property"]]]
        tail = vectors[factory.entity_to_id[target]]
        prediction = head + relation
        denominator = np.linalg.norm(prediction) * np.linalg.norm(tail)
        records.append(
            {
                "subject": subject,
                "subject_label": entities.at[subject, "label"],
                "relation_type": data["relation"],
                "predicate": data["property"],
                "object": target,
                "object_label": entities.at[target, "label"],
                "error_l1": float(np.linalg.norm(prediction - tail, ord=1)),
                "cosine_h_plus_r_t": float(prediction @ tail / denominator) if denominator else 0.0,
            }
        )
    data = pd.DataFrame(records)
    examples = data.groupby("relation_type", sort=True).head(3).reset_index(drop=True)
    summary = (
        data.groupby(["relation_type", "predicate"])
        .agg(
            triples=("error_l1", "size"),
            mean_l1=("error_l1", "mean"),
            median_l1=("error_l1", "median"),
            mean_cosine=("cosine_h_plus_r_t", "mean"),
        )
        .reset_index()
    )
    return examples, summary


def projections(
    matrices: dict[str, np.ndarray], config: Config
) -> tuple[dict[str, np.ndarray], pd.DataFrame]:
    coordinates, rows = {}, []
    for name, matrix in matrices.items():
        for method in ("PCA", "t-SNE"):
            if method == "PCA":
                reducer = PCA(n_components=2, svd_solver="full")
                points = reducer.fit_transform(matrix)
                variance = float(reducer.explained_variance_ratio_.sum())
            else:
                points = TSNE(
                    n_components=2,
                    perplexity=30,
                    max_iter=1000,
                    init="pca",
                    learning_rate="auto",
                    random_state=config.seed,
                    n_jobs=1,
                ).fit_transform(matrix)
                variance = None
            key = f"{name}_{method}"
            coordinates[key] = points
            rows.append(
                {
                    "model": name,
                    "projection": method,
                    "pca_variance": variance,
                    "trustworthiness_k10": float(trustworthiness(matrix, points, n_neighbors=10)),
                }
            )
    return coordinates, pd.DataFrame(rows)


def plot_projections(coordinates: dict[str, np.ndarray], entities: pd.DataFrame) -> Figure:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    figure, axes = plt.subplots(2, 2, figsize=(14, 11))
    ids = list(entities.index)
    labels = [COUNTRY, *QUERIES]
    for axis, (key, points) in zip(axes.flat, coordinates.items(), strict=True):
        for kind, color in COLORS.items():
            mask = entities["class"].to_numpy() == kind
            axis.scatter(
                points[mask, 0],
                points[mask, 1],
                s=65 if kind == "Country" else 9,
                color=color,
                alpha=0.9 if kind == "Country" else 0.55,
                marker="X" if kind == "Country" else "o",
                label=kind,
            )
        for j, node in enumerate(labels):
            index = ids.index(node)
            axis.annotate(
                textwrap.fill(entities.at[node, "label"], 19),
                points[index],
                xytext=(
                    -100 if points[index, 0] > np.median(points[:, 0]) else 20,
                    (55, 85, -55, -85, 25)[j],
                ),
                textcoords="offset points",
                fontsize=8,
                bbox={"facecolor": "white", "edgecolor": "none", "alpha": 1.0},
                arrowprops={"arrowstyle": "-", "color": "#666666", "linewidth": 0.6},
            )
        axis.set(title=key.replace("_", " — "), xlabel="Вимір 1", ylabel="Вимір 2")
        axis.grid(alpha=0.12)
        axis.margins(0.15)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="upper center", ncol=3, frameon=False)
    figure.tight_layout(rect=(0, 0, 1, 0.96))
    return figure


def compare_models(
    matrices: dict[str, np.ndarray], entities: pd.DataFrame, graph: nx.Graph
) -> tuple[pd.DataFrame, pd.DataFrame]:
    results = []
    for name, matrix in matrices.items():
        for query in QUERIES:
            neighbors = nearest_neighbors(matrix, entities, graph, query)
            neighbors.insert(0, "model", name)
            results.append(neighbors)
    neighbors = pd.concat(results, ignore_index=True)
    summary = (
        neighbors.groupby(["model", "query", "query_label"], sort=False)
        .agg(
            shared_context_at5=("shared_specific", lambda values: float(values.gt(0).mean())),
            mean_specific_jaccard=("jaccard_specific", "mean"),
        )
        .reset_index()
    )
    return neighbors, summary


def export_results(result: dict, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    entities, triples = result["entities"], result["triples"]
    entities.to_csv(output / "entities.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(triples, columns=["subject", "predicate", "object"]).to_csv(
        output / "triples.tsv", sep="\t", index=False
    )
    for name, table in result["tables"].items():
        table.to_csv(output / f"{name}.csv", index=False, encoding="utf-8-sig", lineterminator="\n")
    relation_ids = sorted(result["relation_to_id"], key=result["relation_to_id"].get)
    np.savez_compressed(
        output / "embeddings.npz",
        **result["matrices"],
        TransE=result["transe"],
        relations=result["relations"],
        entity_ids=entities.id.to_numpy(dtype=str),
        relation_ids=np.array(relation_ids),
    )
    np.savez_compressed(output / "projections.npz", **result["coordinates"])
    write_json(
        output / "mapping.json",
        {
            "entity_to_id": {node: i for i, node in enumerate(entities.index)},
            "relation_to_id": result["relation_to_id"],
        },
    )
    figure = plot_projections(result["coordinates"], entities)
    figure.savefig(output / "projections.png", dpi=170, bbox_inches="tight")
    plt.close(figure)
    write_json(output / "metrics.json", result["metrics"])


def run_analysis(payload: bytes, output: Path, config: Config = DEFAULT_CONFIG) -> dict:
    graph, triples, entities = prepare_graph(payload)
    print("Node2Vec: 6 experiments", flush=True)
    matrices, experiments, pairs = node2vec_experiments(graph, entities, config)
    print("TransE: training", flush=True)
    vectors, relations, factory, losses = train_transe(triples, entities, config)
    examples, translations = translation_examples(graph, entities, vectors, relations, factory)
    chosen = {"Node2Vec": matrices["U_p1_q1"], "TransE": vectors}
    print("PCA and t-SNE", flush=True)
    coordinates, projection_metrics = projections(chosen, config)
    neighbors, comparison = compare_models(chosen, entities, graph.to_undirected())
    tables = {
        "node2vec_experiments": experiments,
        "sampled_pairs": pairs,
        "translation_examples": examples,
        "translation_summary": translations,
        "projection_metrics": projection_metrics,
        "nearest_neighbors": neighbors,
        "model_comparison": comparison,
        "training_loss": pd.DataFrame({"epoch": range(1, len(losses) + 1), "loss": losses}),
    }
    metrics = {
        "variant": 12,
        "nodes": len(graph),
        "triples": len(triples),
        "relations": factory.relation_to_id,
        "input_sha256": INPUT_SHA256,
        "config": asdict(config),
        "loss_first": losses[0],
        "loss_last": losses[-1],
    }
    result = {
        "graph": graph,
        "entities": entities,
        "triples": triples,
        "matrices": matrices,
        "transe": vectors,
        "relations": relations,
        "factory": factory,
        "losses": losses,
        "relation_to_id": factory.relation_to_id,
        "coordinates": coordinates,
        "tables": tables,
        "metrics": metrics,
    }
    export_results(result, output)
    return result


def main() -> None:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=root / "data/geography_graph.json")
    parser.add_argument("--output", type=Path, default=root / "outputs")
    args = parser.parse_args()
    result = run_analysis(args.input.read_bytes(), args.output)
    print(json.dumps(result["metrics"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
