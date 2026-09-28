"""Brazilian calendar effects on transaction timing."""

from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache

import numpy as np


@lru_cache(maxsize=8)
def brazilian_holidays(first_year: int, last_year: int) -> frozenset[date]:
    """Return the national holidays between the two years, inclusive."""
    import holidays

    calendar = holidays.country_holidays("BR", years=range(first_year, last_year + 1))
    return frozenset(calendar.keys())


def day_weights(
    days: list[date],
    day_of_week: list[float],
    payday_days: list[int],
    payday_multiplier: float,
    holiday_multiplier: float,
) -> np.ndarray:
    """Return a relative activity weight for each day in ``days``.

    Weekends and holidays are quieter; the first working days of the month are
    busier, because wages and benefits land then.
    """
    holidays_set = brazilian_holidays(days[0].year, days[-1].year)
    paydays = set(payday_days)
    weights = np.empty(len(days), dtype=float)
    for index, current in enumerate(days):
        weight = day_of_week[current.weekday()]
        if current in holidays_set:
            weight *= holiday_multiplier
        if current.day in paydays:
            weight *= payday_multiplier
        weights[index] = weight
    return weights


def day_range(reference: date, window_days: int) -> list[date]:
    """Return the ``window_days`` days ending the day before ``reference``."""
    start = reference - timedelta(days=window_days)
    return [start + timedelta(days=offset) for offset in range(window_days)]


def is_night(hours: np.ndarray, start_hour: int, end_hour: int) -> np.ndarray:
    """Return the night-window mask for an array of hours."""
    return (hours >= start_hour) | (hours < end_hour)
