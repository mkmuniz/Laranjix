"""The fidelity checks a generated population is put through."""

from __future__ import annotations

from typing import Any

import numpy as np
import polars as pl

from laranjix.calibration.loader import Calibration
from laranjix.population.accounts import _institution_shares
from laranjix.population.generator import Population
from laranjix.privacy import identifiers as ident
from laranjix.validation.fidelity import (
    FidelityCheck,
    FidelityReport,
    check_distribution,
)


def _shares(frame: pl.DataFrame, column: str) -> dict[str, float]:
    total = float(frame.height)
    if total == 0:
        return {}
    # The alias must not collide with the grouped column itself, which happens
    # when the distribution being checked is already a count ("keys per account").
    counts = frame.group_by(column).agg(pl.len().alias("__count"))
    return {
        str(key): int(value) / total for key, value in counts.select(column, "__count").iter_rows()
    }


def _institution_target(calibration: Calibration, count: int) -> dict[str, float]:
    params = calibration.data("accounts")["institutions"]
    shares = _institution_shares(
        np.random.default_rng(0), count, float(params["share_concentration"])
    )
    return {ident.institution_id(index + 1): share for index, share in enumerate(shares)}


def population_fidelity(
    population: Population,
    calibration: Calibration,
    rng: np.random.Generator | None = None,
) -> FidelityReport:
    """Run every fidelity check against the calibration targets."""
    generator = rng or np.random.default_rng(0)
    accounts = population.accounts
    keys = population.pix_keys
    account_params = calibration.data("accounts")
    key_params = calibration.data("pix_keys")

    provisional = set(calibration.provisional_ids())
    checks: list[FidelityCheck] = []

    def add(
        name: str,
        parameter_id: str,
        frame: pl.DataFrame,
        column: str,
        target: dict[str, Any],
    ) -> None:
        if frame.height == 0 or not target:
            return
        checks.append(
            check_distribution(
                name=name,
                parameter_id=parameter_id,
                observed=_shares(frame, column),
                target_weights={str(k): float(v) for k, v in target.items()},
                sample_size=frame.height,
                rng=generator,
                provisional_target=parameter_id in provisional,
            )
        )

    add(
        "UF das contas",
        "population_uf",
        accounts,
        "uf",
        calibration.data("population_uf")["values"],
    )
    add(
        "Tipo de titular (PF/PJ/MEI)",
        "accounts",
        accounts,
        "holder_type",
        account_params["holder_type_mix"]["values"],
    )
    add(
        "Instituicao da conta",
        "accounts",
        accounts,
        "institution_id",
        _institution_target(calibration, accounts["institution_id"].n_unique()),
    )

    individuals = accounts.filter(pl.col("holder_type") == "PF")
    companies = accounts.filter(pl.col("holder_type").is_in(["PJ", "MEI"]))
    add(
        "Perfil de uso (PF)",
        "accounts",
        individuals,
        "segment",
        account_params["segment_mix"]["pf"],
    )
    add("Perfil de uso (PJ)", "accounts", companies, "segment", account_params["segment_mix"]["pj"])
    add(
        "Faixa de renda (PF)",
        "accounts",
        individuals,
        "income_band",
        account_params["income_band"]["values"],
    )

    pf_ids = individuals.select("account_id")
    pj_ids = companies.select("account_id")
    add(
        "Tipo de chave Pix (PF)",
        "pix_keys",
        keys.join(pf_ids, on="account_id"),
        "key_type",
        key_params["key_type_mix_pf"],
    )
    add(
        "Tipo de chave Pix (PJ)",
        "pix_keys",
        keys.join(pj_ids, on="account_id"),
        "key_type",
        key_params["key_type_mix_pj"],
    )

    per_account = (
        keys.group_by("account_id").agg(pl.len().alias("n")).with_columns(pl.col("n").cast(pl.Utf8))
    )
    add(
        "Chaves por conta",
        "pix_keys",
        per_account,
        "n",
        key_params["keys_per_account"],
    )
    return FidelityReport(checks=checks)
