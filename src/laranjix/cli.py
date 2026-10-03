"""Command line interface."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from laranjix import __version__
from laranjix.calibration.loader import load_calibration
from laranjix.config import GenerationConfig
from laranjix.exporters import write_tables
from laranjix.manifest import build_manifest, write_manifest
from laranjix.population import generate_population
from laranjix.privacy.scan import scan_tree
from laranjix.validation.certificate import CERTIFICATE_JSON, CERTIFICATE_NAME, build_certificate
from laranjix.validation.render import render_markdown

app = typer.Typer(
    add_completion=False,
    help="Gerador de datasets sinteticos de transacoes financeiras brasileiras.",
)


def _load_config(
    config_path: Path | None,
    seed: int | None,
    accounts: int | None,
    output_dir: Path | None,
) -> GenerationConfig:
    config = GenerationConfig.from_yaml(config_path) if config_path else GenerationConfig()
    overrides: dict[str, Any] = {}
    if seed is not None:
        overrides["seed"] = seed
    if accounts is not None:
        overrides["population"] = config.population.model_copy(update={"accounts": accounts})
    if output_dir is not None:
        overrides["output_dir"] = output_dir
    return config.model_copy(update=overrides) if overrides else config


@app.command()
def version() -> None:
    """Mostra a versao instalada."""
    typer.echo(__version__)


@app.command("generate-population")
def generate_population_command(
    config_path: Path | None = typer.Option(
        None, "--config", "-c", exists=True, dir_okay=False, help="Arquivo YAML de configuracao."
    ),
    seed: int | None = typer.Option(None, "--seed", help="Sobrescreve a seed da config."),
    accounts: int | None = typer.Option(
        None, "--accounts", "-n", min=1, help="Sobrescreve o numero de contas."
    ),
    output_dir: Path | None = typer.Option(
        None, "--out", "-o", help="Diretorio de saida (padrao: out/)."
    ),
    check_privacy: bool = typer.Option(
        True, "--check-privacy/--no-check-privacy", help="Roda o scanner de PII na saida."
    ),
) -> None:
    """Gera a populacao de contas, chaves Pix e sociedades (Marco 2)."""
    config = _load_config(config_path, seed, accounts, output_dir)
    calibration = load_calibration()

    population = generate_population(config, calibration)
    tables = population.tables()
    files = write_tables(tables, config.output_dir, config.formats)

    manifest = build_manifest(config, calibration, files, population.summary())
    manifest_path = write_manifest(config.output_dir, manifest)

    for name, frame in tables.items():
        typer.echo(f"{name:18} {frame.height:>9,} linhas")
    typer.echo(f"manifest           {manifest_path}")
    if calibration.provisional_ids():
        typer.secho(
            "aviso: parametros provisorios em uso -> "
            + ", ".join(calibration.provisional_ids())
            + " (ver Marco 1)",
            fg=typer.colors.YELLOW,
        )

    if check_privacy:
        findings = scan_tree(config.output_dir)
        if findings:
            for finding in findings[:20]:
                typer.secho(str(finding), fg=typer.colors.RED, err=True)
            typer.secho(f"FALHOU: {len(findings)} achado(s) de PII.", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)
        typer.secho("privacidade: nenhum achado.", fg=typer.colors.GREEN)


@app.command("privacy-check")
def privacy_check_command(
    paths: list[Path] = typer.Argument(
        ..., exists=True, help="Arquivos ou diretorios a verificar."
    ),
) -> None:
    """Procura dados que possam ser reais em arquivos gerados ou no repositorio."""
    skipped: list[Path] = []
    findings = [finding for path in paths for finding in scan_tree(path, skipped=skipped)]
    for fixture in skipped:
        typer.secho(f"ignorado (fixture declarada): {fixture}", fg=typer.colors.YELLOW)
    for finding in findings:
        typer.secho(str(finding), fg=typer.colors.RED, err=True)
    if findings:
        typer.secho(f"FALHOU: {len(findings)} achado(s).", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    typer.secho(f"OK: nenhum achado em {len(paths)} caminho(s).", fg=typer.colors.GREEN)


@app.command("certify")
def certify_command(
    dataset_dir: Path = typer.Argument(
        ..., exists=True, file_okay=False, help="Diretorio do dataset a certificar."
    ),
    write: bool = typer.Option(
        True, "--write/--no-write", help="Escreve certificate.md e certificate.json no dataset."
    ),
    show: bool = typer.Option(False, "--show", help="Imprime o certificado inteiro."),
) -> None:
    """Emite o certificado de qualidade de um dataset ja gerado."""
    import json

    certificate = build_certificate(dataset_dir)
    markdown = render_markdown(certificate)

    if write:
        (dataset_dir / CERTIFICATE_NAME).write_text(markdown, encoding="utf-8")
        (dataset_dir / CERTIFICATE_JSON).write_text(
            json.dumps(certificate.as_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    if show:
        typer.echo(markdown)
    else:
        for section in (certificate.privacy, certificate.reproducibility):
            colour = typer.colors.GREEN if section.passed else typer.colors.RED
            typer.secho(f"{section.name:<20} {section.detail}", fg=colour)
        report = certificate.fidelity
        worst = report.worst
        colour = typer.colors.GREEN if report.passed else typer.colors.RED
        detail = (
            f"{len(report.checks)} distribuicoes, pior caso {worst.ratio:.1f}x o ruido"
            if worst
            else "nenhuma distribuicao verificada"
        )
        typer.secho(f"{'Fidelidade':<20} {detail}", fg=colour)
        typer.secho(f"{'Utilidade (TSTR)':<20} {certificate.tstr.detail}", fg=typer.colors.YELLOW)
        if write:
            typer.echo(f"{'certificado':<20} {dataset_dir / CERTIFICATE_NAME}")

    if not certificate.passed:
        raise typer.Exit(code=1)


@app.command("calibration")
def calibration_command() -> None:
    """Lista os parametros de calibracao, a fonte e o estado de cada um."""
    calibration = load_calibration()
    for parameter_id, parameter_set in sorted(calibration.sets.items()):
        state = "provisorio" if parameter_set.provisional else "consolidado"
        typer.echo(f"{parameter_id:18} {state:12} {parameter_set.meta.get('source', '-')}")
    typer.echo(f"fingerprint: {calibration.fingerprint()}")


def main() -> None:  # pragma: no cover
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
