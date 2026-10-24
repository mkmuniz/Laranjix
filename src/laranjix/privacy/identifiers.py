"""Generators for identifiers that cannot collide with anything real.

Every function here is built around one rule: an identifier produced by Laranjix
must be impossible to confuse with a real person, company, phone line, mailbox or
financial institution. The strategies are documented in ``docs/privacy.md`` and
enforced by ``tests/test_privacy.py`` plus the CI privacy job.

Everything is generated in batches. The population stage asks for hundreds of
thousands of identifiers at once, and a per-row Python call costs far more than
the arithmetic it performs.
"""

from __future__ import annotations

import numpy as np

# RFC 2606 reserves these second-level domains for documentation and examples.
# They can never be registered, so a generated address can never reach anyone.
RESERVED_EMAIL_DOMAINS = ("example.com", "example.org", "example.net")

# Brazilian area codes ("DDD") always start at 11. A leading zero is not a valid
# area code and never will be, so "+55 00 ..." cannot be dialled.
FICTITIOUS_AREA_CODE = "00"

_DIGIT_ASCII = np.frombuffer(b"0123456789", dtype=np.uint8)
_HEX_ASCII = np.frombuffer(b"0123456789abcdef", dtype=np.uint8)

# Modulus-11 weights of the official check-digit algorithms. They appear here
# only to compute the correct digits, so they can be replaced by wrong ones.
_CPF_WEIGHTS_FIRST = np.arange(10, 1, -1)
_CPF_WEIGHTS_SECOND = np.arange(11, 1, -1)
_CNPJ_WEIGHTS_FIRST = np.array([5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
_CNPJ_WEIGHTS_SECOND = np.concatenate(([6], _CNPJ_WEIGHTS_FIRST))


def _check_digit(digits: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """Vectorised modulus-11 check digit, one per row of ``digits``."""
    remainder = (digits * weights).sum(axis=1) % 11
    return np.where(remainder < 2, 0, 11 - remainder)


def _as_text(
    values: np.ndarray,
    alphabet: np.ndarray = _DIGIT_ASCII,
    separators: dict[int, str] | None = None,
) -> np.ndarray:
    """Render an (n, k) matrix of symbol indices as fixed-width strings.

    Going through ASCII codes and viewing the buffer as bytes keeps the whole
    conversion inside NumPy. Formatting row by row in Python costs more than the
    arithmetic that produced the symbols.
    """
    rows, width = values.shape
    total = width + len(separators or {})
    buffer = np.empty((rows, total), dtype=np.uint8)

    column = 0
    for position in range(width):
        if separators and position in separators:
            buffer[:, column] = ord(separators[position])
            column += 1
        buffer[:, column] = alphabet[values[:, position]]
        column += 1

    return buffer.view(f"S{total}").reshape(rows).astype("U")


def _break_repeated_digits(base: np.ndarray) -> np.ndarray:
    """Avoid 000.000.000-style runs, which read as placeholder rather than fake."""
    uniform = (base == base[:, :1]).all(axis=1)
    base[uniform, 0] = (base[uniform, 0] + 1) % 10
    return base


def fake_cpf(rng: np.random.Generator, size: int, formatted: bool = True) -> np.ndarray:
    """Return ``size`` CPFs whose check digits are wrong on purpose.

    The nine leading digits are random, then both official check digits are
    computed and replaced by different values. Every result fails
    :func:`laranjix.privacy.validators.is_valid_cpf`, so none can be the CPF of
    a real person.
    """
    base = _break_repeated_digits(rng.integers(0, 10, size=(size, 9)))
    first = _check_digit(base, _CPF_WEIGHTS_FIRST)
    second = _check_digit(np.column_stack([base, first]), _CPF_WEIGHTS_SECOND)

    digits = np.column_stack([base, (first + 1) % 10, (second + 1) % 10])
    return _as_text(digits, separators={3: ".", 6: ".", 9: "-"} if formatted else None)


def fake_cnpj(
    rng: np.random.Generator, size: int, branch: int = 1, formatted: bool = True
) -> np.ndarray:
    """Return ``size`` CNPJs whose check digits are wrong on purpose."""
    root = _break_repeated_digits(rng.integers(0, 10, size=(size, 8)))
    branch_digits = np.tile([int(digit) for digit in f"{branch:04d}"], (size, 1))
    base = np.column_stack([root, branch_digits])

    first = _check_digit(base, _CNPJ_WEIGHTS_FIRST)
    second = _check_digit(np.column_stack([base, first]), _CNPJ_WEIGHTS_SECOND)

    digits = np.column_stack([base, (first + 1) % 10, (second + 1) % 10])
    separators = {2: ".", 5: ".", 8: "/", 12: "-"} if formatted else None
    return _as_text(digits, separators=separators)


def _join(parts: list[np.ndarray], separator: str = " ") -> np.ndarray:
    joined = parts[0]
    for part in parts[1:]:
        joined = np.char.add(np.char.add(joined, separator), part)
    return joined


def _sample(rng: np.random.Generator, values: list[str], size: int) -> np.ndarray:
    """Draw ``size`` items from ``values`` by index.

    ``rng.choice`` over a list of strings is an order of magnitude slower than
    drawing integers and indexing, and this runs once per account.
    """
    return np.asarray(values)[rng.integers(0, len(values), size=size)]


def fake_name(
    rng: np.random.Generator,
    size: int,
    given_names: list[str],
    surnames: list[str],
    surname_count: int = 2,
) -> np.ndarray:
    """Return ``size`` combinatorial personal names.

    A name on its own carries no personal data: it is never paired with a valid
    document, an address or any real attribute.
    """
    parts = [_sample(rng, given_names, size)]
    parts.extend(_sample(rng, surnames, size) for _ in range(surname_count))
    return _join(parts)


def fake_company_name(
    rng: np.random.Generator,
    size: int,
    surnames: list[str],
    branches: list[str],
    suffixes: list[str],
) -> np.ndarray:
    """Return ``size`` fictitious company names, e.g. ``Almeida Comercio LTDA``."""
    return _join([_sample(rng, values, size) for values in (surnames, branches, suffixes)])


def fake_email(rng: np.random.Generator, names: np.ndarray, salt_offset: int = 0) -> np.ndarray:
    """Return one address per name, in an RFC 2606 reserved domain."""
    size = names.size
    local = np.char.lower(np.char.replace(np.asarray(names, dtype="U"), " ", "."))
    salt = np.char.mod("%04d", np.arange(salt_offset, salt_offset + size))
    domain = _sample(rng, list(RESERVED_EMAIL_DOMAINS), size)
    addresses: np.ndarray = np.char.add(np.char.add(np.char.add(local, salt), "@"), domain)
    return addresses


def fake_phone(rng: np.random.Generator, size: int) -> np.ndarray:
    """Return ``size`` phone numbers that cannot be dialled.

    The area code is ``00``, which is not a valid Brazilian DDD, so the number
    does not exist in any numbering plan. Resolves open question 1 of the scope
    document; see ``docs/privacy.md``.
    """
    subscriber = _as_text(rng.integers(0, 10, size=(size, 8)))
    numbers: np.ndarray = np.char.add(f"+55{FICTITIOUS_AREA_CODE}9", subscriber)
    return numbers


def evp_key(rng: np.random.Generator, size: int) -> np.ndarray:
    """Return ``size`` locally generated random Pix keys (EVP), as UUIDv4 strings."""
    nibbles = rng.integers(0, 16, size=(size, 32))
    nibbles[:, 12] = 4  # version
    nibbles[:, 16] = rng.integers(8, 12, size=size)  # RFC 4122 variant
    return _as_text(nibbles, _HEX_ASCII, separators={8: "-", 12: "-", 16: "-", 20: "-"})


def institution_id(index: int) -> str:
    """Return a fictitious institution id. Never a real bank code or ISPB."""
    return f"inst_{index:02d}"


def institution_name(index: int) -> str:
    """Return a fictitious institution display name."""
    return f"Instituicao Ficticia {index:02d}"


def account_id(index: int) -> str:
    return f"acc_{index:06d}"


def account_ids(size: int) -> np.ndarray:
    """Return ``acc_000001`` .. ``acc_<size>`` as an array."""
    return np.char.mod("acc_%06d", np.arange(1, size + 1))
