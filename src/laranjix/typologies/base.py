"""The plugin interface every fraud typology implements.

A typology receives the ordinary activity that already exists and plants cases
inside it. It returns the transactions it added and, separately, the ground
truth: which case each one belongs to and what role each account played. Labels
never travel in the data tables -- see ``laranjix.labels``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from functools import cached_property
from typing import Protocol

import numpy as np
import polars as pl

from laranjix.calibration.loader import Calibration
from laranjix.config import DifficultySettings, FraudConfig


@dataclass(frozen=True)
class PlantedTransaction:
    """One transaction belonging to a fraud case."""

    src_account_id: str
    dst_account_id: str
    amount: float
    timestamp: np.datetime64
    channel: str
    device_id: str
    case_id: str
    typology: str
    role: str


@dataclass(frozen=True)
class Case:
    """One fraud case: a set of accounts, roles and transactions."""

    case_id: str
    typology: str
    difficulty: str
    start_ts: np.datetime64
    end_ts: np.datetime64
    depth: int
    total_amount: float
    accounts: dict[str, str]
    source_reference: str


@dataclass(frozen=True)
class InjectionResult:
    """What a typology planted."""

    transactions: list[PlantedTransaction] = field(default_factory=list)
    cases: list[Case] = field(default_factory=list)


@dataclass
class InjectionContext:
    """Everything a typology needs to plant cases in an existing dataset.

    The lookups below are built once and cached. A typology asks for them once
    per case -- hundreds of times per run -- and each answer needs a pass over
    the whole transaction table, which is millions of rows.
    """

    rng: np.random.Generator
    accounts: pl.DataFrame
    normal: pl.DataFrame
    calibration: Calibration
    difficulty: DifficultySettings
    difficulty_name: str
    fraud: FraudConfig
    reference_date: date

    def account_index(self) -> dict[str, int]:
        return {account: index for index, account in enumerate(self.accounts["account_id"])}

    @cached_property
    def _active(self) -> pl.DataFrame:
        senders = self.normal["src_account_id"].unique()
        return self.accounts.filter(pl.col("account_id").is_in(senders))

    def active_accounts(self, holder_type: str | None = None) -> np.ndarray:
        """Accounts that already have ordinary outgoing activity.

        A mule with no history at all is a giveaway, so the harder difficulties
        recruit from here.
        """
        frame = self._active
        if holder_type is not None:
            frame = frame.filter(pl.col("holder_type") == holder_type)
        return frame["account_id"].to_numpy()

    @cached_property
    def _typical_amounts(self) -> dict[str, float]:
        """The 92nd percentile each account usually sends, in one pass."""
        stats = (
            self.normal.group_by("src_account_id")
            .agg(pl.col("amount").quantile(0.92).alias("usual"), pl.len().alias("sent"))
            .filter(pl.col("sent") >= 4)
        )
        return dict(zip(stats["src_account_id"], stats["usual"], strict=True))

    def typical_amount(self, account_id: str, fallback: float) -> float:
        """A plausible large-but-not-absurd amount for this account."""
        return self._typical_amounts.get(account_id) or fallback


class Typology(Protocol):
    """A fraud typology plugin."""

    code: str
    name: str
    source_reference: str

    def inject(self, context: InjectionContext) -> InjectionResult: ...
