"""Guards against the generator going quadratic again.

Absolute throughput cannot be asserted: CI runners vary too much, and a test
that fails because the machine was busy teaches nothing. What can be asserted is
the *shape* of the cost curve. Quadrupling the population should roughly
quadruple the work; if some lookup starts rescanning the whole table per row
again, the ratio jumps and this fails.
"""

from __future__ import annotations

import time

from laranjix.calibration import load_calibration
from laranjix.config import GenerationConfig
from laranjix.population import generate_population

SMALL = 20_000
LARGE = 80_000
# Linear would be 4x. The slack absorbs noise and constant overheads; quadratic
# growth would land near 16x and cannot hide under this.
MAX_RATIO = 7.0


def _time_population(accounts: int) -> float:
    calibration = load_calibration()
    config = GenerationConfig(seed=1, population={"accounts": accounts})
    generate_population(config, calibration)  # warm the calibration cache

    start = time.perf_counter()
    generate_population(config, calibration)
    return time.perf_counter() - start


def test_population_cost_grows_about_linearly() -> None:
    small = _time_population(SMALL)
    large = _time_population(LARGE)
    ratio = large / max(small, 1e-6)
    assert ratio < MAX_RATIO, (
        f"gerar {LARGE:,} contas custou {ratio:.1f}x o de {SMALL:,}; "
        f"esperado perto de {LARGE / SMALL:.0f}x"
    )


def test_population_scales_to_a_large_run() -> None:
    """A size that the row-by-row generator could not reach in reasonable time."""
    calibration = load_calibration()
    population = generate_population(
        GenerationConfig(seed=2, population={"accounts": 200_000}), calibration
    )
    assert population.accounts.height == 200_000
    assert population.pix_keys.height > 200_000
