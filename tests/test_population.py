"""Milestone 2: the generated population must be plausible and safe."""

from __future__ import annotations

import polars as pl
import pytest

from laranjix.config import GenerationConfig
from laranjix.population import generate_population
from laranjix.population.partners import shared_partner_pairs
from laranjix.privacy.scan import scan_text
from laranjix.privacy.validators import is_valid_cnpj, is_valid_cpf


@pytest.fixture(scope="module")
def population():
    return generate_population(GenerationConfig(seed=7, population={"accounts": 1_200}))


def test_account_count_and_unique_ids(population) -> None:
    accounts = population.accounts
    assert accounts.height == 1_200
    assert accounts["account_id"].n_unique() == 1_200
    assert accounts.null_count().sum_horizontal().item() == 0


def test_no_account_document_is_valid(population) -> None:
    documents = population.accounts.select("holder_type", "holder_id")
    for holder_type, holder_id in documents.iter_rows():
        if holder_type == "PF":
            assert not is_valid_cpf(holder_id)
        else:
            assert not is_valid_cnpj(holder_id)


def test_generated_tables_contain_no_pii(population) -> None:
    for name, frame in population.tables().items():
        text = "\n".join(
            "\t".join("" if value is None else str(value) for value in row)
            for row in frame.iter_rows()
        )
        assert scan_text(text, name) == [], f"PII finding in {name}"


def test_all_holder_types_are_present(population) -> None:
    assert set(population.accounts["holder_type"].unique()) == {"PF", "PJ", "MEI"}


def test_uf_distribution_follows_calibration(population) -> None:
    shares = (
        population.accounts.group_by("uf")
        .agg((pl.len() / population.accounts.height).alias("share"))
        .sort("share", descending=True)
    )
    # SP holds roughly 22% of the Brazilian population and must lead by a margin.
    assert shares["uf"][0] == "SP"
    assert 0.12 < shares["share"][0] < 0.32


def test_accounts_are_opened_before_the_reference_date(population) -> None:
    reference = GenerationConfig().population.reference_date
    assert population.accounts["created_at"].max() < reference


def test_pix_keys_reference_existing_accounts(population) -> None:
    known = set(population.accounts["account_id"])
    assert set(population.pix_keys["account_id"]) <= known
    assert population.pix_keys["key_id"].n_unique() == population.pix_keys.height


def test_pix_key_types_are_consistent_with_holder_type(population) -> None:
    joined = population.pix_keys.join(
        population.accounts.select("account_id", "holder_type"), on="account_id"
    )
    cnpj_for_person = (pl.col("key_type") == "cnpj") & (pl.col("holder_type") == "PF")
    cpf_for_company = (pl.col("key_type") == "cpf") & (pl.col("holder_type") != "PF")
    assert joined.filter(cnpj_for_person).height == 0
    assert joined.filter(cpf_for_company).height == 0


def test_no_account_holds_two_keys_of_the_same_unique_type(population) -> None:
    duplicates = (
        population.pix_keys.filter(pl.col("key_type") != "evp")
        .group_by("account_id", "key_type")
        .agg(pl.len().alias("n"))
        .filter(pl.col("n") > 1)
    )
    assert duplicates.height == 0


def test_key_count_respects_the_configured_maximum(population) -> None:
    per_account = population.pix_keys.group_by("account_id").agg(pl.len().alias("n"))
    assert per_account["n"].max() <= GenerationConfig().population.max_keys_per_account


def test_partners_link_individuals_to_companies(population) -> None:
    individuals = set(population.accounts.filter(pl.col("holder_type") == "PF")["account_id"])
    companies = set(
        population.accounts.filter(pl.col("holder_type").is_in(["PJ", "MEI"]))["account_id"]
    )
    assert population.company_partners.height > 0
    assert set(population.company_partners["partner_account_id"]) <= individuals
    assert set(population.company_partners["company_account_id"]) <= companies


def test_mei_has_exactly_one_partner(population) -> None:
    mei = population.accounts.filter(pl.col("holder_type") == "MEI").select(
        company_account_id="account_id"
    )
    counts = (
        population.company_partners.join(mei, on="company_account_id")
        .group_by("company_account_id")
        .agg(pl.len().alias("n"))
    )
    assert counts.height == mei.height
    assert counts["n"].max() == 1


def test_shared_partner_pairs_are_ordered_and_deduplicated(population) -> None:
    pairs = shared_partner_pairs(population.company_partners)
    if pairs.height:
        assert (pairs["company_a"] < pairs["company_b"]).all()
        assert pairs.select("company_a", "company_b").is_duplicated().sum() == 0


def test_same_seed_produces_an_identical_population() -> None:
    config = GenerationConfig(seed=99, population={"accounts": 300})
    first = generate_population(config)
    second = generate_population(config)
    for name, frame in first.tables().items():
        assert frame.equals(second.tables()[name]), f"{name} is not reproducible"


def test_different_seeds_produce_different_populations() -> None:
    base = generate_population(GenerationConfig(seed=1, population={"accounts": 300}))
    other = generate_population(GenerationConfig(seed=2, population={"accounts": 300}))
    assert not base.accounts.equals(other.accounts)


def test_summary_reports_row_counts(population) -> None:
    summary = population.summary()
    assert summary["accounts"] == 1_200
    assert summary["accounts_PF"] + summary["accounts_PJ"] + summary["accounts_MEI"] == 1_200
