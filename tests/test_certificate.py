"""The certificate must be recomputable and must fail when the dataset is wrong.

One test plants an address the PII scanner has to catch, so this file opts out of
being scanned itself: laranjix-pii-fixture
"""

from __future__ import annotations

import json

import numpy as np
import pytest
from typer.testing import CliRunner

from laranjix.cli import app
from laranjix.validation.certificate import CERTIFICATE_JSON, CERTIFICATE_NAME, build_certificate
from laranjix.validation.render import render_markdown
from laranjix.validation.tstr import TstrStatus, run_tstr, tstr_not_applicable

runner = CliRunner()


@pytest.fixture(scope="module")
def dataset(tmp_path_factory):
    target = tmp_path_factory.mktemp("dataset")
    result = runner.invoke(
        app, ["generate-population", "-n", "3000", "--seed", "42", "-o", str(target)]
    )
    assert result.exit_code == 0, result.stdout
    return target


def test_certificate_passes_on_a_freshly_generated_dataset(dataset) -> None:
    certificate = build_certificate(dataset)
    assert certificate.privacy.passed
    assert certificate.reproducibility.passed
    assert certificate.fidelity.passed
    assert certificate.passed


def test_privacy_section_counts_every_document(dataset) -> None:
    certificate = build_certificate(dataset)
    evidence = certificate.privacy.evidence
    assert evidence["documents_checked"] == 3000
    assert evidence["valid_documents_found"] == 0
    assert evidence["pii_findings"] == 0


def test_reproducibility_section_regenerates_and_compares_hashes(dataset) -> None:
    certificate = build_certificate(dataset)
    evidence = certificate.reproducibility.evidence
    assert evidence["files_compared"] > 0
    assert evidence["files_matching"] == evidence["files_compared"]
    assert evidence["mismatches"] == []


def test_reproducibility_fails_on_a_tampered_manifest(dataset, tmp_path) -> None:
    import shutil

    copy = tmp_path / "tampered"
    shutil.copytree(dataset, copy)
    manifest_path = copy / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["config"]["seed"] = manifest["config"]["seed"] + 1
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    certificate = build_certificate(copy)
    assert not certificate.reproducibility.passed
    assert not certificate.passed


def test_tstr_is_pending_until_fraud_labels_exist(dataset) -> None:
    certificate = build_certificate(dataset)
    assert certificate.tstr.status is TstrStatus.PENDING_LABELS
    assert "Marco 4" in certificate.tstr.detail


def test_markdown_states_the_result_and_the_limits(dataset) -> None:
    markdown = render_markdown(build_certificate(dataset))
    assert "# Certificado de qualidade do dataset" in markdown
    assert "Resultado: PASSOU" in markdown
    assert "nao afirma" in markdown.lower()
    assert "laranjix certify" in markdown


def test_certify_command_writes_both_files(dataset) -> None:
    result = runner.invoke(app, ["certify", str(dataset)])
    assert result.exit_code == 0, result.stdout
    assert (dataset / CERTIFICATE_NAME).exists()

    payload = json.loads((dataset / CERTIFICATE_JSON).read_text(encoding="utf-8"))
    assert payload["passed"] is True
    assert payload["privacy"]["evidence"]["valid_documents_found"] == 0
    assert payload["fidelity"]["passed"] is True
    assert payload["utility_tstr"]["status"] == "pending_labels"


def test_certify_exits_nonzero_when_a_section_fails(dataset, tmp_path) -> None:
    import shutil

    copy = tmp_path / "broken"
    shutil.copytree(dataset, copy)
    (copy / "leak.csv").write_text("email\nalguem@gmail.com\n", encoding="utf-8")
    result = runner.invoke(app, ["certify", str(copy), "--no-write"])
    assert result.exit_code == 1


# -- TSTR ---------------------------------------------------------------------


def test_tstr_measures_utility_on_a_separable_task() -> None:
    rng = np.random.default_rng(0)

    def make(size: int, shift: float) -> tuple[np.ndarray, np.ndarray]:
        labels = (rng.random(size) < 0.03).astype(int)
        features = rng.normal(size=(size, 5))
        features[labels == 1] += 1.5 + shift
        return features, labels

    synthetic_x, synthetic_y = make(8_000, 0.0)
    real_x, real_y = make(4_000, 0.2)

    result = run_tstr(synthetic_x, synthetic_y, real_x, real_y)
    assert result.status is TstrStatus.OK
    assert result.tstr_average_precision > result.baseline_average_precision
    assert 0.0 < (result.utility_ratio or 0.0) <= 1.5


def test_tstr_reports_mismatched_feature_shapes() -> None:
    rng = np.random.default_rng(1)
    synthetic_x, synthetic_y = rng.normal(size=(200, 4)), (rng.random(200) < 0.3).astype(int)
    real_x, real_y = rng.normal(size=(200, 6)), (rng.random(200) < 0.3).astype(int)
    result = run_tstr(synthetic_x, synthetic_y, real_x, real_y)
    assert result.status is TstrStatus.MISSING_REFERENCE


def test_tstr_needs_both_classes() -> None:
    rng = np.random.default_rng(2)
    features = rng.normal(size=(100, 3))
    result = run_tstr(features, np.zeros(100), features, np.ones(100))
    assert result.status is TstrStatus.PENDING_LABELS


def test_not_applicable_carries_its_reason() -> None:
    result = tstr_not_applicable("sem rotulos")
    assert result.status is TstrStatus.PENDING_LABELS
    assert result.utility_ratio is None
    assert result.as_dict()["tstr_average_precision"] is None
