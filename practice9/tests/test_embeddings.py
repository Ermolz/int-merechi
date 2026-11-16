from dataclasses import replace

import networkx as nx
import numpy as np
import pandas as pd
import pytest

from graph_embeddings import (
    Config,
    biased_walks,
    nearest_neighbors,
    shared_context,
    train_node2vec,
    train_transe,
    transition_probabilities,
)


def test_return_and_outward_bias():
    graph = nx.path_graph(["a", "b", "c"])
    nodes, probabilities = transition_probabilities(graph, "a", "b", p=0.5, q=2)
    assert nodes == ["a", "c"]
    assert probabilities == pytest.approx([0.8, 0.2])
    with pytest.raises(ValueError):
        transition_probabilities(graph, "a", "b", p=0, q=1)


def test_directed_transition_uses_reverse_adjacency():
    graph = nx.DiGraph([("a", "b"), ("b", "c"), ("b", "d"), ("c", "a")])
    nodes, probabilities = transition_probabilities(graph, "a", "b", p=1, q=2)
    assert nodes == ["c", "d"]
    assert probabilities == pytest.approx([2 / 3, 1 / 3])


def test_sinks_stop_and_do_not_create_reverse_edges():
    graph = nx.DiGraph([("City", "Admin"), ("City", "Country"), ("Admin", "Country")])
    config = replace(Config(), num_walks=2)
    first, _ = biased_walks(graph, config, 0.5, 2)
    second, _ = biased_walks(graph, config, 2, 0.5)
    assert first == second
    assert max(map(len, first)) <= 3
    assert all(graph.has_edge(a, b) for walk in first for a, b in zip(walk, walk[1:], strict=False))


def test_node2vec_alignment_and_determinism():
    graph = nx.cycle_graph(["d", "b", "c", "a"])
    config = replace(Config(), num_walks=2, walk_length=5, word2vec_epochs=2)
    first, _ = train_node2vec(graph, config, 1, 1)
    second, _ = train_node2vec(graph, config, 1, 1)
    assert first.shape == (4, 32)
    np.testing.assert_array_equal(first, second)


def test_shared_context_excludes_universal_country():
    graph = nx.Graph([("a", "Q183"), ("b", "Q183"), ("a", "admin")])
    assert shared_context(graph, "a", "b") == (0, 0)


def test_neighbors_exclude_query_and_filter_class():
    entities = pd.DataFrame(
        {"id": ["a", "b", "c"], "class": ["City", "City", "Country"], "label": ["A", "B", "C"]}
    ).set_index("id", drop=False)
    graph = nx.Graph([("a", "c"), ("b", "c")])
    result = nearest_neighbors(np.array([[1.0, 0.0], [0.8, 0.2], [1.0, 0.0]]), entities, graph, "a")
    assert result.neighbor.tolist() == ["b"]


def test_real_pykeen_training_preserves_mapping():
    entities = pd.DataFrame(
        {
            "id": ["a", "b", "c"],
            "class": ["City", "AdministrativeTerritory", "Country"],
            "label": ["A", "B", "C"],
        }
    ).set_index("id", drop=False)
    triples = np.array([["a", "P131", "b"], ["a", "P17", "c"], ["b", "P17", "c"]])
    config = replace(Config(), transe_epochs=2, batch_size=3)
    vectors, relations, factory, losses = train_transe(triples, entities, config)
    assert vectors.shape == (3, 32) and relations.shape == (2, 32)
    assert factory.entity_to_id == {"a": 0, "b": 1, "c": 2}
    assert factory.relation_to_id == {"P131": 0, "P17": 1}
    assert len(losses) == 2 and np.isfinite(losses).all()
