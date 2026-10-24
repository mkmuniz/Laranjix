"""Ground truth, kept in files of its own.

The labels never travel inside the data tables. A model that reads ``case_id``
from the transaction it is scoring has learned nothing, and a benchmark built
that way measures nothing.

``label_available_at`` is the part most generators leave out. In production a
fraud label does not exist at the moment of the transaction: it exists when the
victim contests, which under the MED can be up to 80 days later (the window rose
from 30 to 80 days on 1 September 2026). A benchmark that hands the label over
instantly trains a model that cannot exist. Splitting on this column instead of
on ``timestamp`` is what makes a temporal evaluation honest.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import polars as pl

from laranjix.typologies.base import Case

# Resolucao BCB 493/2025: prazo de contestacao do MED.
MED_CONTESTATION_DAYS = 80

LABELS_TX_SCHEMA: dict[str, Any] = {
    "tx_id": pl.Utf8,
    "is_fraud": pl.Boolean,
    "typology": pl.Utf8,
    "case_id": pl.Utf8,
    "role": pl.Utf8,
    "label_available_at": pl.Datetime("us"),
}

CASES_SCHEMA: dict[str, Any] = {
    "case_id": pl.Utf8,
    "typology": pl.Utf8,
    "difficulty": pl.Utf8,
    "start_ts": pl.Datetime("us"),
    "end_ts": pl.Datetime("us"),
    "depth": pl.Int32,
    "total_amount": pl.Float64,
    "account_count": pl.Int32,
    "source_reference": pl.Utf8,
}


def reporting_delay(
    rng: np.random.Generator, size: int, max_days: int = MED_CONTESTATION_DAYS
) -> np.ndarray:
    """Days between a fraudulent transaction and the victim contesting it.

    Most victims notice within a couple of days; a long tail takes weeks, and the
    window closes at ``max_days``.
    """
    days = rng.gamma(shape=1.4, scale=6.0, size=size)
    return np.clip(days, 0.02, float(max_days))


def build_transaction_labels(
    transactions: pl.DataFrame,
    rng: np.random.Generator,
) -> pl.DataFrame:
    """Return ``labels_transactions`` for an assembled transaction table."""
    fraud_mask = transactions["case_id"].fill_null("") != ""
    delays = np.zeros(transactions.height)
    fraud_count = int(fraud_mask.sum())
    if fraud_count:
        delays[fraud_mask.to_numpy()] = reporting_delay(rng, fraud_count)

    available = transactions["timestamp"].to_numpy() + (delays * 86_400).astype(
        "timedelta64[s]"
    ).astype("timedelta64[us]")

    return pl.DataFrame(
        {
            "tx_id": transactions["tx_id"],
            "is_fraud": fraud_mask,
            "typology": transactions["typology"].fill_null(""),
            "case_id": transactions["case_id"].fill_null(""),
            "role": transactions["role"].fill_null(""),
            "label_available_at": available,
        },
        schema=LABELS_TX_SCHEMA,
    )


def build_account_labels(cases: list[Case]) -> pl.DataFrame:
    """Return ``labels_accounts``: which accounts took part, and as what."""
    roles: dict[str, set[str]] = {}
    case_ids: dict[str, set[str]] = {}
    for case in cases:
        for account, role in case.accounts.items():
            roles.setdefault(account, set()).add(role)
            case_ids.setdefault(account, set()).add(case.case_id)

    accounts = sorted(roles)
    return pl.DataFrame(
        {
            "account_id": accounts,
            "is_involved": [True] * len(accounts),
            "roles": [";".join(sorted(roles[account])) for account in accounts],
            "case_ids": [";".join(sorted(case_ids[account])) for account in accounts],
        },
        schema={
            "account_id": pl.Utf8,
            "is_involved": pl.Boolean,
            "roles": pl.Utf8,
            "case_ids": pl.Utf8,
        },
    )


def build_cases_table(cases: list[Case]) -> pl.DataFrame:
    """Return the ``cases`` table."""
    if not cases:
        return pl.DataFrame(schema=CASES_SCHEMA)
    return pl.DataFrame(
        {
            "case_id": [case.case_id for case in cases],
            "typology": [case.typology for case in cases],
            "difficulty": [case.difficulty for case in cases],
            # numpy scalars in a list arrive as objects; build the columns as arrays.
            "start_ts": np.array([case.start_ts for case in cases], dtype="datetime64[us]"),
            "end_ts": np.array([case.end_ts for case in cases], dtype="datetime64[us]"),
            "depth": [case.depth for case in cases],
            "total_amount": [case.total_amount for case in cases],
            "account_count": [len(case.accounts) for case in cases],
            "source_reference": [case.source_reference for case in cases],
        },
        schema=CASES_SCHEMA,
    )
