"""Generation of the fictitious account population (scope milestone 2)."""

from __future__ import annotations

from typing import Any

import numpy as np
import polars as pl

from laranjix.calibration.loader import Calibration, normalise
from laranjix.config import PopulationConfig
from laranjix.privacy import identifiers as ident

ACCOUNT_SCHEMA: dict[str, Any] = {
    "account_id": pl.Utf8,
    "holder_type": pl.Utf8,
    "holder_id": pl.Utf8,
    "holder_name": pl.Utf8,
    "institution_id": pl.Utf8,
    "uf": pl.Utf8,
    "created_at": pl.Date,
    "income_band": pl.Utf8,
    "segment": pl.Utf8,
}

_COMPANY_TYPES = frozenset({"PJ", "MEI"})


def _choose(rng: np.random.Generator, weights: dict[str, float], size: int) -> np.ndarray:
    keys, probabilities = normalise(weights)
    return rng.choice(keys, size=size, p=probabilities)


def _institution_shares(rng: np.random.Generator, count: int, concentration: float) -> list[float]:
    """Skewed market share: a few institutions hold most of the accounts."""
    ranks = np.arange(1, count + 1, dtype=float)
    weights = ranks**-concentration
    return list(weights / weights.sum())


def _account_ages(rng: np.random.Generator, size: int, params: dict[str, float]) -> np.ndarray:
    days = rng.lognormal(
        mean=float(params["lognormal_mean_log"]),
        sigma=float(params["lognormal_sigma_log"]),
        size=size,
    )
    return np.clip(days, 1.0, float(params["max_days"])).astype(int)


def generate_accounts(
    rng: np.random.Generator,
    config: PopulationConfig,
    calibration: Calibration,
) -> pl.DataFrame:
    """Return the ``accounts`` table.

    Holder documents are invalid by construction and institutions are fictitious;
    see :mod:`laranjix.privacy.identifiers`.
    """
    size = config.accounts
    account_params = calibration.data("accounts")
    names = calibration.data("names")

    holder_types = _choose(rng, account_params["holder_type_mix"]["values"], size)
    ufs = _choose(rng, calibration.data("population_uf")["values"], size)

    institution_count = config.institutions or int(account_params["institutions"]["count"])
    shares = _institution_shares(
        rng, institution_count, float(account_params["institutions"]["share_concentration"])
    )
    institution_names = np.array([ident.institution_id(i) for i in range(1, institution_count + 1)])
    institutions = institution_names[rng.choice(institution_count, size=size, p=shares)]

    ages = _account_ages(rng, size, account_params["account_age"])
    created_at = np.datetime64(config.reference_date, "D") - ages.astype("timedelta64[D]")

    income_bands = _choose(rng, account_params["income_band"]["values"], size)
    revenue_bands = _choose(rng, account_params["revenue_band"]["values"], size)
    pf_segments = _choose(rng, account_params["segment_mix"]["pf"], size)
    pj_segments = _choose(rng, account_params["segment_mix"]["pj"], size)

    given_names = list(names["given_names"])
    surnames = list(names["surnames"])
    branches = list(names["company_branches"])
    suffixes = list(names["company_suffixes"])

    # Both kinds are drawn for every row and selected by mask. The vectorised
    # generators cost microseconds per thousand, so branching per row would cost
    # more than the work it avoids.
    is_company = np.isin(holder_types, list(_COMPANY_TYPES))
    holder_ids = np.where(is_company, ident.fake_cnpj(rng, size), ident.fake_cpf(rng, size))
    holder_names = np.where(
        is_company,
        ident.fake_company_name(rng, size, surnames, branches, suffixes),
        ident.fake_name(rng, size, given_names, surnames),
    )
    bands = np.where(
        is_company,
        np.where(holder_types == "MEI", "mei", revenue_bands),
        income_bands,
    )
    segments = np.where(is_company, pj_segments, pf_segments)

    return pl.DataFrame(
        {
            "account_id": ident.account_ids(size),
            "holder_type": holder_types,
            "holder_id": holder_ids,
            "holder_name": holder_names,
            "institution_id": institutions,
            "uf": ufs,
            "created_at": created_at,
            "income_band": bands,
            "segment": segments,
        },
        schema=ACCOUNT_SCHEMA,
    )


def institutions_table(count: int) -> pl.DataFrame:
    """Return the fictitious institutions reference table."""
    return pl.DataFrame(
        {
            "institution_id": [ident.institution_id(i) for i in range(1, count + 1)],
            "institution_name": [ident.institution_name(i) for i in range(1, count + 1)],
            "is_fictitious": [True] * count,
        }
    )
