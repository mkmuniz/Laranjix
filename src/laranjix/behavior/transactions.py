"""Generation of ordinary, non-fraudulent transactions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np
import polars as pl

from laranjix.behavior.calendar import day_range, day_weights, is_night
from laranjix.behavior.social import CounterpartyGraph, build_counterparty_graph
from laranjix.calibration.loader import Calibration

TRANSACTION_SCHEMA: dict[str, Any] = {
    "tx_id": pl.Utf8,
    "src_account_id": pl.Utf8,
    "dst_account_id": pl.Utf8,
    "channel": pl.Utf8,
    "amount": pl.Float64,
    "timestamp": pl.Datetime("us"),
    "is_night": pl.Boolean,
    "device_id": pl.Utf8,
}

SECONDS_PER_DAY = 86_400
DEVICE_CHANGE_RATE = 0.03


@dataclass(frozen=True)
class NormalActivity:
    """Ordinary transactions plus the graph they were drawn on."""

    transactions: pl.DataFrame
    graph: CounterpartyGraph
    account_ids: np.ndarray


def _snap_to_round_values(
    amounts: np.ndarray, rng: np.random.Generator, fraction: float
) -> np.ndarray:
    """Round a share of the amounts, the way people actually send money.

    Pix values cluster hard on round numbers. A generator that produces only
    smooth lognormal cents gives a model a free signal it would not have in
    production.
    """
    chosen = rng.random(amounts.size) < fraction
    if not chosen.any():
        return amounts
    values = amounts[chosen]
    step = np.where(values < 200, 10.0, np.where(values < 1_000, 50.0, 100.0))
    amounts = amounts.copy()
    amounts[chosen] = np.maximum(np.round(values / step) * step, step)
    return amounts


def generate_normal_transactions(
    rng: np.random.Generator,
    accounts: pl.DataFrame,
    calibration: Calibration,
    reference_date: date,
) -> NormalActivity:
    """Return the ordinary activity of every account over the calibration window."""
    params: dict[str, Any] = calibration.data("behavior")
    window_days = int(params["window"]["days"])
    days = day_range(reference_date, window_days)

    segments = accounts["segment"].to_numpy()
    holder_types = accounts["holder_type"].to_numpy()
    account_ids = accounts["account_id"].to_numpy()
    account_count = accounts.height

    monthly = params["activity"]["monthly_tx"]
    rates = np.array([float(monthly.get(str(segment), 30)) for segment in segments])
    expected = rates * window_days / 30.0
    total = int(expected.sum())
    if total <= 0:
        return NormalActivity(
            transactions=pl.DataFrame(schema=TRANSACTION_SCHEMA),
            graph=build_counterparty_graph(rng, account_count, 1, 2, 0.75),
            account_ids=account_ids,
        )

    counterparty_params = params["counterparties"]
    graph = build_counterparty_graph(
        rng,
        account_count,
        int(counterparty_params["regular_min"]),
        int(counterparty_params["regular_max"]),
        float(counterparty_params["preferential_attachment"]),
    )

    senders = rng.choice(account_count, size=total, p=expected / expected.sum())

    # Most payments go to someone the sender already pays; the rest are new pairs.
    new_fraction = float(counterparty_params["new_counterparty_fraction"])
    from_circle = rng.random(total) >= new_fraction
    receivers = np.where(
        from_circle,
        graph.pick(senders, rng.random(total)),
        rng.integers(0, account_count, size=total),
    )
    self_pay = receivers == senders
    receivers[self_pay] = (receivers[self_pay] + 1) % account_count

    day_probabilities = day_weights(
        days,
        [float(w) for w in params["day_of_week"]["weights"]],
        [int(d) for d in params["payday"]["days"]],
        float(params["payday"]["multiplier"]),
        float(params["holiday_multiplier"]),
    )
    day_probabilities = day_probabilities / day_probabilities.sum()
    day_index = rng.choice(len(days), size=total, p=day_probabilities)

    hour_weights = np.array([float(w) for w in params["hour_of_day"]["weights"]])
    hours = rng.choice(24, size=total, p=hour_weights / hour_weights.sum())
    seconds_in_hour = rng.integers(0, 3600, size=total)

    epoch = np.datetime64(days[0], "s")
    timestamps = (
        epoch
        + day_index.astype("timedelta64[D]").astype("timedelta64[s]")
        + (hours * 3600 + seconds_in_hour).astype("timedelta64[s]")
    )

    lognormal = params["amount"]["lognormal"]
    means = np.array([float(lognormal[str(s)]["mean_log"]) for s in segments])[senders]
    sigmas = np.array([float(lognormal[str(s)]["sigma_log"]) for s in segments])[senders]
    amounts = rng.lognormal(mean=means, sigma=sigmas)
    amounts = _snap_to_round_values(amounts, rng, float(params["amount"]["round_number_fraction"]))
    amounts = np.clip(
        amounts, float(params["amount"]["min_brl"]), float(params["amount"]["max_brl"])
    )

    night = is_night(hours, int(params["night"]["start_hour"]), int(params["night"]["end_hour"]))
    individual = holder_types == "PF"
    limit = float(params["night"]["pf_limit_brl"])
    capped = night & individual[senders] & individual[receivers] & (amounts > limit)
    # Scale rather than clip: a hard clip would pile every large night payment on
    # exactly R$ 1.000, a spike no real dataset has.
    amounts[capped] = rng.uniform(0.25, 1.0, size=int(capped.sum())) * limit

    devices = np.char.add("dev_", senders.astype(str))
    switched = rng.random(total) < DEVICE_CHANGE_RATE
    devices[switched] = np.char.add("dev_alt_", senders[switched].astype(str))

    order = np.argsort(timestamps, kind="stable")
    frame = pl.DataFrame(
        {
            "tx_id": [f"tx_{index:09d}" for index in range(1, total + 1)],
            "src_account_id": account_ids[senders[order]],
            "dst_account_id": account_ids[receivers[order]],
            "channel": np.full(total, "pix"),
            "amount": np.round(amounts[order], 2),
            "timestamp": timestamps[order].astype("datetime64[us]"),
            "is_night": night[order],
            "device_id": devices[order],
        },
        schema=TRANSACTION_SCHEMA,
    )
    return NormalActivity(transactions=frame, graph=graph, account_ids=account_ids)
