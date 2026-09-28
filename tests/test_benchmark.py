"""The benchmark has to be able to fail the dataset, not just flatter it."""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from laranjix.benchmark.baselines import recall_at_fpr, rule_scores
from laranjix.benchmark.features import GRAPH_FEATURES, TABULAR_FEATURES, build_features
from laranjix.benchmark.runner import render_table, run_benchmark
from laranjix.config import GenerationConfig
from laranjix.dataset import generate_dataset


@pytest.fixture(scope="module")
def hard_dataset():
    return generate_dataset(
        GenerationConfig(seed=4, difficulty="hard", population={"accounts": 5_000})
    )


@pytest.fixture(scope="module")
def easy_dataset():
    return generate_dataset(
        GenerationConfig(seed=4, difficulty="easy", population={"accounts": 5_000})
    )


def test_features_are_complete_and_aligned(hard_dataset) -> None:
    features = build_features(hard_dataset.transactions, hard_dataset.population.accounts)
    assert features.height == hard_dataset.transactions.height
    for column in TABULAR_FEATURES + GRAPH_FEATURES:
        assert column in features.columns
        assert features[column].null_count() == 0, f"{column} tem nulos"


def test_graph_features_separate_fraud_from_ordinary_activity(hard_dataset) -> None:
    features = build_features(hard_dataset.transactions, hard_dataset.population.accounts)
    joined = features.join(hard_dataset.labels_transactions.select("tx_id", "is_fraud"), on="tx_id")
    fraud = joined.filter(pl.col("is_fraud"))
    ordinary = joined.filter(~pl.col("is_fraud"))

    # Money passing straight through, and pairs that never transacted before.
    assert fraud["passthrough_ratio"].median() > ordinary["passthrough_ratio"].median()
    assert fraud["pair_seen_before"].median() < ordinary["pair_seen_before"].median()


def test_recall_at_fpr_is_bounded_and_ordered() -> None:
    labels = np.array([0] * 990 + [1] * 10)
    perfect = np.concatenate([np.zeros(990), np.ones(10)])
    useless = np.zeros(1000)
    assert recall_at_fpr(labels, perfect) == 1.0
    assert recall_at_fpr(labels, useless) == 0.0


def test_rules_produce_a_score_per_transaction(hard_dataset) -> None:
    features = build_features(hard_dataset.transactions, hard_dataset.population.accounts)
    scores = rule_scores(features)
    assert scores.shape == (features.height,)
    assert np.isfinite(scores).all()
    assert scores.max() <= 4


def test_simple_rules_collapse_when_the_dataset_is_hard(easy_dataset, hard_dataset) -> None:
    """The quality criterion from the scope document, section 7.2.

    If hand-written rules still solve the dataset at the hard level, the dataset
    is too easy and the typology needs rework. This test is the guard.
    """
    easy = run_benchmark(easy_dataset).by_name("Regras simples")
    hard = run_benchmark(hard_dataset).by_name("Regras simples")
    assert easy is not None and hard is not None
    assert easy.average_precision > hard.average_precision
    assert hard.average_precision < 0.05, "as regras ainda resolvem o nivel hard"


def test_graph_features_beat_the_tabular_model(hard_dataset) -> None:
    result = run_benchmark(hard_dataset)
    tabular = result.by_name("Tabular (sem grafo)")
    graph = result.by_name("Tabular + grafo")
    assert tabular is not None and graph is not None
    assert graph.average_precision > tabular.average_precision
    assert graph.features > tabular.features


def test_training_labels_respect_the_reporting_delay(hard_dataset) -> None:
    result = run_benchmark(hard_dataset)
    # Some frauds in the training period had not been contested by the cutoff,
    # so the model trains on them as ordinary transactions -- as in production.
    assert result.labels_unknown_at_train_time > 0
    assert result.train_rows > result.test_rows


def test_table_renders_every_model(hard_dataset) -> None:
    table = render_table([run_benchmark(hard_dataset)])
    assert "PR-AUC" in table
    assert "Regras simples" in table
    assert "Tabular + grafo" in table
