from __future__ import annotations

import pytest

from laranjix.calibration import load_calibration
from laranjix.config import GenerationConfig


@pytest.fixture(scope="session")
def calibration():
    return load_calibration()


@pytest.fixture()
def small_config() -> GenerationConfig:
    return GenerationConfig(seed=123, population={"accounts": 400})
