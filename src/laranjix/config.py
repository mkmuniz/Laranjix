"""Typed, YAML-backed configuration for every generation run."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

DIFFICULTIES = ("easy", "medium", "hard")


class DifficultySettings(BaseModel):
    """How well hidden the planted fraud is.

    These are not calibration: no public statistic says how obvious a fraud
    should look. They are the knobs that let a benchmark have a floor and a
    ceiling, so a dataset can be *shown* to be hard rather than asserted to be.
    """

    model_config = ConfigDict(extra="forbid")

    mule_history_fraction: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Share of mule accounts recruited among accounts with ordinary history.",
    )
    hop_minutes_min: float = Field(default=2.0, gt=0)
    hop_minutes_max: float = Field(default=30.0, gt=0)
    amount_from_history: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Share of victim amounts drawn from the victim's own usual range.",
    )
    retained_fraction_min: float = Field(default=0.85, gt=0, le=1)
    retained_fraction_max: float = Field(default=0.97, gt=0, le=1)
    decoy_cases: int = Field(
        default=40,
        ge=0,
        description="Legitimate accounts made to look like mules, as realistic false positives.",
    )


DIFFICULTY_PRESETS: dict[str, DifficultySettings] = {
    "easy": DifficultySettings(
        mule_history_fraction=0.0,
        hop_minutes_min=1.0,
        hop_minutes_max=4.0,
        amount_from_history=0.0,
        retained_fraction_min=0.97,
        retained_fraction_max=1.0,
        decoy_cases=0,
    ),
    # Tuned so the three levels actually form a ladder for the strongest model,
    # not just for the rules: with the library defaults, medium scored the same
    # as easy for the graph model, which makes the middle rung useless.
    "medium": DifficultySettings(
        mule_history_fraction=0.75,
        hop_minutes_min=3.0,
        hop_minutes_max=75.0,
        amount_from_history=0.80,
        retained_fraction_min=0.78,
        retained_fraction_max=0.98,
        decoy_cases=120,
    ),
    "hard": DifficultySettings(
        mule_history_fraction=0.95,
        hop_minutes_min=5.0,
        hop_minutes_max=180.0,
        amount_from_history=0.95,
        retained_fraction_min=0.70,
        retained_fraction_max=0.99,
        decoy_cases=220,
    ),
}


class PopulationConfig(BaseModel):
    """How many fictitious accounts to create, and with which shape."""

    model_config = ConfigDict(extra="forbid")

    accounts: int = Field(default=10_000, ge=1, description="Total number of accounts.")
    institutions: int | None = Field(
        default=None, ge=1, description="Override the institution count from calibration."
    )
    reference_date: date = Field(
        default=date(2026, 1, 1),
        description="Date the account ages are measured against.",
    )
    max_keys_per_account: int = Field(default=5, ge=1, le=20)


class FraudConfig(BaseModel):
    """How many cases of each typology to plant."""

    model_config = ConfigDict(extra="forbid")

    mule_chain_cases: int = Field(default=120, ge=0, description="T1: cadeias de contas laranja.")
    social_engineering_cases: int = Field(
        default=90, ge=0, description="T2: golpes de engenharia social."
    )
    chain_depth_min: int = Field(default=2, ge=1)
    chain_depth_max: int = Field(default=6, ge=1)
    victims_per_case_min: int = Field(default=4, ge=1)
    victims_per_case_max: int = Field(default=28, ge=1)


class GenerationConfig(BaseModel):
    """Top-level configuration. Same config + same seed = same dataset."""

    model_config = ConfigDict(extra="forbid")

    seed: int = Field(default=0, ge=0, description="Deterministic seed for the whole run.")
    difficulty: str = Field(default="medium")
    population: PopulationConfig = Field(default_factory=PopulationConfig)
    fraud: FraudConfig = Field(default_factory=FraudConfig)
    output_dir: Path = Field(default=Path("out"))
    formats: tuple[str, ...] = Field(default=("parquet", "csv"))

    @field_validator("difficulty")
    @classmethod
    def _known_difficulty(cls, value: str) -> str:
        if value not in DIFFICULTIES:
            raise ValueError(f"difficulty must be one of {DIFFICULTIES}, got {value!r}")
        return value

    @field_validator("formats")
    @classmethod
    def _known_formats(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        allowed = {"parquet", "csv"}
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise ValueError(f"unknown output formats: {unknown}")
        if not value:
            raise ValueError("at least one output format is required")
        return value

    @property
    def difficulty_settings(self) -> DifficultySettings:
        """The camouflage settings for this run's difficulty level."""
        return DIFFICULTY_PRESETS[self.difficulty]

    @classmethod
    def from_yaml(cls, path: Path) -> GenerationConfig:
        payload: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return cls.model_validate(payload)

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe dump, embedded verbatim in the dataset manifest."""
        return self.model_dump(mode="json")
