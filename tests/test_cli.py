from __future__ import annotations

import json

import polars as pl
from typer.testing import CliRunner

from laranjix import __version__
from laranjix.cli import app
from laranjix.privacy.validators import cpf_check_digits

runner = CliRunner()


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_calibration_command_lists_sources() -> None:
    result = runner.invoke(app, ["calibration"])
    assert result.exit_code == 0
    assert "population_uf" in result.stdout
    assert "fingerprint:" in result.stdout


def test_generate_population_writes_tables_and_manifest(tmp_path) -> None:
    result = runner.invoke(
        app, ["generate-population", "-n", "300", "--seed", "5", "-o", str(tmp_path)]
    )
    assert result.exit_code == 0, result.stdout
    assert "privacidade: nenhum achado." in result.stdout

    for name in ("accounts", "pix_keys", "company_partners", "institutions"):
        assert (tmp_path / f"{name}.parquet").exists()
        assert (tmp_path / f"{name}.csv").exists()

    assert pl.read_parquet(tmp_path / "accounts.parquet").height == 300


def test_manifest_records_everything_needed_to_reproduce(tmp_path) -> None:
    runner.invoke(app, ["generate-population", "-n", "120", "--seed", "11", "-o", str(tmp_path)])
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["seed"] == 11
    assert manifest["config"]["population"]["accounts"] == 120
    assert manifest["synthetic"] is True
    assert manifest["row_counts"]["accounts"] == 120
    assert len(manifest["calibration"]["fingerprint"]) == 64
    assert "population_uf" in manifest["calibration"]["provisional"]
    assert manifest["files"]["accounts.parquet"]["bytes"] > 0
    assert len(manifest["files"]["accounts.parquet"]["sha256"]) == 64


def test_generation_is_byte_identical_for_the_same_seed(tmp_path) -> None:
    first, second = tmp_path / "a", tmp_path / "b"
    for target in (first, second):
        runner.invoke(app, ["generate-population", "-n", "200", "--seed", "42", "-o", str(target)])
    assert (first / "accounts.csv").read_bytes() == (second / "accounts.csv").read_bytes()


def test_privacy_check_fails_on_a_valid_document(tmp_path) -> None:
    base = [1, 2, 3, 4, 5, 6, 7, 8, 9]
    cpf = "".join(str(d) for d in [*base, *cpf_check_digits(base)])
    target = tmp_path / "leak.csv"
    target.write_text(f"holder_id\n{cpf}\n", encoding="utf-8")
    result = runner.invoke(app, ["privacy-check", str(target)])
    assert result.exit_code == 1


def test_privacy_check_accepts_several_paths(tmp_path) -> None:
    first, second = tmp_path / "a.csv", tmp_path / "b.csv"
    first.write_text("a\n1\n", encoding="utf-8")
    second.write_text("b\n2\n", encoding="utf-8")
    result = runner.invoke(app, ["privacy-check", str(first), str(second)])
    assert result.exit_code == 0, result.stdout


def test_privacy_check_passes_on_generated_output(tmp_path) -> None:
    runner.invoke(app, ["generate-population", "-n", "150", "-o", str(tmp_path)])
    result = runner.invoke(app, ["privacy-check", str(tmp_path)])
    assert result.exit_code == 0, result.stdout


def test_config_file_drives_the_run(tmp_path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"seed: 3\nformats: [csv]\noutput_dir: {tmp_path / 'ds'}\npopulation:\n  accounts: 80\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["generate-population", "-c", str(config_path)])
    assert result.exit_code == 0, result.stdout
    assert (tmp_path / "ds" / "accounts.csv").exists()
    assert not (tmp_path / "ds" / "accounts.parquet").exists()
