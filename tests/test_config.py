from __future__ import annotations

import pytest
from pydantic import ValidationError

from laranjix.config import GenerationConfig


def test_defaults_are_usable() -> None:
    config = GenerationConfig()
    assert config.seed == 0
    assert config.difficulty == "medium"
    assert config.population.accounts > 0


def test_unknown_difficulty_is_rejected() -> None:
    with pytest.raises(ValidationError):
        GenerationConfig(difficulty="impossivel")


def test_unknown_format_is_rejected() -> None:
    with pytest.raises(ValidationError):
        GenerationConfig(formats=("avro",))


def test_extra_keys_are_rejected() -> None:
    with pytest.raises(ValidationError):
        GenerationConfig(unexpected=1)


def test_yaml_roundtrip(tmp_path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("seed: 9\npopulation:\n  accounts: 50\n", encoding="utf-8")
    config = GenerationConfig.from_yaml(path)
    assert config.seed == 9
    assert config.population.accounts == 50


def test_to_dict_is_json_safe() -> None:
    payload = GenerationConfig(seed=3).to_dict()
    assert payload["population"]["reference_date"] == "2026-01-01"
    assert isinstance(payload["output_dir"], str)
