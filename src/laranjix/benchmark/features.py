"""Features for the benchmark, split into tabular and graph-derived.

The split is the point of the benchmark. The tabular block is what any
transaction-level model sees: amount, hour, account age. The graph block needs
the transaction to be an edge in a network: how many distinct senders paid this
receiver in the last hour, whether this pair ever transacted before, whether
money arrived in the sender's account minutes before it left again.

Running the same model on the tabular block alone and on both blocks measures
what the graph structure is worth -- which is the whole thesis of the dataset.
"""

from __future__ import annotations

import polars as pl

TABULAR_FEATURES = (
    "log_amount",
    "hour",
    "is_night",
    "day_of_week",
    "src_account_age_days",
    "dst_account_age_days",
    "src_is_company",
    "dst_is_company",
    "amount_vs_src_median",
    "src_tx_count",
)

GRAPH_FEATURES = (
    "pair_seen_before",
    "dst_in_1h",
    "dst_unique_senders_1h",
    "dst_in_amount_1h",
    "src_out_24h",
    "src_unique_receivers_24h",
    "src_inflow_1h_count",
    "src_inflow_1h_amount",
    "passthrough_ratio",
    "seconds_since_src_inflow",
)


def build_features(transactions: pl.DataFrame, accounts: pl.DataFrame) -> pl.DataFrame:
    """Return one row per transaction with every feature column."""
    accounts_small = accounts.select(
        "account_id",
        pl.col("created_at").alias("account_created_at"),
        (pl.col("holder_type") != "PF").cast(pl.Int8).alias("is_company"),
    )

    frame = (
        transactions.sort("timestamp")
        .join(
            accounts_small.rename(
                {
                    "account_id": "src_account_id",
                    "account_created_at": "src_created_at",
                    "is_company": "src_is_company",
                }
            ),
            on="src_account_id",
            how="left",
        )
        .join(
            accounts_small.rename(
                {
                    "account_id": "dst_account_id",
                    "account_created_at": "dst_created_at",
                    "is_company": "dst_is_company",
                }
            ),
            on="dst_account_id",
            how="left",
        )
    )

    frame = frame.with_columns(
        log_amount=pl.col("amount").log1p(),
        hour=pl.col("timestamp").dt.hour(),
        day_of_week=pl.col("timestamp").dt.weekday(),
        src_account_age_days=(
            pl.col("timestamp").dt.date() - pl.col("src_created_at")
        ).dt.total_days(),
        dst_account_age_days=(
            pl.col("timestamp").dt.date() - pl.col("dst_created_at")
        ).dt.total_days(),
        is_night=pl.col("is_night").cast(pl.Int8),
    ).with_columns(
        # How many times this exact pair transacted before this transaction.
        pair_seen_before=pl.int_range(pl.len()).over(["src_account_id", "dst_account_id"]),
        src_tx_count=pl.len().over("src_account_id"),
        amount_vs_src_median=(
            pl.col("amount") / (pl.col("amount").median().over("src_account_id") + 1.0)
        ),
    )

    inbound = _rolling_inbound(frame)
    outbound = _rolling_outbound(frame)
    sender_inflow = _sender_inflow(frame)

    frame = (
        frame.join(inbound, on=["dst_account_id", "timestamp"], how="left")
        .join(outbound, on=["src_account_id", "timestamp"], how="left")
        .join(sender_inflow, on="tx_id", how="left")
    )

    return frame.with_columns(
        src_inflow_1h_count=pl.col("src_inflow_1h_count").fill_null(0),
        src_inflow_1h_amount=pl.col("src_inflow_1h_amount").fill_null(0.0),
        seconds_since_src_inflow=pl.col("seconds_since_src_inflow").fill_null(10**7),
        dst_in_1h=pl.col("dst_in_1h").fill_null(0),
        dst_unique_senders_1h=pl.col("dst_unique_senders_1h").fill_null(0),
        dst_in_amount_1h=pl.col("dst_in_amount_1h").fill_null(0.0),
        src_out_24h=pl.col("src_out_24h").fill_null(0),
        src_unique_receivers_24h=pl.col("src_unique_receivers_24h").fill_null(0),
    ).with_columns(
        # Close to 1 means the money that just arrived is the money leaving:
        # the defining behaviour of a pass-through account.
        passthrough_ratio=pl.col("amount") / (pl.col("src_inflow_1h_amount") + 1.0),
    )


# Polars' rolling collapses rows that share an index value inside a group, so the
# result is keyed by (account, timestamp) rather than by transaction. Joining on
# that key instead of on tx_id gives every transaction in a tie the same window
# statistics, which is what they should have.
def _rolling_inbound(frame: pl.DataFrame) -> pl.DataFrame:
    """Fan-in on the receiver over the last hour."""
    return (
        frame.select("dst_account_id", "timestamp", "src_account_id", "amount")
        .sort("dst_account_id", "timestamp")
        .rolling(index_column="timestamp", period="1h", group_by="dst_account_id")
        .agg(
            pl.len().alias("dst_in_1h"),
            pl.col("src_account_id").n_unique().alias("dst_unique_senders_1h"),
            pl.col("amount").sum().alias("dst_in_amount_1h"),
        )
        .unique(subset=["dst_account_id", "timestamp"], keep="last")
    )


def _rolling_outbound(frame: pl.DataFrame) -> pl.DataFrame:
    """Fan-out on the sender over the last day."""
    return (
        frame.select("src_account_id", "timestamp", "dst_account_id")
        .sort("src_account_id", "timestamp")
        .rolling(index_column="timestamp", period="24h", group_by="src_account_id")
        .agg(
            pl.len().alias("src_out_24h"),
            pl.col("dst_account_id").n_unique().alias("src_unique_receivers_24h"),
        )
        .unique(subset=["src_account_id", "timestamp"], keep="last")
    )


def _sender_inflow(frame: pl.DataFrame) -> pl.DataFrame:
    """What arrived in the sender's account shortly before it sent."""
    inbound = (
        frame.select(
            account="dst_account_id",
            inflow_ts="timestamp",
            amount="amount",
        )
        .sort("account", "inflow_ts")
        .rolling(index_column="inflow_ts", period="1h", group_by="account")
        .agg(
            pl.len().alias("src_inflow_1h_count"),
            pl.col("amount").sum().alias("src_inflow_1h_amount"),
        )
        .sort("inflow_ts")
    )

    outgoing = frame.select("tx_id", account="src_account_id", timestamp="timestamp").sort(
        "timestamp"
    )
    joined = outgoing.join_asof(
        inbound,
        left_on="timestamp",
        right_on="inflow_ts",
        by="account",
        strategy="backward",
    )
    return joined.select(
        "tx_id",
        "src_inflow_1h_count",
        "src_inflow_1h_amount",
        seconds_since_src_inflow=(pl.col("timestamp") - pl.col("inflow_ts")).dt.total_seconds(),
    )
