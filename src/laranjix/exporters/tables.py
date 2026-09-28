"""Writing generated tables to Parquet and CSV."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import polars as pl


def write_tables(
    tables: dict[str, pl.DataFrame],
    directory: Path,
    formats: Iterable[str] = ("parquet", "csv"),
) -> list[Path]:
    """Write each table once per requested format; return the written paths."""
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, frame in tables.items():
        for output_format in formats:
            if output_format == "parquet":
                path = directory / f"{name}.parquet"
                frame.write_parquet(path)
            elif output_format == "csv":
                path = directory / f"{name}.csv"
                frame.write_csv(path)
            else:
                raise ValueError(f"unsupported output format: {output_format}")
            written.append(path)
    return written
