"""Ownership edges between individuals and companies (feeds typology T4)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import numpy as np
import polars as pl

from laranjix.calibration.loader import Calibration, normalise

PARTNER_SCHEMA: dict[str, Any] = {
    "partner_account_id": pl.Utf8,
    "company_account_id": pl.Utf8,
    "since": pl.Date,
}


def generate_company_partners(
    rng: np.random.Generator,
    accounts: pl.DataFrame,
    calibration: Calibration,
) -> pl.DataFrame:
    """Return the ``company_partners`` table.

    A MEI always has exactly one owner. Other companies draw their partner count
    from calibration, and partners are sampled from the existing PF accounts --
    which is what creates the shared-ownership subgraphs typology T4 looks for.
    """
    params = calibration.data("accounts")["company"]
    counts, probabilities = normalise(
        {str(k): float(v) for k, v in params["partners_per_company"].items()}
    )
    partner_counts = [int(value) for value in counts]

    individuals = accounts.filter(pl.col("holder_type") == "PF")["account_id"].to_list()
    companies = accounts.filter(pl.col("holder_type").is_in(["PJ", "MEI"])).select(
        "account_id", "holder_type", "created_at"
    )

    rows: dict[str, list[Any]] = {name: [] for name in PARTNER_SCHEMA}
    if not individuals or companies.height == 0:
        return pl.DataFrame(rows, schema=PARTNER_SCHEMA)

    for company_id, holder_type, created_at in companies.iter_rows():
        wanted = 1 if holder_type == "MEI" else int(rng.choice(partner_counts, p=probabilities))
        wanted = min(wanted, len(individuals))
        chosen = rng.choice(len(individuals), size=wanted, replace=False)
        for position in chosen:
            # Partners may predate the company by up to a year.
            offset = int(rng.integers(0, 366))
            rows["partner_account_id"].append(individuals[int(position)])
            rows["company_account_id"].append(company_id)
            rows["since"].append(created_at + timedelta(days=offset))

    return pl.DataFrame(rows, schema=PARTNER_SCHEMA)


def shared_partner_pairs(partners: pl.DataFrame) -> pl.DataFrame:
    """Return company pairs that share at least one partner.

    Not used by milestone 2 itself; it is the seed of the T4 signature and a cheap
    way to check that the ownership graph is connected enough to be interesting.
    """
    left = partners.select("partner_account_id", company_a="company_account_id")
    right = partners.select("partner_account_id", company_b="company_account_id")
    return (
        left.join(right, on="partner_account_id")
        .filter(pl.col("company_a") < pl.col("company_b"))
        .group_by("company_a", "company_b")
        .agg(pl.len().alias("shared_partners"))
        .sort("shared_partners", descending=True)
    )
