"""Running the benchmark over a generated dataset."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import polars as pl

from laranjix.benchmark.baselines import (
    ALL_FEATURES,
    ModelScore,
    score_rules,
    train_and_score,
)
from laranjix.benchmark.features import TABULAR_FEATURES, build_features
from laranjix.dataset import Dataset

TRAIN_FRACTION = 0.7


@dataclass(frozen=True)
class BenchmarkResult:
    """The benchmark for one dataset at one difficulty."""

    difficulty: str
    transactions: int
    fraud_transactions: int
    fraud_rate: float
    train_rows: int
    test_rows: int
    labels_unknown_at_train_time: int
    scores: list[ModelScore]

    def as_dict(self) -> dict[str, Any]:
        return {
            "difficulty": self.difficulty,
            "transactions": self.transactions,
            "fraud_transactions": self.fraud_transactions,
            "fraud_rate": round(self.fraud_rate, 6),
            "train_rows": self.train_rows,
            "test_rows": self.test_rows,
            "labels_unknown_at_train_time": self.labels_unknown_at_train_time,
            "scores": [score.as_dict() for score in self.scores],
        }

    def by_name(self, name: str) -> ModelScore | None:
        return next((score for score in self.scores if score.name == name), None)


def run_benchmark(dataset: Dataset, seed: int = 0, runs: int = 5) -> BenchmarkResult:
    """Train the reference models on the past and score them on the future.

    The split is temporal, and a fraud is only labelled in training if the victim
    had already contested it by the cutoff. Frauds still unreported at that point
    are trained on as ordinary transactions -- which is the situation a real team
    is in, and which a benchmark that hands over labels instantly hides.
    """
    features = build_features(dataset.transactions, dataset.population.accounts)
    frame = features.join(
        dataset.labels_transactions.select("tx_id", "is_fraud", "label_available_at"),
        on="tx_id",
        how="left",
    ).sort("timestamp")

    cutoff = frame["timestamp"].quantile(TRAIN_FRACTION, interpolation="nearest")
    train = frame.filter(pl.col("timestamp") < cutoff)
    test = frame.filter(pl.col("timestamp") >= cutoff)

    known = train["label_available_at"] < cutoff
    train_labels = (train["is_fraud"] & known).to_numpy().astype(int)
    test_labels = test["is_fraud"].to_numpy().astype(int)
    unknown = int((train["is_fraud"] & ~known).sum())

    scores: list[ModelScore] = [score_rules(test, test_labels)]
    if train_labels.sum() > 0 and test_labels.sum() > 0:
        scores.append(
            train_and_score(
                "Tabular (sem grafo)",
                TABULAR_FEATURES,
                train,
                train_labels,
                test,
                test_labels,
                seed,
            )
        )
        scores.append(
            train_and_score(
                "Tabular + grafo",
                ALL_FEATURES,
                train,
                train_labels,
                test,
                test_labels,
                seed,
                runs,
            )
        )

    return BenchmarkResult(
        difficulty=dataset.cases["difficulty"][0] if dataset.cases.height else "n/a",
        transactions=frame.height,
        fraud_transactions=int(frame["is_fraud"].sum()),
        fraud_rate=_as_float(frame["is_fraud"].mean()),
        train_rows=train.height,
        test_rows=test.height,
        labels_unknown_at_train_time=unknown,
        scores=scores,
    )


def render_table(results: list[BenchmarkResult]) -> str:
    """Render the benchmark as the Markdown table the README carries."""
    lines = [
        "| Dificuldade | Modelo | PR-AUC | Recall @ 1% FPR |",
        "|---|---|---:|---:|",
    ]
    for result in results:
        for index, score in enumerate(result.scores):
            label = result.difficulty if index == 0 else ""
            if score.runs > 1:
                precision = f"{score.average_precision:.4f} ± {score.average_precision_std:.4f}"
                recall = f"{score.recall_at_1pct_fpr:.3f} ± {score.recall_std:.3f}"
            else:
                precision = f"{score.average_precision:.4f}"
                recall = f"{score.recall_at_1pct_fpr:.3f}"
            lines.append(f"| {label} | {score.name} | {precision} | {recall} |")
    return "\n".join(lines)


def _as_float(value: object) -> float:
    """Polars aggregations are typed as a wide union; narrow it here."""
    return float(value) if isinstance(value, int | float) else 0.0
