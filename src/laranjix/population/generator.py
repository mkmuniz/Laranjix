"""Orchestration of the population stage."""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

from laranjix.calibration.loader import Calibration, load_calibration
from laranjix.config import GenerationConfig
from laranjix.population.accounts import generate_accounts, institutions_table
from laranjix.population.partners import generate_company_partners
from laranjix.population.pix_keys import generate_pix_keys
from laranjix.rng import stage_rng


@dataclass(frozen=True)
class Population:
    """The tables produced by the population stage."""

    accounts: pl.DataFrame
    pix_keys: pl.DataFrame
    company_partners: pl.DataFrame
    institutions: pl.DataFrame

    def tables(self) -> dict[str, pl.DataFrame]:
        return {
            "accounts": self.accounts,
            "pix_keys": self.pix_keys,
            "company_partners": self.company_partners,
            "institutions": self.institutions,
        }

    def summary(self) -> dict[str, int]:
        counts = {name: frame.height for name, frame in self.tables().items()}
        by_type = dict(self.accounts.group_by("holder_type").agg(pl.len().alias("n")).iter_rows())
        for holder_type, total in by_type.items():
            counts[f"accounts_{holder_type}"] = int(total)
        return counts


def generate_population(
    config: GenerationConfig,
    calibration: Calibration | None = None,
) -> Population:
    """Run the population stage for ``config``.

    Each sub-stage uses its own seeded stream, so the accounts table is identical
    whether or not the later stages run.
    """
    params = calibration or load_calibration()
    accounts = generate_accounts(
        stage_rng(config.seed, "population.accounts"), config.population, params
    )
    pix_keys = generate_pix_keys(
        stage_rng(config.seed, "population.pix_keys"), accounts, config.population, params
    )
    partners = generate_company_partners(
        stage_rng(config.seed, "population.partners"), accounts, params
    )
    institution_count = accounts["institution_id"].n_unique()
    declared = config.population.institutions or int(
        params.data("accounts")["institutions"]["count"]
    )
    return Population(
        accounts=accounts,
        pix_keys=pix_keys,
        company_partners=partners,
        institutions=institutions_table(max(declared, institution_count)),
    )
