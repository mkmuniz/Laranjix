"""Official Brazilian document validators.

These implement the *real* CPF and CNPJ check-digit algorithms. The Laranjix
generators never use them to build identifiers -- they exist so tests and CI can
prove that every generated document is **invalid** by the official rules, and
therefore cannot belong to a real person or company.

See ``docs/privacy.md``.
"""

from __future__ import annotations

import re

CPF_DIGITS = 11
CNPJ_DIGITS = 14

_NON_DIGITS = re.compile(r"\D")


def strip_punctuation(value: str) -> str:
    """Return only the digits of ``value``."""
    return _NON_DIGITS.sub("", value)


def _weighted_remainder(digits: list[int], start_weight: int) -> int:
    """Modulus-11 check digit used by both CPF and CNPJ."""
    weights = range(start_weight, 1, -1)
    total = sum(digit * weight for digit, weight in zip(digits, weights, strict=True))
    remainder = total % 11
    return 0 if remainder < 2 else 11 - remainder


def cpf_check_digits(base: list[int]) -> tuple[int, int]:
    """Return the two valid check digits for the 9 leading CPF digits."""
    if len(base) != CPF_DIGITS - 2:
        raise ValueError(f"CPF base must have {CPF_DIGITS - 2} digits, got {len(base)}")
    first = _weighted_remainder(base, 10)
    second = _weighted_remainder([*base, first], 11)
    return first, second


def is_valid_cpf(value: str) -> bool:
    """Return ``True`` if ``value`` is a valid CPF by the official algorithm."""
    digits = strip_punctuation(value)
    if len(digits) != CPF_DIGITS or len(set(digits)) == 1:
        return False
    numbers = [int(char) for char in digits]
    return tuple(numbers[9:]) == cpf_check_digits(numbers[:9])


_CNPJ_WEIGHTS_FIRST = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
_CNPJ_WEIGHTS_SECOND = [6, *_CNPJ_WEIGHTS_FIRST]


def _cnpj_digit(digits: list[int], weights: list[int]) -> int:
    remainder = sum(d * w for d, w in zip(digits, weights, strict=True)) % 11
    return 0 if remainder < 2 else 11 - remainder


def cnpj_check_digits(base: list[int]) -> tuple[int, int]:
    """Return the two valid check digits for the 12 leading CNPJ digits."""
    if len(base) != CNPJ_DIGITS - 2:
        raise ValueError(f"CNPJ base must have {CNPJ_DIGITS - 2} digits, got {len(base)}")
    first = _cnpj_digit(base, _CNPJ_WEIGHTS_FIRST)
    second = _cnpj_digit([*base, first], _CNPJ_WEIGHTS_SECOND)
    return first, second


def is_valid_cnpj(value: str) -> bool:
    """Return ``True`` if ``value`` is a valid CNPJ by the official algorithm."""
    digits = strip_punctuation(value)
    if len(digits) != CNPJ_DIGITS or len(set(digits)) == 1:
        return False
    numbers = [int(char) for char in digits]
    return tuple(numbers[12:]) == cnpj_check_digits(numbers[:12])


def is_valid_luhn(value: str) -> bool:
    """Return ``True`` if ``value`` passes the Luhn checksum (card numbers)."""
    digits = [int(char) for char in strip_punctuation(value)]
    if len(digits) < 12:
        return False
    total = 0
    for index, digit in enumerate(reversed(digits)):
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0
