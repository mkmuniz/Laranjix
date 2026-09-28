"""The privacy guarantees of section 5 of the scope document, as tests.

This file holds values that must trip the PII scanner, so it opts out of being
scanned itself: laranjix-pii-fixture
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from laranjix.privacy import identifiers as ident
from laranjix.privacy.scan import FIXTURE_PRAGMA, is_fixture, scan_text, scan_tree
from laranjix.privacy.validators import (
    cnpj_check_digits,
    cpf_check_digits,
    is_valid_cnpj,
    is_valid_cpf,
    is_valid_luhn,
)

SAMPLE = 5_000


@pytest.fixture()
def rng() -> np.random.Generator:
    return np.random.default_rng(20260101)


def _valid_cpf(base: list[int]) -> str:
    """Build a valid CPF from ``base``, so no valid document is hard-coded here."""
    return "".join(str(d) for d in [*base, *cpf_check_digits(base)])


def _valid_cnpj(base: list[int]) -> str:
    return "".join(str(d) for d in [*base, *cnpj_check_digits(base)])


def test_validators_accept_documents_built_from_the_official_algorithm() -> None:
    cpf = _valid_cpf([1, 2, 3, 4, 5, 6, 7, 8, 9])
    cnpj = _valid_cnpj([1, 2, 3, 4, 5, 6, 7, 8, 0, 0, 0, 1])
    assert is_valid_cpf(cpf)
    assert is_valid_cnpj(cnpj)


def test_validators_reject_wrong_check_digits() -> None:
    cpf = _valid_cpf([1, 2, 3, 4, 5, 6, 7, 8, 9])
    cnpj = _valid_cnpj([1, 2, 3, 4, 5, 6, 7, 8, 0, 0, 0, 1])
    assert not is_valid_cpf(cpf[:-1] + str((int(cpf[-1]) + 1) % 10))
    assert not is_valid_cnpj(cnpj[:-1] + str((int(cnpj[-1]) + 1) % 10))
    assert not is_valid_cpf("111.111.111-11")  # repeated digits are rejected
    assert not is_valid_cnpj("11.111.111/1111-11")


def test_luhn_matches_a_constructed_checksum() -> None:
    body = "453957876362148"
    checksum = next(d for d in "0123456789" if is_valid_luhn(body + d))
    assert is_valid_luhn(body + checksum)
    assert not is_valid_luhn(body + str((int(checksum) + 1) % 10))


def test_check_digit_helpers_reject_wrong_length() -> None:
    with pytest.raises(ValueError):
        cpf_check_digits([1, 2, 3])
    with pytest.raises(ValueError):
        cnpj_check_digits([1, 2, 3])


def test_no_generated_cpf_is_valid(rng: np.random.Generator) -> None:
    for _ in range(SAMPLE):
        digits = ident.fake_cpf(rng)
        assert len(digits) == 11
        assert not is_valid_cpf(digits)


def test_no_generated_cnpj_is_valid(rng: np.random.Generator) -> None:
    for _ in range(SAMPLE):
        digits = ident.fake_cnpj(rng)
        assert len(digits) == 14
        assert not is_valid_cnpj(digits)


def test_generated_emails_use_reserved_domains_only(rng: np.random.Generator) -> None:
    for index in range(500):
        address = ident.fake_email(rng, "Maria Souza Lima", index)
        assert address.rsplit("@", 1)[-1] in ident.RESERVED_EMAIL_DOMAINS


def test_generated_phones_are_not_dialable(rng: np.random.Generator) -> None:
    for _ in range(500):
        phone = ident.fake_phone(rng)
        assert phone.startswith(f"+55{ident.FICTITIOUS_AREA_CODE}")
        assert not scan_text(phone, "phone")


def test_institution_labels_are_fictitious() -> None:
    assert ident.institution_id(7) == "inst_07"
    assert "Ficticia" in ident.institution_name(7)


def test_scanner_detects_every_category() -> None:
    cpf = _valid_cpf([1, 2, 3, 4, 5, 6, 7, 8, 9])
    cnpj = _valid_cnpj([1, 2, 3, 4, 5, 6, 7, 8, 0, 0, 0, 1])
    card = "453957876362148" + next(d for d in "0123456789" if is_valid_luhn("453957876362148" + d))
    text = f"cpf {cpf} cnpj {cnpj} card {card} mail alguem@gmail.com fone +55 11 99999-8888"
    kinds = {finding.kind for finding in scan_text(text, "sample")}
    assert kinds == {"valid_cpf", "valid_cnpj", "luhn_card", "non_reserved_email", "dialable_phone"}


def test_scanner_never_echoes_the_full_value() -> None:
    cpf = _valid_cpf([1, 2, 3, 4, 5, 6, 7, 8, 9])
    findings = scan_text(f"cpf {cpf}", "sample")
    assert findings
    assert cpf not in findings[0].value
    assert "*" in findings[0].value


def test_scanner_accepts_synthetic_identifiers(rng: np.random.Generator) -> None:
    values = [
        ident.format_cpf(ident.fake_cpf(rng)),
        ident.format_cnpj(ident.fake_cnpj(rng)),
        ident.fake_email(rng, "Joao Silva", 3),
        ident.fake_phone(rng),
        ident.evp_key(rng),
    ]
    assert scan_text(" ".join(values), "synthetic") == []


def test_uuid_keys_do_not_trip_the_numeric_heuristics(rng: np.random.Generator) -> None:
    # A UUID's hex groups can spell out a Luhn-valid run or a phone-like pattern
    # by accident (found while generating 50k accounts). Both must be ignored.
    keys = [ident.evp_key(rng) for _ in range(20_000)]
    assert scan_text("\n".join(keys), "evp") == []
    assert scan_text("5511456789012345-6789-4abc-8def-0123456789ab", "crafted") == []


def test_the_scanner_module_does_not_exclude_itself() -> None:
    # The module defines FIXTURE_PRAGMA, so the literal appears in its own source.
    from laranjix.privacy import scan as scan_module

    assert not is_fixture(Path(scan_module.__file__))


def test_a_declared_fixture_is_skipped_and_reported(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture.py"
    fixture.write_text(f"# {FIXTURE_PRAGMA}\nalguem@gmail.com\n", encoding="utf-8")
    plain = tmp_path / "plain.py"
    plain.write_text("outra@gmail.com\n", encoding="utf-8")

    skipped: list[Path] = []
    findings = scan_tree(tmp_path, skipped=skipped)
    assert skipped == [fixture]
    assert [finding.path for finding in findings] == [str(plain)]


def test_ssh_remotes_are_not_treated_as_e_mail_addresses() -> None:
    assert scan_text("git clone git@github.com:owner/repo.git", "readme") == []
    assert scan_text("contato: alguem@github.com", "readme")
