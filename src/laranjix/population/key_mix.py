"""Solving the per-draw weights that make the Pix key mix match calibration.

The calibration target is a *realized* mix: the share of each key type across all
keys, as the Banco Central publishes it. But keys are drawn per account under a
constraint -- an account holds at most one key of each document or contact type,
and only EVP repeats. Drawing straight from the target and pushing every
collision into EVP inflates EVP badly: 42.7% against a 31% target for PF, 18.6
times what sampling noise explains.

So the target is not the right thing to draw from. This module solves for the
per-draw weights whose *outcome* is the target, by iterating

    w <- w * target / realized(w)

where ``realized`` is computed exactly, by dynamic programming over which unique
types an account has already used. No Monte Carlo: the solution depends only on
the calibration numbers, so it is identical on every machine and every NumPy
version, which is what reproducibility across releases requires.
"""

from __future__ import annotations

from functools import lru_cache

SOLVER_ITERATIONS = 400
SOLVER_TOLERANCE = 1e-12


def realized_marginal(
    weights: dict[str, float],
    count_probabilities: dict[int, float],
    unique_types: frozenset[str],
) -> dict[str, float]:
    """Return the key-type mix that drawing with ``weights`` actually produces.

    Exact, not simulated: the state is the set of unique types an account has
    already used, which is small enough to enumerate.
    """
    types = list(weights)
    expected: dict[str, float] = dict.fromkeys(types, 0.0)
    expected_keys = 0.0

    for count, count_probability in count_probabilities.items():
        if count_probability <= 0 or count <= 0:
            continue
        expected_keys += count_probability * count
        states: dict[frozenset[str], float] = {frozenset(): 1.0}
        for _ in range(count):
            next_states: dict[frozenset[str], float] = {}
            for used, state_probability in states.items():
                allowed = [t for t in types if not (t in unique_types and t in used)]
                total = sum(weights[t] for t in allowed)
                if total <= 0:
                    continue
                for chosen in allowed:
                    probability = state_probability * weights[chosen] / total
                    expected[chosen] += count_probability * probability
                    successor = used | {chosen} if chosen in unique_types else used
                    next_states[successor] = next_states.get(successor, 0.0) + probability
            states = next_states

    if expected_keys <= 0:
        return dict.fromkeys(types, 0.0)
    return {key: value / expected_keys for key, value in expected.items()}


def _solve(
    target: tuple[tuple[str, float], ...],
    counts: tuple[tuple[int, float], ...],
    unique_types: frozenset[str],
) -> dict[str, float]:
    target_mix = dict(target)
    count_probabilities = dict(counts)
    weights = dict(target_mix)

    for _ in range(SOLVER_ITERATIONS):
        realized = realized_marginal(weights, count_probabilities, unique_types)
        shift = 0.0
        for key in weights:
            if realized[key] <= 0:
                continue
            updated = weights[key] * target_mix[key] / realized[key]
            shift = max(shift, abs(updated - weights[key]))
            weights[key] = updated
        total = sum(weights.values())
        weights = {key: value / total for key, value in weights.items()}
        if shift < SOLVER_TOLERANCE:
            break
    return weights


@lru_cache(maxsize=32)
def solve_draw_weights(
    target: tuple[tuple[str, float], ...],
    counts: tuple[tuple[int, float], ...],
    unique_types: frozenset[str],
) -> tuple[tuple[str, float], ...]:
    """Return draw weights whose realized mix equals ``target``.

    Arguments are tuples so the solution can be cached; it depends only on the
    calibration numbers.
    """
    return tuple(sorted(_solve(target, counts, unique_types).items()))
