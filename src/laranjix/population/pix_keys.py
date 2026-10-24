"""Generation of the Pix keys bound to each account."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import numpy as np
import polars as pl

from laranjix.calibration.loader import Calibration, normalise
from laranjix.config import PopulationConfig
from laranjix.population.key_mix import solve_draw_weights
from laranjix.privacy import identifiers as ident

PIX_KEY_SCHEMA: dict[str, Any] = {
    "key_id": pl.Utf8,
    "account_id": pl.Utf8,
    "key_type": pl.Utf8,
    "key_value": pl.Utf8,
    "registered_at": pl.Date,
}

# A Pix account can hold at most one key of each document/contact type; only EVP
# repeats. Because of that constraint the calibrated mix is not what may be drawn
# from directly -- see laranjix.population.key_mix.
_UNIQUE_TYPES = frozenset({"cpf", "cnpj", "email", "phone"})


def _key_count_distribution(params: dict[str, float]) -> tuple[list[int], list[float]]:
    keys, probabilities = normalise({str(k): float(v) for k, v in params.items()})
    return [int(key) for key in keys], probabilities


def _draw_weights(
    mix: dict[str, Any], counts: tuple[tuple[int, float], ...]
) -> tuple[list[str], list[float]]:
    """Return the draw weights whose realized mix matches ``mix``."""
    names, probabilities = normalise({str(k): float(v) for k, v in mix.items()})
    target = tuple(sorted(zip(names, probabilities, strict=True)))
    solved = solve_draw_weights(target, counts, _UNIQUE_TYPES)
    return [name for name, _ in solved], [weight for _, weight in solved]


def generate_pix_keys(
    rng: np.random.Generator,
    accounts: pl.DataFrame,
    config: PopulationConfig,
    calibration: Calibration,
) -> pl.DataFrame:
    """Return the ``pix_keys`` table.

    Key values reuse the account's own (invalid) document, a reserved-domain
    e-mail, an undialable phone number or a locally generated UUID.
    """
    params = calibration.data("pix_keys")
    counts, count_probabilities = _key_count_distribution(params["keys_per_account"])
    count_pairs = tuple(zip(counts, count_probabilities, strict=True))
    individual_weights = _draw_weights(params["key_type_mix_pf"], count_pairs)
    company_weights = _draw_weights(params["key_type_mix_pj"], count_pairs)
    recent_fraction = float(params["registration"]["recent_fraction"])
    recent_window = int(params["registration"]["recent_window_days"])

    rows: dict[str, list[Any]] = {name: [] for name in PIX_KEY_SCHEMA}
    key_index = 0

    columns = accounts.select("account_id", "holder_type", "holder_id", "holder_name", "created_at")
    for account_id, holder_type, holder_id, holder_name, created_at in columns.iter_rows():
        is_company = holder_type in {"PJ", "MEI"}
        types, type_probabilities = company_weights if is_company else individual_weights

        wanted = min(
            int(rng.choice(counts, p=count_probabilities)),
            config.max_keys_per_account,
        )
        used_unique: set[str] = set()
        for _ in range(wanted):
            # Draw only among the types this account may still take, renormalised
            # -- the scheme the draw weights were solved for.
            allowed = [
                index
                for index, name in enumerate(types)
                if not (name in _UNIQUE_TYPES and name in used_unique)
            ]
            weights = np.array([type_probabilities[index] for index in allowed])
            total = weights.sum()
            if total <= 0:
                break
            key_type = str(types[int(rng.choice(allowed, p=weights / total))])
            if key_type in _UNIQUE_TYPES:
                used_unique.add(key_type)

            if key_type in {"cpf", "cnpj"}:
                key_value = holder_id
            elif key_type == "email":
                key_value = ident.fake_email(rng, holder_name, key_index)
            elif key_type == "phone":
                key_value = ident.fake_phone(rng)
            else:
                key_value = ident.evp_key(rng)

            if rng.random() < recent_fraction:
                registered_at = config.reference_date - timedelta(
                    days=int(rng.integers(0, recent_window))
                )
            else:
                span = max((config.reference_date - created_at).days, 0)
                registered_at = created_at + timedelta(days=int(rng.integers(0, span + 1)))

            key_index += 1
            rows["key_id"].append(f"key_{key_index:07d}")
            rows["account_id"].append(account_id)
            rows["key_type"].append(key_type)
            rows["key_value"].append(key_value)
            rows["registered_at"].append(registered_at)

    return pl.DataFrame(rows, schema=PIX_KEY_SCHEMA)
