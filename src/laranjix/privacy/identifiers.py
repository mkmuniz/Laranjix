"""Generators for identifiers that cannot collide with anything real.

Every function here is built around one rule: an identifier produced by Laranjix
must be impossible to confuse with a real person, company, phone line, mailbox or
financial institution. The strategies are documented in ``docs/privacy.md`` and
enforced by ``tests/test_privacy.py`` plus the CI privacy job.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from laranjix.privacy.validators import cnpj_check_digits, cpf_check_digits

if TYPE_CHECKING:  # pragma: no cover
    import numpy as np

# RFC 2606 reserves these second-level domains for documentation and examples.
# They can never be registered, so a generated address can never reach anyone.
RESERVED_EMAIL_DOMAINS = ("example.com", "example.org", "example.net")

# Brazilian area codes ("DDD") always start at 11. A leading zero is not a valid
# area code and never will be, so "+55 00 ..." cannot be dialled.
FICTITIOUS_AREA_CODE = "00"


def _shift_digit(digit: int) -> int:
    """Return a digit guaranteed to differ from ``digit``."""
    return (digit + 1) % 10


def fake_cpf(rng: np.random.Generator) -> str:
    """Return an 11-digit CPF whose check digits are wrong on purpose.

    The nine leading digits are random, then both official check digits are
    computed and replaced by different values. The result fails
    :func:`laranjix.privacy.validators.is_valid_cpf`, so it cannot be the CPF of
    any real person.
    """
    base = [int(d) for d in rng.integers(0, 10, size=9)]
    if len(set(base)) == 1:  # avoid 000000000-style sequences
        base[0] = _shift_digit(base[0])
    first, second = cpf_check_digits(base)
    digits = [*base, _shift_digit(first), _shift_digit(second)]
    return "".join(str(d) for d in digits)


def fake_cnpj(rng: np.random.Generator, branch: int = 1) -> str:
    """Return a 14-digit CNPJ whose check digits are wrong on purpose."""
    root = [int(d) for d in rng.integers(0, 10, size=8)]
    if len(set(root)) == 1:
        root[0] = _shift_digit(root[0])
    base = root + [int(d) for d in f"{branch:04d}"]
    first, second = cnpj_check_digits(base)
    digits = [*base, _shift_digit(first), _shift_digit(second)]
    return "".join(str(d) for d in digits)


def fake_name(
    rng: np.random.Generator,
    given_names: list[str],
    surnames: list[str],
    surname_count: int = 2,
) -> str:
    """Return a combinatorial personal name.

    A name on its own carries no personal data: it is never paired with a valid
    document, an address or any real attribute.
    """
    given = str(rng.choice(given_names))
    chosen = rng.choice(surnames, size=surname_count, replace=False)
    return " ".join([given] + [str(s) for s in chosen])


def fake_company_name(
    rng: np.random.Generator,
    surnames: list[str],
    branches: list[str],
    suffixes: list[str],
) -> str:
    """Return a fictitious company name, e.g. ``Almeida Comercio LTDA``."""
    return " ".join(
        [
            str(rng.choice(surnames)),
            str(rng.choice(branches)),
            str(rng.choice(suffixes)),
        ]
    )


def fake_email(rng: np.random.Generator, name: str, salt: int) -> str:
    """Return an address in an RFC 2606 reserved domain."""
    parts = [part for part in name.lower().split() if part]
    local = ".".join(parts[:2]) if parts else "conta"
    local = "".join(char for char in local if char.isalnum() or char == ".")
    domain = str(rng.choice(list(RESERVED_EMAIL_DOMAINS)))
    return f"{local}{salt:04d}@{domain}"


def fake_phone(rng: np.random.Generator) -> str:
    """Return a phone number in E.164-like shape that cannot be dialled.

    The area code is ``00``, which is not a valid Brazilian DDD, so the number
    does not exist in any numbering plan. Resolves open question 1 of the scope
    document; see ``docs/privacy.md``.
    """
    subscriber = "".join(str(int(d)) for d in rng.integers(0, 10, size=8))
    return f"+55{FICTITIOUS_AREA_CODE}9{subscriber}"


def evp_key(rng: np.random.Generator) -> str:
    """Return a locally generated random Pix key (EVP), as a UUIDv4 string."""
    return str(uuid.UUID(bytes=bytes(rng.integers(0, 256, size=16, dtype="uint8")), version=4))


def institution_id(index: int) -> str:
    """Return a fictitious institution id. Never a real bank code or ISPB."""
    return f"inst_{index:02d}"


def institution_name(index: int) -> str:
    """Return a fictitious institution display name."""
    return f"Instituicao Ficticia {index:02d}"


def account_id(index: int) -> str:
    return f"acc_{index:06d}"


def format_cpf(digits: str) -> str:
    return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"


def format_cnpj(digits: str) -> str:
    return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"
