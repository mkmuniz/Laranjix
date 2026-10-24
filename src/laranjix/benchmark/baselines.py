"""Reference models the benchmark compares.

Three of them, and the comparison between them is the measurement:

* **rules** -- what a fraud analyst writes on day one. If these solve the
  dataset, the dataset is too easy and the typology needs rework.
* **tabular** -- gradient boosting on transaction-level features only.
* **tabular + graph** -- the same model, plus features that only exist because
  the transaction is an edge in a network.

The gap between the last two is what the graph structure is worth.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import polars as pl

from laranjix.benchmark.features import GRAPH_FEATURES, TABULAR_FEATURES


@dataclass(frozen=True)
class ModelScore:
    """How one model did on the held-out period, over repeated fits.

    A single fit is not reportable. With roughly two thousand frauds in a test
    period, PR-AUC moves a lot with the model's random seed -- one seed scored
    0.199 where its neighbours scored between 0.47 and 0.63. Every number here
    is therefore a mean over ``runs`` seeds, carrying its spread.
    """

    name: str
    average_precision: float
    average_precision_std: float
    recall_at_1pct_fpr: float
    recall_std: float
    features: int
    runs: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "average_precision": round(self.average_precision, 4),
            "average_precision_std": round(self.average_precision_std, 4),
            "recall_at_1pct_fpr": round(self.recall_at_1pct_fpr, 4),
            "recall_std": round(self.recall_std, 4),
            "features": self.features,
            "runs": self.runs,
        }


def rule_scores(frame: pl.DataFrame) -> np.ndarray:
    """Score by how many hand-written red flags a transaction trips."""
    flags = (
        (pl.col("pair_seen_before") == 0) & (pl.col("amount") >= 1_000),
        pl.col("dst_unique_senders_1h") >= 4,
        (pl.col("passthrough_ratio").is_between(0.80, 1.05))
        & (pl.col("seconds_since_src_inflow") < 1_800),
        (pl.col("dst_account_age_days") < 30) & (pl.col("amount") >= 500),
    )
    total = flags[0].cast(pl.Int8)
    for flag in flags[1:]:
        total = total + flag.cast(pl.Int8)
    scored = frame.select(total.alias("score"))
    return scored["score"].to_numpy().astype(float)


def recall_at_fpr(labels: np.ndarray, scores: np.ndarray, target_fpr: float = 0.01) -> float:
    """Recall at a fixed false-positive rate.

    This is the number an anti-fraud team actually lives with: alert volume is
    capped by how many analysts there are, so what matters is how much fraud you
    catch inside that budget.
    """
    negatives = scores[labels == 0]
    positives = scores[labels == 1]
    if negatives.size == 0 or positives.size == 0:
        return 0.0
    threshold = float(np.quantile(negatives, 1.0 - target_fpr))
    return float((positives > threshold).mean())


def train_and_score(
    name: str,
    feature_names: tuple[str, ...],
    train: pl.DataFrame,
    train_labels: np.ndarray,
    test: pl.DataFrame,
    test_labels: np.ndarray,
    seed: int = 0,
    runs: int = 5,
) -> ModelScore:
    """Fit gradient boosting ``runs`` times and report the mean and spread."""
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import average_precision_score

    train_x = train.select(feature_names).to_numpy()
    test_x = test.select(feature_names).to_numpy()

    precisions: list[float] = []
    recalls: list[float] = []
    for offset in range(runs):
        model = HistGradientBoostingClassifier(random_state=seed + offset, max_iter=200)
        model.fit(train_x, train_labels)
        scores = model.predict_proba(test_x)[:, 1]
        precisions.append(float(average_precision_score(test_labels, scores)))
        recalls.append(recall_at_fpr(test_labels, scores))

    return ModelScore(
        name=name,
        average_precision=float(np.mean(precisions)),
        average_precision_std=float(np.std(precisions)),
        recall_at_1pct_fpr=float(np.mean(recalls)),
        recall_std=float(np.std(recalls)),
        features=len(feature_names),
        runs=runs,
    )


def score_rules(test: pl.DataFrame, test_labels: np.ndarray) -> ModelScore:
    from sklearn.metrics import average_precision_score

    scores = rule_scores(test)
    return ModelScore(
        name="Regras simples",
        average_precision=float(average_precision_score(test_labels, scores)),
        average_precision_std=0.0,
        recall_at_1pct_fpr=recall_at_fpr(test_labels, scores),
        recall_std=0.0,
        features=4,
        runs=1,  # deterministic: no model is fitted
    )


ALL_FEATURES = TABULAR_FEATURES + GRAPH_FEATURES
