"""Deterministic random number generation.

Every stage draws from its own child stream, derived from the run seed and the
stage name. Adding a stage therefore never shifts the numbers drawn by the
existing ones, which keeps old seeds reproducible (``CONTRIBUTING.md``, section 6).
"""

from __future__ import annotations

import hashlib

import numpy as np


def stage_seed(seed: int, stage: str) -> int:
    """Return a stable 63-bit seed for ``stage`` under the run ``seed``."""
    digest = hashlib.sha256(f"{seed}:{stage}".encode()).digest()
    return int.from_bytes(digest[:8], "big") >> 1


def stage_rng(seed: int, stage: str) -> np.random.Generator:
    """Return the generator for one pipeline stage."""
    return np.random.default_rng(stage_seed(seed, stage))
