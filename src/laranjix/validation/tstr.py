"""Train-on-Synthetic, Test-on-Real (TSTR).

TSTR is the protocol that answers the only question that really matters about a
synthetic dataset: does a model trained on it work on real data? A model is
trained on the synthetic set and scored on a real holdout, and the score is
compared against the same model trained on real data (TRTR). The ratio
TSTR/TRTR is the utility number.

The point for Laranjix is the direction data flows. The real holdout stays on the
machine of whoever owns it and is passed to this function in memory; nothing
about it is written to the dataset, the certificate or the repository. Only the
score crosses the boundary. That is what lets the project keep its promise --
no real data, ever -- while still measuring utility against reality.

Fraud is rare, so the metric is average precision (area under the
precision-recall curve), not ROC-AUC, which flatters a model on imbalanced data.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol


class TstrStatus(StrEnum):
    """Why a TSTR run produced, or did not produce, a number."""

    OK = "ok"
    PENDING_LABELS = "pending_labels"
    MISSING_REFERENCE = "missing_reference"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class TstrResult:
    """The outcome of one TSTR evaluation."""

    status: TstrStatus
    detail: str
    tstr_average_precision: float | None = None
    trtr_average_precision: float | None = None
    baseline_average_precision: float | None = None
    model: str | None = None

    @property
    def utility_ratio(self) -> float | None:
        """TSTR divided by TRTR: 1.0 means synthetic trains as well as real."""
        if self.tstr_average_precision is None or not self.trtr_average_precision:
            return None
        return self.tstr_average_precision / self.trtr_average_precision

    def as_dict(self) -> dict[str, Any]:
        ratio = self.utility_ratio
        return {
            "status": self.status.value,
            "detail": self.detail,
            "model": self.model,
            "tstr_average_precision": _round(self.tstr_average_precision),
            "trtr_average_precision": _round(self.trtr_average_precision),
            "baseline_average_precision": _round(self.baseline_average_precision),
            "utility_ratio": _round(ratio),
        }


def _round(value: float | None) -> float | None:
    return None if value is None else round(float(value), 4)


class LabelledFrame(Protocol):
    """Minimal shape a dataset must have to take part in TSTR."""

    def to_numpy(self) -> Any: ...


def run_tstr(
    synthetic_features: Any,
    synthetic_labels: Any,
    real_features: Any,
    real_labels: Any,
    model_name: str = "gradient_boosting",
    seed: int = 0,
) -> TstrResult:
    """Train on the synthetic set, score on the real holdout.

    ``real_features``/``real_labels`` never leave the caller's process: they are
    consumed here and only the resulting scores are returned.
    """
    try:
        import numpy as np
        from sklearn.dummy import DummyClassifier
        from sklearn.ensemble import HistGradientBoostingClassifier
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import average_precision_score
    except ImportError:  # pragma: no cover - exercised only without the extra
        return TstrResult(
            status=TstrStatus.UNAVAILABLE,
            detail="scikit-learn nao instalado; use: pip install 'laranjix[bench]'",
        )

    def build() -> Any:
        if model_name == "logistic_regression":
            return LogisticRegression(max_iter=1000)
        return HistGradientBoostingClassifier(random_state=seed)

    synthetic_y = np.asarray(synthetic_labels).astype(int).ravel()
    real_y = np.asarray(real_labels).astype(int).ravel()
    if len(np.unique(synthetic_y)) < 2 or len(np.unique(real_y)) < 2:
        return TstrResult(
            status=TstrStatus.PENDING_LABELS,
            detail="e preciso ter as duas classes nos rotulos de treino e de teste",
        )

    synthetic_x = np.asarray(synthetic_features, dtype=float)
    real_x = np.asarray(real_features, dtype=float)
    if synthetic_x.shape[1] != real_x.shape[1]:
        return TstrResult(
            status=TstrStatus.MISSING_REFERENCE,
            detail=(
                f"as features nao batem: sintetico tem {synthetic_x.shape[1]} colunas, "
                f"real tem {real_x.shape[1]}"
            ),
        )

    trained_on_synthetic = build().fit(synthetic_x, synthetic_y)
    tstr = average_precision_score(real_y, trained_on_synthetic.predict_proba(real_x)[:, 1])

    trained_on_real = build().fit(real_x, real_y)
    trtr = average_precision_score(real_y, trained_on_real.predict_proba(real_x)[:, 1])

    dummy = DummyClassifier(strategy="prior").fit(real_x, real_y)
    baseline = average_precision_score(real_y, dummy.predict_proba(real_x)[:, 1])

    return TstrResult(
        status=TstrStatus.OK,
        detail="treinado no sintetico, avaliado no real",
        tstr_average_precision=float(tstr),
        trtr_average_precision=float(trtr),
        baseline_average_precision=float(baseline),
        model=model_name,
    )


def tstr_not_applicable(reason: str) -> TstrResult:
    """Return a result explaining why TSTR could not run for this dataset."""
    return TstrResult(status=TstrStatus.PENDING_LABELS, detail=reason)
