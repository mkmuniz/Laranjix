"""The fidelity machinery, including the bug it was built to catch."""

from __future__ import annotations

import numpy as np
import pytest

from laranjix.calibration.loader import normalise
from laranjix.config import GenerationConfig
from laranjix.population import generate_population
from laranjix.population.key_mix import realized_marginal, solve_draw_weights
from laranjix.validation.checks import population_fidelity
from laranjix.validation.fidelity import (
    check_distribution,
    sampling_noise_threshold,
    total_variation_distance,
)

UNIQUE = frozenset({"cpf", "cnpj", "email", "phone"})


def test_tvd_bounds() -> None:
    assert total_variation_distance({"a": 0.5, "b": 0.5}, {"a": 0.5, "b": 0.5}) == 0.0
    assert total_variation_distance({"a": 1.0}, {"b": 1.0}) == pytest.approx(1.0)


def test_noise_threshold_shrinks_with_the_square_root_of_the_sample() -> None:
    rng = np.random.default_rng(0)
    probabilities = [0.5, 0.3, 0.2]
    small = sampling_noise_threshold(probabilities, 1_000, rng)
    large = sampling_noise_threshold(probabilities, 100_000, rng)
    # Ten times the sample should cut the noise by roughly sqrt(10) per decade.
    assert small > large
    assert 7 < small / large < 14


def test_a_matching_distribution_passes_and_a_skewed_one_fails() -> None:
    rng = np.random.default_rng(1)
    target = {"a": 0.5, "b": 0.3, "c": 0.2}
    matching = check_distribution(
        "ok", "p", dict(target), target, 50_000, rng, provisional_target=False
    )
    assert matching.passed

    skewed = check_distribution(
        "ruim",
        "p",
        {"a": 0.70, "b": 0.20, "c": 0.10},
        target,
        50_000,
        rng,
        provisional_target=False,
    )
    assert not skewed.passed
    assert skewed.ratio > 10


# -- the solved key mix -------------------------------------------------------


def _counts(calibration) -> tuple[tuple[int, float], ...]:
    names, probabilities = normalise(
        {str(k): float(v) for k, v in calibration.data("pix_keys")["keys_per_account"].items()}
    )
    return tuple((int(name), p) for name, p in zip(names, probabilities, strict=True))


def test_drawing_straight_from_the_target_does_not_reproduce_it(calibration) -> None:
    # This is the bug the certificate found: an account holds at most one key of
    # each unique type, so drawing from the target over-represents EVP.
    mix = calibration.data("pix_keys")["key_type_mix_pf"]
    names, probabilities = normalise({str(k): float(v) for k, v in mix.items()})
    target = dict(zip(names, probabilities, strict=True))

    naive = realized_marginal(target, dict(_counts(calibration)), UNIQUE)
    assert total_variation_distance(naive, target) > 0.05


def test_solved_weights_reproduce_the_target_exactly(calibration) -> None:
    counts = _counts(calibration)
    for key in ("key_type_mix_pf", "key_type_mix_pj"):
        names, probabilities = normalise(
            {str(k): float(v) for k, v in calibration.data("pix_keys")[key].items()}
        )
        target = dict(zip(names, probabilities, strict=True))
        solved = dict(solve_draw_weights(tuple(sorted(target.items())), counts, UNIQUE))
        realized = realized_marginal(solved, dict(counts), UNIQUE)
        assert total_variation_distance(realized, target) < 1e-9


def test_the_solver_is_deterministic_and_uses_no_randomness(calibration) -> None:
    counts = _counts(calibration)
    names, probabilities = normalise(
        {str(k): float(v) for k, v in calibration.data("pix_keys")["key_type_mix_pf"].items()}
    )
    target = tuple(sorted(zip(names, probabilities, strict=True)))
    assert solve_draw_weights(target, counts, UNIQUE) == solve_draw_weights(target, counts, UNIQUE)


# -- end to end ---------------------------------------------------------------


def test_a_generated_population_passes_every_fidelity_check(calibration) -> None:
    population = generate_population(
        GenerationConfig(seed=42, population={"accounts": 30_000}), calibration
    )
    report = population_fidelity(population, calibration)
    assert report.checks
    failures = [check.name for check in report.checks if not check.passed]
    assert not failures, f"checagens falharam: {failures}"


def test_the_key_mix_check_would_catch_the_old_bug(calibration) -> None:
    # Guard against a regression: if key generation ever collapses collisions
    # into EVP again, this check must fail loudly.
    population = generate_population(
        GenerationConfig(seed=7, population={"accounts": 20_000}), calibration
    )
    broken = population.pix_keys.with_columns(
        key_type=population.pix_keys["key_type"].replace({"cpf": "evp", "phone": "evp"})
    )
    damaged = population.__class__(
        accounts=population.accounts,
        pix_keys=broken,
        company_partners=population.company_partners,
        institutions=population.institutions,
    )
    report = population_fidelity(damaged, calibration)
    assert not report.passed
