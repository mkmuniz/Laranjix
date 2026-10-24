"""Assembling a complete dataset: population, activity, planted fraud and labels."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import polars as pl

from laranjix.behavior.transactions import TRANSACTION_SCHEMA, generate_normal_transactions
from laranjix.calibration.loader import Calibration, load_calibration
from laranjix.camouflage.decoys import build_decoys
from laranjix.config import GenerationConfig
from laranjix.labels import build_account_labels, build_cases_table, build_transaction_labels
from laranjix.population import Population, generate_population
from laranjix.rng import stage_rng
from laranjix.typologies import t1_mule_chain, t2_social_engineering
from laranjix.typologies.base import Case, InjectionContext, PlantedTransaction

TYPOLOGIES = (t1_mule_chain, t2_social_engineering)


@dataclass(frozen=True)
class Dataset:
    """A complete dataset: data tables and, separately, the ground truth."""

    population: Population
    transactions: pl.DataFrame
    labels_transactions: pl.DataFrame
    labels_accounts: pl.DataFrame
    cases: pl.DataFrame

    def data_tables(self) -> dict[str, pl.DataFrame]:
        """Tables a model is allowed to see."""
        tables = dict(self.population.tables())
        tables["transactions"] = self.transactions
        return tables

    def label_tables(self) -> dict[str, pl.DataFrame]:
        """Ground truth, written to separate files to avoid label leakage."""
        return {
            "labels_transactions": self.labels_transactions,
            "labels_accounts": self.labels_accounts,
            "cases": self.cases,
        }

    def tables(self) -> dict[str, pl.DataFrame]:
        return {**self.data_tables(), **self.label_tables()}

    def summary(self) -> dict[str, int]:
        counts = self.population.summary()
        counts["transactions"] = self.transactions.height
        counts["cases"] = self.cases.height
        counts["fraud_transactions"] = int(self.labels_transactions["is_fraud"].sum())
        return counts

    @property
    def fraud_rate(self) -> float:
        if not self.transactions.height:
            return 0.0
        mean = self.labels_transactions["is_fraud"].mean()
        return float(mean) if isinstance(mean, int | float) else 0.0


def _planted_frame(planted: list[PlantedTransaction]) -> pl.DataFrame:
    schema: dict[str, Any] = {
        **TRANSACTION_SCHEMA,
        "case_id": pl.Utf8,
        "typology": pl.Utf8,
        "role": pl.Utf8,
    }
    if not planted:
        return pl.DataFrame(schema=schema)

    # A list of numpy scalars arrives as objects; build the column as an array.
    timestamps = np.array([item.timestamp for item in planted], dtype="datetime64[us]")
    hours = timestamps.astype("datetime64[h]").astype(np.int64) % 24
    return pl.DataFrame(
        {
            "tx_id": [""] * len(planted),
            "src_account_id": [item.src_account_id for item in planted],
            "dst_account_id": [item.dst_account_id for item in planted],
            "channel": [item.channel for item in planted],
            "amount": [item.amount for item in planted],
            "timestamp": timestamps,
            "is_night": (hours >= 20) | (hours < 6),
            "device_id": [item.device_id for item in planted],
            "case_id": [item.case_id for item in planted],
            "typology": [item.typology for item in planted],
            "role": [item.role for item in planted],
        },
        schema=schema,
    )


def generate_dataset(
    config: GenerationConfig,
    calibration: Calibration | None = None,
) -> Dataset:
    """Generate a complete dataset for ``config``."""
    params = calibration or load_calibration()
    population = generate_population(config, params)

    activity = generate_normal_transactions(
        stage_rng(config.seed, "behavior.transactions"),
        population.accounts,
        params,
        config.population.reference_date,
    )
    normal = activity.transactions.with_columns(
        case_id=pl.lit(""), typology=pl.lit(""), role=pl.lit("")
    )

    def context_for(stage: str) -> InjectionContext:
        return InjectionContext(
            rng=stage_rng(config.seed, stage),
            accounts=population.accounts,
            normal=activity.transactions,
            calibration=params,
            difficulty=config.difficulty_settings,
            difficulty_name=config.difficulty,
            fraud=config.fraud,
            reference_date=config.population.reference_date,
        )

    frames = [normal]
    cases: list[Case] = []
    for module in TYPOLOGIES:
        result = module.inject(context_for(f"typology.{module.CODE}"))
        cases.extend(result.cases)
        frames.append(_planted_frame(result.transactions))

    frames.append(_planted_frame(build_decoys(context_for("camouflage.decoys"))))

    combined = pl.concat(frames, how="vertical").sort("timestamp", maintain_order=True)
    combined = combined.with_columns(
        tx_id=pl.Series(
            "tx_id", [f"tx_{index:09d}" for index in range(1, combined.height + 1)], dtype=pl.Utf8
        )
    )

    labels = build_transaction_labels(combined, stage_rng(config.seed, "labels.delay"))
    return Dataset(
        population=population,
        transactions=combined.drop("case_id", "typology", "role"),
        labels_transactions=labels,
        labels_accounts=build_account_labels(cases),
        cases=build_cases_table(cases),
    )
