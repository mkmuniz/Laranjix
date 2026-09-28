"""The dataset quality certificate.

A certificate is what a user of a Laranjix dataset can check for themselves. It
is produced from a dataset directory, not from the generator's memory, and every
line in it is recomputed at verification time: the documents are re-validated,
the files are re-scanned, the dataset is regenerated from its own manifest and
the hashes are compared, and the distributions are re-measured against the
calibration targets.

It is deliberately explicit about what it does *not* establish. A dataset can
pass every check here and still be a poor model of Brazil, because the fidelity
checks compare the data against the calibration parameters, not against reality;
whether those parameters are realistic is a separate question, and the
certificate names the ones still marked provisional.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl

from laranjix import __version__
from laranjix.calibration.loader import Calibration, load_calibration
from laranjix.config import GenerationConfig
from laranjix.manifest import MANIFEST_NAME, file_sha256
from laranjix.population.generator import Population
from laranjix.privacy.scan import scan_tree
from laranjix.privacy.validators import is_valid_cnpj, is_valid_cpf
from laranjix.validation.checks import population_fidelity
from laranjix.validation.fidelity import FidelityReport
from laranjix.validation.tstr import TstrResult, tstr_not_applicable

TABLES = ("accounts", "pix_keys", "company_partners", "institutions")
CERTIFICATE_NAME = "certificate.md"
CERTIFICATE_JSON = "certificate.json"


@dataclass(frozen=True)
class SectionResult:
    """One pass/fail section of the certificate."""

    name: str
    passed: bool
    detail: str
    evidence: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "detail": self.detail,
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class Certificate:
    """Everything the certificate asserts about one dataset."""

    dataset: str
    issued_at: str
    laranjix_version: str
    manifest: dict[str, Any]
    privacy: SectionResult
    reproducibility: SectionResult
    fidelity: FidelityReport
    tstr: TstrResult

    @property
    def passed(self) -> bool:
        return self.privacy.passed and self.reproducibility.passed and self.fidelity.passed

    def as_dict(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset,
            "issued_at": self.issued_at,
            "laranjix_version": self.laranjix_version,
            "passed": self.passed,
            "seed": self.manifest.get("seed"),
            "row_counts": self.manifest.get("row_counts", {}),
            "calibration_fingerprint": self.manifest.get("calibration", {}).get("fingerprint"),
            "provisional_parameters": self.manifest.get("calibration", {}).get("provisional", []),
            "privacy": self.privacy.as_dict(),
            "reproducibility": self.reproducibility.as_dict(),
            "fidelity": self.fidelity.as_dict(),
            "utility_tstr": self.tstr.as_dict(),
        }


def load_population(directory: Path) -> Population:
    """Rebuild a :class:`Population` from the Parquet files in ``directory``."""
    frames: dict[str, pl.DataFrame] = {}
    for table in TABLES:
        path = directory / f"{table}.parquet"
        if not path.exists():
            raise FileNotFoundError(f"tabela ausente no dataset: {path.name}")
        frames[table] = pl.read_parquet(path)
    return Population(
        accounts=frames["accounts"],
        pix_keys=frames["pix_keys"],
        company_partners=frames["company_partners"],
        institutions=frames["institutions"],
    )


def check_privacy(directory: Path, population: Population) -> SectionResult:
    """Re-validate every document and re-scan every file in the dataset."""
    valid_documents = 0
    for holder_type, holder_id in population.accounts.select(
        "holder_type", "holder_id"
    ).iter_rows():
        checker = is_valid_cpf if holder_type == "PF" else is_valid_cnpj
        if checker(holder_id):
            valid_documents += 1

    findings = scan_tree(directory)
    passed = valid_documents == 0 and not findings
    return SectionResult(
        name="Privacidade",
        passed=passed,
        detail=(
            "nenhum documento valido e nenhum achado de PII"
            if passed
            else f"{valid_documents} documento(s) valido(s), {len(findings)} achado(s) de PII"
        ),
        evidence={
            "documents_checked": population.accounts.height,
            "valid_documents_found": valid_documents,
            "pii_findings": len(findings),
            "finding_kinds": sorted({finding.kind for finding in findings}),
        },
    )


def check_reproducibility(
    directory: Path, manifest: dict[str, Any], calibration: Calibration
) -> SectionResult:
    """Regenerate the dataset from its own manifest and compare file hashes."""
    from laranjix.exporters import write_tables
    from laranjix.population import generate_population

    try:
        config = GenerationConfig.model_validate(manifest["config"])
    except Exception as error:
        return SectionResult(
            name="Reprodutibilidade",
            passed=False,
            detail=f"config do manifest nao pode ser lida: {error}",
            evidence={},
        )

    import tempfile

    recorded: dict[str, Any] = manifest.get("files", {})
    with tempfile.TemporaryDirectory() as temporary:
        target = Path(temporary)
        population = generate_population(config, calibration)
        write_tables(population.tables(), target, config.formats)

        compared: dict[str, bool] = {}
        for name, entry in sorted(recorded.items()):
            rebuilt = target / name
            compared[name] = rebuilt.exists() and file_sha256(rebuilt) == entry.get("sha256")

    mismatches = sorted(name for name, same in compared.items() if not same)
    passed = bool(compared) and not mismatches
    return SectionResult(
        name="Reprodutibilidade",
        passed=passed,
        detail=(
            f"a seed {config.seed} reproduziu {len(compared)} arquivo(s) byte a byte"
            if passed
            else (
                "arquivos diferentes ao regerar: "
                + (", ".join(mismatches) or "nenhum arquivo no manifest")
            )
        ),
        evidence={
            "seed": config.seed,
            "files_compared": len(compared),
            "files_matching": sum(compared.values()),
            "mismatches": mismatches,
        },
    )


def build_certificate(
    directory: Path,
    calibration: Calibration | None = None,
    tstr: TstrResult | None = None,
) -> Certificate:
    """Produce the certificate for the dataset in ``directory``."""
    params = calibration or load_calibration()
    manifest_path = directory / MANIFEST_NAME
    if not manifest_path.exists():
        raise FileNotFoundError(f"{MANIFEST_NAME} nao encontrado em {directory}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    population = load_population(directory)
    return Certificate(
        dataset=str(directory),
        issued_at=datetime.now(UTC).isoformat(timespec="seconds"),
        laranjix_version=__version__,
        manifest=manifest,
        privacy=check_privacy(directory, population),
        reproducibility=check_reproducibility(directory, manifest, params),
        fidelity=population_fidelity(population, params),
        tstr=tstr
        or tstr_not_applicable(
            "o dataset ainda nao tem rotulos de fraude; TSTR entra com o Marco 4"
        ),
    )
