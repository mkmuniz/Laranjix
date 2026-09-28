"""The circle of regular counterparties each account transacts with.

Without this, every payment would land on a random stranger and "first time these
two accounts ever transacted" would carry no information -- which would make the
fraud typologies trivially separable, since that signal is exactly what the
social-engineering pattern trips. The graph is built with preferential
attachment so a few accounts act as hubs, the way shops and employers do.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class CounterpartyGraph:
    """Ragged adjacency: ``neighbours[offsets[i]:offsets[i + 1]]`` for account ``i``."""

    neighbours: np.ndarray
    offsets: np.ndarray

    @property
    def sizes(self) -> np.ndarray:
        return np.diff(self.offsets)

    def pick(self, senders: np.ndarray, draws: np.ndarray) -> np.ndarray:
        """Vectorised choice of one regular counterparty per sender."""
        sizes = self.sizes[senders]
        positions = self.offsets[senders] + (draws * sizes).astype(np.int64)
        result: np.ndarray = self.neighbours[positions]
        return result


def build_counterparty_graph(
    rng: np.random.Generator,
    account_count: int,
    regular_min: int,
    regular_max: int,
    preferential_attachment: float,
) -> CounterpartyGraph:
    """Return each account's circle of regular counterparties."""
    if account_count < 2:
        return CounterpartyGraph(
            neighbours=np.zeros(0, dtype=np.int64), offsets=np.zeros(2, dtype=np.int64)
        )

    # Popularity follows a heavy tail, so hubs emerge instead of a uniform mesh.
    popularity = rng.pareto(1.0 / max(preferential_attachment, 1e-6), size=account_count) + 1.0
    probabilities = popularity / popularity.sum()

    sizes = rng.integers(regular_min, regular_max + 1, size=account_count)
    sizes = np.minimum(sizes, account_count - 1)
    offsets = np.zeros(account_count + 1, dtype=np.int64)
    np.cumsum(sizes, out=offsets[1:])

    total = int(offsets[-1])
    neighbours = rng.choice(account_count, size=total, p=probabilities)

    # An account must not be its own counterparty; shift the collisions.
    owners = np.repeat(np.arange(account_count), sizes)
    collisions = neighbours == owners
    neighbours[collisions] = (neighbours[collisions] + 1) % account_count
    return CounterpartyGraph(neighbours=neighbours.astype(np.int64), offsets=offsets)
