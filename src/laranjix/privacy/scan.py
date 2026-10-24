"""PII scanner used by the CLI and by the CI privacy job.

The scanner looks for anything that *could* be real: a document that passes the
official check digits, an e-mail outside the reserved domains, a phone number in
a dialable range, or a card number with a valid Luhn checksum. Any finding fails
the build -- see ``CONTRIBUTING.md``, section 5.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from laranjix.privacy.identifiers import FICTITIOUS_AREA_CODE, RESERVED_EMAIL_DOMAINS
from laranjix.privacy.validators import is_valid_cnpj, is_valid_cpf, is_valid_luhn

TEXT_SUFFIXES = frozenset(
    {".csv", ".tsv", ".json", ".jsonl", ".yaml", ".yml", ".md", ".txt", ".py", ".svg"}
)
TABULAR_SUFFIXES = frozenset({".parquet"})

# Vector geometry is never personal data, but coordinates with many decimals form
# long digit runs that pass the Luhn checksum by accident. These attributes are
# masked so an SVG is still scanned for what can actually carry PII: metadata,
# titles, descriptions, author fields and text nodes.
_SVG_GEOMETRY = re.compile(
    r"\b(?:d|points|viewBox|transform|x|y|x1|y1|x2|y2|cx|cy|r|rx|ry|width|height"
    r"|stroke-width|stroke-dasharray|offset|gradientTransform|patternTransform)"
    r'\s*=\s*"[^"]*"'
)

# A file carrying this marker is skipped entirely. It exists so the scanner's own
# tests can hold values that must trip it. The marker only works inside a test
# directory, so documentation can quote it without excluding itself, and skipped
# files are always reported, so the exclusion is never silent.
FIXTURE_PRAGMA = "laranjix-pii-fixture"
FIXTURE_DIRS = frozenset({"tests", "test"})

# A run preceded by "+" is an E.164 phone number, handled by _BR_PHONE below.
_DIGIT_RUN = re.compile(r"(?<![\d+])(\d[\d.\-/ ]{9,24}\d)(?!\d)")
# A punctuated document is never a card number, so it is only checked as a
# document. Without punctuation a 14-digit run is ambiguous and gets both checks.
_CPF_FORMAT = re.compile(r"^\d{3}\.\d{3}\.\d{3}-\d{2}$")
_CNPJ_FORMAT = re.compile(r"^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$")
# EVP Pix keys are locally generated UUIDs. Their hex groups are joined by
# hyphens, so a digit run can straddle two of them and look like a long card
# number -- or even like a phone number -- by accident. UUIDs are masked out
# before the numeric scans; a real card or phone number is never shaped like a
# UUID, so nothing is lost. E-mail matching still runs on the raw text.
# A hex digest (md5, sha1, sha256) is 32 characters or more and can contain a
# long run of digits that passes Luhn by chance -- the dataset manifest is full
# of them. A card number is at most 19 digits, so masking tokens this long
# cannot hide one.
_HEX_DIGEST = re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{32,}(?![0-9a-fA-F])")
_UUID = re.compile(
    r"(?<![0-9a-fA-F-])[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}"
    r"-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}(?![0-9a-fA-F-])"
)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# "git@host:path" is an SSH remote, not a mailbox. Masked before e-mail matching.
_SSH_REMOTE = re.compile(r"\b[\w.-]+@[\w.-]+(?=:[^\s/])")
# +55 followed by a real area code (11-99) is a dialable Brazilian number.
_BR_PHONE = re.compile(r"(?<!\d)\+?55\s?\(?([1-9][1-9])\)?\s?9?\d{4}[-\s]?\d{4}(?!\d)")


@dataclass(frozen=True)
class Finding:
    """One suspicious value found in one place."""

    path: str
    kind: str
    value: str
    detail: str

    def __str__(self) -> str:
        return f"{self.path}: {self.kind} -> {self.value} ({self.detail})"


def _redact(value: str) -> str:
    """Never echo a possibly-real identifier in full."""
    cleaned = value.strip()
    if len(cleaned) <= 4:
        return "*" * len(cleaned)
    return f"{cleaned[:2]}{'*' * (len(cleaned) - 4)}{cleaned[-2:]}"


def scan_text(text: str, origin: str) -> list[Finding]:
    """Return every finding in ``text``."""
    findings: list[Finding] = []
    numeric_text = _HEX_DIGEST.sub(" ", _UUID.sub(" ", text))

    for match in _DIGIT_RUN.finditer(numeric_text):
        raw = match.group(1).strip()
        digits = re.sub(r"\D", "", raw)
        as_cpf = len(digits) == 11 and not _CNPJ_FORMAT.match(raw)
        as_cnpj = len(digits) == 14 and not _CPF_FORMAT.match(raw)
        as_card = (
            13 <= len(digits) <= 19 and not _CNPJ_FORMAT.match(raw) and not _CPF_FORMAT.match(raw)
        )

        if as_cpf and is_valid_cpf(digits):
            findings.append(
                Finding(origin, "valid_cpf", _redact(digits), "passes official check digits")
            )
        elif as_cnpj and is_valid_cnpj(digits):
            findings.append(
                Finding(origin, "valid_cnpj", _redact(digits), "passes official check digits")
            )
        elif as_card and is_valid_luhn(digits):
            findings.append(Finding(origin, "luhn_card", _redact(digits), "passes Luhn checksum"))

    for match in _EMAIL.finditer(_SSH_REMOTE.sub(" ", text)):
        address = match.group(0)
        domain = address.rsplit("@", 1)[-1].lower()
        if domain not in RESERVED_EMAIL_DOMAINS:
            findings.append(
                Finding(
                    origin,
                    "non_reserved_email",
                    _redact(address),
                    "domain is not reserved by RFC 2606",
                )
            )

    for match in _BR_PHONE.finditer(numeric_text):
        if not match.group(0).replace(" ", "").startswith(f"+55{FICTITIOUS_AREA_CODE}"):
            findings.append(
                Finding(
                    origin,
                    "dialable_phone",
                    _redact(match.group(0)),
                    "area code is a valid Brazilian DDD",
                )
            )

    return findings


def is_fixture(path: Path) -> bool:
    """Return ``True`` if ``path`` opts out of the scan via :data:`FIXTURE_PRAGMA`."""
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return False
    if path.resolve() == Path(__file__).resolve():
        # This module defines the marker, so it would otherwise exclude itself.
        return False
    if not FIXTURE_DIRS.intersection(path.resolve().parts):
        # Outside a test directory the marker is just text -- in the docs that
        # describe it, for instance.
        return False
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:4096]
    except OSError:
        return False
    return FIXTURE_PRAGMA in head


def scan_path(path: Path) -> list[Finding]:
    """Scan one file. Parquet files are read as tables, others as text."""
    suffix = path.suffix.lower()
    origin = str(path)
    if is_fixture(path):
        return []
    if suffix in TABULAR_SUFFIXES:
        import polars as pl

        frame = pl.read_parquet(path)
        text = "\n".join(
            "\t".join("" if value is None else str(value) for value in row)
            for row in frame.iter_rows()
        )
        return scan_text(text, origin)
    if suffix in TEXT_SUFFIXES:
        text = path.read_text(encoding="utf-8", errors="replace")
        if suffix == ".svg":
            text = _SVG_GEOMETRY.sub(" ", text)
        return scan_text(text, origin)
    return []


def scan_tree(
    root: Path,
    ignore: tuple[str, ...] = (".git", ".venv", "__pycache__", "node_modules"),
    skipped: list[Path] | None = None,
) -> list[Finding]:
    """Scan every supported file under ``root``.

    Files that opt out via :data:`FIXTURE_PRAGMA` are appended to ``skipped`` so
    the caller can report them.
    """
    findings: list[Finding] = []
    targets = [root] if root.is_file() else sorted(root.rglob("*"))
    for candidate in targets:
        if not candidate.is_file():
            continue
        if any(part in ignore for part in candidate.parts):
            continue
        if is_fixture(candidate):
            if skipped is not None:
                skipped.append(candidate)
            continue
        findings.extend(scan_path(candidate))
    return findings
