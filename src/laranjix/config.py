"""Typed, YAML-backed configuration for every generation run."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

DIFFICULTIES = ("easy", "medium", "hard")


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


class GenerationConfig(BaseModel):
    """Top-level configuration. Same config + same seed = same dataset."""

    model_config = ConfigDict(extra="forbid")

    seed: int = Field(default=0, ge=0, description="Deterministic seed for the whole run.")
    difficulty: str = Field(default="medium")
    population: PopulationConfig = Field(default_factory=PopulationConfig)
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

    @classmethod
    def from_yaml(cls, path: Path) -> GenerationConfig:
        payload: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return cls.model_validate(payload)

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe dump, embedded verbatim in the dataset manifest."""
        return self.model_dump(mode="json")
