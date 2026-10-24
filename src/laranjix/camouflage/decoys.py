"""Legitimate accounts that look exactly like mules.

This is what separates a hard dataset from a toy one. "Money arrives and leaves
within the hour" describes a mule -- and also a small shop paying suppliers, a
church treasurer, a building manager collecting condo fees. If every fast
pass-through in the dataset is fraud, a two-line rule solves the benchmark and
the dataset teaches a model nothing it can use in production.

These transactions are ordinary and are never labelled as fraud.
"""

from __future__ import annotations

import numpy as np

from laranjix.typologies.base import InjectionContext, PlantedTransaction


def build_decoys(context: InjectionContext) -> list[PlantedTransaction]:
    """Return legitimate fast pass-through activity."""
    rng = context.rng
    wanted = context.difficulty.decoy_cases
    if wanted <= 0 or context.normal.height == 0:
        return []

    everyone = context.accounts["account_id"].to_numpy()
    if everyone.size < 4:
        return []

    timestamps = context.normal["timestamp"].to_numpy()
    first, last = timestamps.min(), timestamps.max()
    span_seconds = max(int((last - first) / np.timedelta64(1, "s")), 1)

    planted: list[PlantedTransaction] = []
    for _ in range(wanted):
        hub = str(rng.choice(everyone))
        payers = rng.choice(everyone, size=int(rng.integers(4, 22)))
        window_start = first + np.timedelta64(int(rng.integers(0, span_seconds)), "s")
        window_seconds = int(rng.uniform(1.0, 8.0) * 3600)

        collected = 0.0
        latest = window_start
        for payer in payers:
            payer_id = str(payer)
            if payer_id == hub:
                continue
            amount = float(np.clip(rng.lognormal(4.4, 1.0), 20.0, 9_000.0))
            moment = window_start + np.timedelta64(int(rng.integers(0, window_seconds)), "s")
            planted.append(
                PlantedTransaction(
                    src_account_id=payer_id,
                    dst_account_id=hub,
                    amount=round(amount, 2),
                    timestamp=moment,
                    channel="pix",
                    device_id=f"dev_{payer_id.removeprefix('acc_').lstrip('0') or '0'}",
                    case_id="",
                    typology="",
                    role="",
                )
            )
            collected += amount
            latest = max(latest, moment)

        # And it goes straight back out, the same shape a mule would show.
        slices = int(rng.integers(2, 6))
        moment = latest
        for target in rng.choice(everyone, size=slices):
            target_id = str(target)
            if target_id == hub:
                continue
            moment = moment + np.timedelta64(int(rng.uniform(3, 90) * 60), "s")
            planted.append(
                PlantedTransaction(
                    src_account_id=hub,
                    dst_account_id=target_id,
                    amount=round(max(collected * rng.uniform(0.7, 0.98) / slices, 1.0), 2),
                    timestamp=moment,
                    channel="pix",
                    device_id=f"dev_{hub.removeprefix('acc_').lstrip('0') or '0'}",
                    case_id="",
                    typology="",
                    role="",
                )
            )
    return planted
