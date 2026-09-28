"""The plugin interface every fraud typology implements.

A typology receives the ordinary activity that already exists and plants cases
inside it. It returns the transactions it added and, separately, the ground
truth: which case each one belongs to and what role each account played. Labels
never travel in the data tables -- see ``laranjix.labels``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
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


@dataclass(frozen=True)
class InjectionContext:
    """Everything a typology needs to plant cases in an existing dataset."""

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

    def active_accounts(self, holder_type: str | None = None) -> np.ndarray:
        """Accounts that already have ordinary outgoing activity.

        A mule with no history at all is a giveaway, so the harder difficulties
        recruit from here.
        """
        active = self.normal["src_account_id"].unique()
        frame = self.accounts.filter(pl.col("account_id").is_in(active))
        if holder_type is not None:
            frame = frame.filter(pl.col("holder_type") == holder_type)
        return frame["account_id"].to_numpy()

    def typical_amount(self, account_id: str, fallback: float) -> float:
        """A plausible large-but-not-absurd amount for this account."""
        history = self.normal.filter(pl.col("src_account_id") == account_id)["amount"]
        if history.len() < 4:
            return fallback
        return float(history.quantile(0.92) or fallback)


class Typology(Protocol):
    """A fraud typology plugin."""

    code: str
    name: str
    source_reference: str

    def inject(self, context: InjectionContext) -> InjectionResult: ...
