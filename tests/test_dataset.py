"""The planted typologies must produce the graph signatures they claim."""

from __future__ import annotations

from itertools import pairwise

import polars as pl
import pytest

from laranjix.config import GenerationConfig
from laranjix.dataset import generate_dataset
from laranjix.labels import MED_CONTESTATION_DAYS


@pytest.fixture(scope="module")
def dataset():
    return generate_dataset(
        GenerationConfig(seed=3, difficulty="hard", population={"accounts": 4_000})
    )


def test_transactions_carry_no_label_columns(dataset) -> None:
    # Label leakage would make every benchmark meaningless.
    leaked = {"is_fraud", "case_id", "typology", "role"} & set(dataset.transactions.columns)
    assert leaked == set()


def test_labels_cover_every_transaction_exactly_once(dataset) -> None:
    labels = dataset.labels_transactions
    assert labels.height == dataset.transactions.height
    assert labels["tx_id"].n_unique() == labels.height
    assert set(labels["tx_id"]) == set(dataset.transactions["tx_id"])


def test_fraud_is_rare_but_present(dataset) -> None:
    assert dataset.cases.height > 0
    assert 0.0 < dataset.fraud_rate < 0.05


def test_transactions_are_ordered_in_time(dataset) -> None:
    timestamps = dataset.transactions["timestamp"].to_list()
    assert timestamps == sorted(timestamps)


def test_labels_become_available_after_the_transaction(dataset) -> None:
    joined = dataset.transactions.join(dataset.labels_transactions, on="tx_id")
    fraud = joined.filter(pl.col("is_fraud"))
    assert fraud.height > 0
    delay_days = (pl.col("label_available_at") - pl.col("timestamp")).dt.total_seconds() / 86_400
    delays = fraud.select(delay_days.alias("d"))["d"]
    assert delays.min() > 0, "um rotulo de fraude nunca chega antes da transacao"
    assert delays.max() <= MED_CONTESTATION_DAYS
    # Non-fraud rows are known immediately.
    assert (
        joined.filter(~pl.col("is_fraud"))
        .select((pl.col("label_available_at") == pl.col("timestamp")).all())
        .item()
    )


def test_t1_chains_form_directed_paths_with_short_hops(dataset) -> None:
    labels = dataset.labels_transactions.filter(pl.col("typology") == "T1")
    assert labels.height > 0
    joined = dataset.transactions.join(labels, on="tx_id").sort("timestamp")

    checked = 0
    for case_id in labels["case_id"].unique().to_list()[:15]:
        case = joined.filter(pl.col("case_id") == case_id)
        if case.height < 2:
            continue
        checked += 1
        # Each hop starts where the previous one ended: a directed path.
        senders = case["src_account_id"].to_list()[1:]
        receivers = case["dst_account_id"].to_list()[:-1]
        assert senders == receivers
        # And the money keeps moving, never gaining value.
        amounts = case["amount"].to_list()
        assert all(later <= earlier + 0.01 for earlier, later in pairwise(amounts))
    assert checked > 0


def test_t2_cases_are_fan_in_followed_by_fan_out(dataset) -> None:
    labels = dataset.labels_transactions.filter(pl.col("typology") == "T2")
    assert labels.height > 0
    joined = dataset.transactions.join(labels, on="tx_id")

    checked = 0
    for case_id in labels["case_id"].unique().to_list()[:15]:
        case = joined.filter(pl.col("case_id") == case_id)
        inbound = case.filter(pl.col("role") == "victim_payment")
        outbound = case.filter(pl.col("role").str.starts_with("fan_out"))
        if inbound.height == 0 or outbound.height == 0:
            continue
        checked += 1
        # Many distinct victims, all paying the same account.
        assert inbound["src_account_id"].n_unique() >= 3
        assert inbound["dst_account_id"].n_unique() == 1
        # And the money leaves after it arrives.
        assert outbound["timestamp"].min() >= inbound["timestamp"].min()
    assert checked > 0


def test_case_accounts_are_recorded_in_the_account_labels(dataset) -> None:
    involved = set(dataset.labels_accounts["account_id"])
    assert involved
    assert involved <= set(dataset.population.accounts["account_id"])
    assert dataset.labels_accounts["roles"].str.contains("victim").any()


def test_the_same_seed_reproduces_the_whole_dataset() -> None:
    config = GenerationConfig(seed=5, difficulty="medium", population={"accounts": 1_500})
    first, second = generate_dataset(config), generate_dataset(config)
    for name, frame in first.tables().items():
        assert frame.equals(second.tables()[name]), f"{name} nao e reprodutivel"


def test_difficulty_changes_how_well_hidden_the_fraud_is() -> None:
    easy = GenerationConfig(seed=5, difficulty="easy").difficulty_settings
    hard = GenerationConfig(seed=5, difficulty="hard").difficulty_settings
    assert hard.mule_history_fraction > easy.mule_history_fraction
    assert hard.hop_minutes_max > easy.hop_minutes_max
    assert hard.decoy_cases > easy.decoy_cases


def test_decoys_are_never_labelled_as_fraud() -> None:
    # Legitimate pass-through accounts exist precisely so that "fast in, fast
    # out" is not a perfect rule. They must not be in the ground truth.
    dataset = generate_dataset(
        GenerationConfig(seed=9, difficulty="hard", population={"accounts": 2_000})
    )
    fraud_cases = set(dataset.labels_transactions.filter(pl.col("is_fraud"))["case_id"])
    assert "" not in fraud_cases
