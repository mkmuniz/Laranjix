"""Distributional fidelity of a generated dataset against its calibration.

What this measures, precisely: whether the generator reproduces the parameters it
was given. It does **not** measure whether those parameters describe Brazil --
that is milestone 1's job, and parameters still marked provisional say so in the
certificate. The distinction matters: a dataset can score perfectly here and
still be unrealistic, so the certificate reports both numbers side by side.

The metric is the total variation distance (TVD) between the generated and the
target distribution: the largest probability difference over all categories, in
[0, 1]. A TVD is never zero on a finite sample, so each check is compared
against the TVD that pure sampling noise would produce at that sample size,
estimated by simulation. A check fails only when the deviation is larger than
sampling noise explains -- which is what a real generator bug looks like.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import polars as pl

from laranjix.calibration.loader import normalise

# How unlikely a pass-by-noise must be: the observed TVD is compared against the
# 99.9th percentile of the noise distribution.
NOISE_QUANTILE = 99.9
NOISE_TRIALS = 600


@dataclass(frozen=True)
class FidelityCheck:
    """One distribution compared against its calibration target."""

    name: str
    parameter_id: str
    sample_size: int
    tvd: float
    noise_threshold: float
    provisional_target: bool
    largest_gap: tuple[str, float, float]

    @property
    def passed(self) -> bool:
        return self.tvd <= self.noise_threshold

    @property
    def ratio(self) -> float:
        """Observed TVD as a multiple of what sampling noise explains."""
        if self.noise_threshold <= 0:
            return float("inf") if self.tvd > 0 else 0.0
        return self.tvd / self.noise_threshold

    def as_dict(self) -> dict[str, object]:
        category, observed, target = self.largest_gap
        return {
            "name": self.name,
            "parameter_id": self.parameter_id,
            "sample_size": self.sample_size,
            "tvd": round(self.tvd, 6),
            "noise_threshold": round(self.noise_threshold, 6),
            "ratio_to_noise": round(self.ratio, 3),
            "passed": self.passed,
            "provisional_target": self.provisional_target,
            "largest_gap": {
                "category": category,
                "observed": round(observed, 6),
                "target": round(target, 6),
            },
        }


@dataclass(frozen=True)
class FidelityReport:
    """Every fidelity check for one dataset."""

    checks: list[FidelityCheck] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def worst(self) -> FidelityCheck | None:
        return max(self.checks, key=lambda check: check.ratio, default=None)

    def as_dict(self) -> dict[str, object]:
        worst = self.worst
        return {
            "passed": self.passed,
            "checks": [check.as_dict() for check in self.checks],
            "worst_check": worst.name if worst else None,
            "worst_ratio_to_noise": round(worst.ratio, 3) if worst else None,
            "targets_provisional": sorted(
                {check.parameter_id for check in self.checks if check.provisional_target}
            ),
        }


def total_variation_distance(observed: dict[str, float], target: dict[str, float]) -> float:
    """Return the TVD between two distributions over the union of their keys."""
    categories = set(observed) | set(target)
    return 0.5 * sum(abs(observed.get(key, 0.0) - target.get(key, 0.0)) for key in categories)


def sampling_noise_threshold(
    probabilities: list[float],
    sample_size: int,
    rng: np.random.Generator,
    trials: int = NOISE_TRIALS,
    quantile: float = NOISE_QUANTILE,
) -> float:
    """Return the TVD that sampling alone produces at this size, at ``quantile``.

    Drawing ``sample_size`` items from the target distribution never reproduces it
    exactly. This simulates that noise so a check can tell a real deviation from
    an unavoidable one.
    """
    if sample_size <= 0:
        return 0.0
    draws = rng.multinomial(sample_size, probabilities, size=trials) / sample_size
    distances = 0.5 * np.abs(draws - np.asarray(probabilities)).sum(axis=1)
    return float(np.percentile(distances, quantile))


def _observed_shares(frame: pl.DataFrame, column: str) -> dict[str, float]:
    counts = frame.group_by(column).agg(pl.len().alias("n"))
    total = float(frame.height)
    return {str(key): int(value) / total for key, value in counts.iter_rows()}


def check_distribution(
    name: str,
    parameter_id: str,
    observed: dict[str, float],
    target_weights: dict[str, float],
    sample_size: int,
    rng: np.random.Generator,
    provisional_target: bool,
) -> FidelityCheck:
    """Compare one observed distribution against its calibration target."""
    categories, probabilities = normalise(target_weights)
    target = dict(zip(categories, probabilities, strict=True))
    tvd = total_variation_distance(observed, target)
    threshold = sampling_noise_threshold(probabilities, sample_size, rng)

    gap_category = max(
        set(observed) | set(target),
        key=lambda key: abs(observed.get(key, 0.0) - target.get(key, 0.0)),
    )
    return FidelityCheck(
        name=name,
        parameter_id=parameter_id,
        sample_size=sample_size,
        tvd=tvd,
        noise_threshold=threshold,
        provisional_target=provisional_target,
        largest_gap=(
            gap_category,
            observed.get(gap_category, 0.0),
            target.get(gap_category, 0.0),
        ),
    )
