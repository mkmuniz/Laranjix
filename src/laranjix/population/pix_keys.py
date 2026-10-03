"""Generation of the Pix keys bound to each account."""

from __future__ import annotations

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
) -> tuple[list[str], np.ndarray]:
    """Return the draw weights whose realized mix matches ``mix``."""
    names, probabilities = normalise({str(k): float(v) for k, v in mix.items()})
    target = tuple(sorted(zip(names, probabilities, strict=True)))
    solved = solve_draw_weights(target, counts, _UNIQUE_TYPES)
    return [name for name, _ in solved], np.array([weight for _, weight in solved])


def _draw_key_types(
    rng: np.random.Generator,
    wanted: np.ndarray,
    type_names: list[str],
    weights: np.ndarray,
    max_keys: int,
) -> np.ndarray:
    """Draw each account's key types, one draw position at a time.

    The constraint is per account -- a type already taken cannot be taken again
    -- so the draws cannot be independent. Instead of looping over accounts, the
    whole population advances through draw position 0, 1, 2 ... together, with a
    mask of which types each account may still take. That is the same sequential
    renormalised scheme the weights were solved for, just transposed.

    Returns an (accounts, max_keys) matrix of type indices, ``-1`` where the
    account has no key in that position.
    """
    accounts = wanted.size
    unique = np.array([name in _UNIQUE_TYPES for name in type_names])
    allowed = np.ones((accounts, len(type_names)), dtype=bool)
    chosen = np.full((accounts, max_keys), -1, dtype=np.int64)

    for position in range(max_keys):
        active = wanted > position
        if not active.any():
            break

        masked = np.where(allowed, weights, 0.0)
        totals = masked.sum(axis=1, keepdims=True)
        # out= matters: without it, rows where the divisor is zero would hold
        # uninitialised memory rather than zeros.
        shares = np.divide(masked, totals, out=np.zeros_like(masked), where=totals > 0)
        cumulative = np.cumsum(shares, axis=1)

        draws = rng.random(accounts)[:, None]
        picked = (cumulative < draws).sum(axis=1).clip(max=len(type_names) - 1)

        chosen[active, position] = picked[active]
        # A unique type just taken is no longer available to that account.
        taken = active & unique[picked]
        allowed[taken, picked[taken]] = False

    return chosen


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
    recent_fraction = float(params["registration"]["recent_fraction"])
    recent_window = int(params["registration"]["recent_window_days"])

    size = accounts.height
    holder_types = accounts["holder_type"].to_numpy()
    holder_ids = accounts["holder_id"].to_numpy()
    holder_names = accounts["holder_name"].to_numpy()
    account_ids = accounts["account_id"].to_numpy()
    created_at = accounts["created_at"].to_numpy().astype("datetime64[D]")

    max_keys = min(max(counts), config.max_keys_per_account)
    wanted = np.minimum(
        np.asarray(counts)[rng.choice(len(counts), size=size, p=count_probabilities)],
        config.max_keys_per_account,
    )

    # PF and PJ draw from different mixes, so each group advances on its own.
    is_company = np.isin(holder_types, ["PJ", "MEI"])
    type_index = np.full((size, max_keys), -1, dtype=np.int64)
    type_names: list[str] = []
    for mix_key, group in (
        ("key_type_mix_pf", ~is_company),
        ("key_type_mix_pj", is_company),
    ):
        names, weights = _draw_weights(params[mix_key], count_pairs)
        if not group.any():
            continue
        drawn = _draw_key_types(rng, wanted[group], names, weights, max_keys)
        # Both mixes share evp/email/phone; map each group's indices onto one
        # shared vocabulary so the two can live in the same matrix.
        offset = len(type_names)
        type_names.extend(names)
        type_index[group] = np.where(drawn < 0, -1, drawn + offset)

    vocabulary = np.array(type_names)
    present = type_index >= 0
    rows, positions = np.nonzero(present)
    key_types = vocabulary[type_index[rows, positions]]
    total = rows.size

    key_values = np.where(
        np.isin(key_types, ["cpf", "cnpj"]),
        holder_ids[rows],
        "",
    )
    email_mask = key_types == "email"
    key_values[email_mask] = ident.fake_email(rng, holder_names[rows][email_mask])
    phone_mask = key_types == "phone"
    key_values[phone_mask] = ident.fake_phone(rng, int(phone_mask.sum()))
    evp_mask = key_types == "evp"
    key_values[evp_mask] = ident.evp_key(rng, int(evp_mask.sum()))

    reference = np.datetime64(config.reference_date, "D")
    span = (reference - created_at[rows]).astype(int)
    since_opening = created_at[rows] + (rng.random(total) * (span + 1)).astype("timedelta64[D]")
    recently = reference - (rng.random(total) * recent_window).astype("timedelta64[D]")
    registered_at = np.where(rng.random(total) < recent_fraction, recently, since_opening)

    return pl.DataFrame(
        {
            "key_id": np.char.mod("key_%07d", np.arange(1, total + 1)),
            "account_id": account_ids[rows],
            "key_type": key_types,
            "key_value": key_values,
            "registered_at": registered_at,
        },
        schema=PIX_KEY_SCHEMA,
    )
