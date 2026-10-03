"""Rendering the certificate as Markdown."""

from __future__ import annotations

from laranjix.validation.certificate import Certificate
from laranjix.validation.tstr import TstrStatus

MARK_PASS = "PASSOU"
MARK_FAIL = "FALHOU"


def _mark(passed: bool) -> str:
    return MARK_PASS if passed else MARK_FAIL


def render_markdown(certificate: Certificate) -> str:
    """Return the certificate as a Markdown document."""
    manifest = certificate.manifest
    counts = manifest.get("row_counts", {})
    calibration = manifest.get("calibration", {})
    provisional = calibration.get("provisional", [])

    lines: list[str] = []
    add = lines.append

    add("# Certificado de qualidade do dataset")
    add("")
    add(
        f"**Resultado: {_mark(certificate.passed)}** · "
        f"Laranjix {certificate.laranjix_version} · emitido em {certificate.issued_at}"
    )
    add("")
    add("| | |")
    add("|---|---|")
    add(f"| Seed | `{manifest.get('seed')}` |")
    add(f"| Contas | {counts.get('accounts', 0):,} |")
    add(f"| Chaves Pix | {counts.get('pix_keys', 0):,} |")
    add(f"| Sociedades | {counts.get('company_partners', 0):,} |")
    add(f"| Fingerprint da calibracao | `{str(calibration.get('fingerprint', ''))[:16]}…` |")
    add("")

    add("## 1. Privacidade")
    add("")
    evidence = certificate.privacy.evidence
    add(f"**{_mark(certificate.privacy.passed)}** — {certificate.privacy.detail}")
    add("")
    add("| Verificacao | Resultado |")
    add("|---|---|")
    checked = evidence.get("documents_checked", 0)
    valid = evidence.get("valid_documents_found", 0)
    findings = evidence.get("pii_findings", 0)
    add(f"| Documentos revalidados pelo algoritmo oficial | {checked:,} |")
    add(f"| Documentos que passariam como validos | **{valid}** |")
    add(f"| Achados do scanner de PII | **{findings}** |")
    add("")

    add("## 2. Reprodutibilidade")
    add("")
    evidence = certificate.reproducibility.evidence
    add(f"**{_mark(certificate.reproducibility.passed)}** — {certificate.reproducibility.detail}")
    add("")
    add(
        f"O dataset foi regerado a partir do proprio `manifest.json` e "
        f"{evidence.get('files_matching', 0)} de {evidence.get('files_compared', 0)} "
        "arquivos bateram no SHA-256."
    )
    add("")

    add("## 3. Fidelidade a calibracao")
    add("")
    report = certificate.fidelity
    add(
        f"**{_mark(report.passed)}** — cada distribuicao gerada e comparada com o alvo da "
        "calibracao. O limiar e o desvio que o proprio tamanho da amostra produz, "
        "estimado por simulacao: uma checagem so falha quando o desvio e maior do que "
        "o acaso explica."
    )
    add("")
    add("| Distribuicao | TVD | Limiar de ruido | x ruido | |")
    add("|---|---:|---:|---:|---|")
    for check in report.checks:
        add(
            f"| {check.name} | {check.tvd:.5f} | {check.noise_threshold:.5f} | "
            f"{check.ratio:.1f}x | {_mark(check.passed)} |"
        )
    add("")

    add("## 4. Utilidade (TSTR)")
    add("")
    result = certificate.tstr
    if result.status is TstrStatus.OK:
        ratio = result.utility_ratio or 0.0
        add(
            f"**{result.model}** — treinado no dataset sintetico, avaliado na base real "
            "de quem executou. A base real nunca entra no repositorio; so o numero sai."
        )
        add("")
        add("| Metrica | Average precision |")
        add("|---|---:|")
        synthetic = result.tstr_average_precision or 0.0
        real = result.trtr_average_precision or 0.0
        add(f"| Treinado no sintetico, testado no real (TSTR) | {synthetic:.4f} |")
        add(f"| Treinado no real, testado no real (TRTR) | {real:.4f} |")
        add(f"| Baseline (taxa base) | {result.baseline_average_precision:.4f} |")
        add(f"| **Razao de utilidade TSTR/TRTR** | **{ratio:.3f}** |")
    else:
        add(f"**PENDENTE** — {result.detail}")
    add("")

    add("## 5. O que este certificado nao afirma")
    add("")
    add(
        "- **Nao afirma que o dataset descreve o Brasil.** A secao 3 compara o gerado com "
        "os parametros de calibracao, nao com a realidade. Se os parametros estiverem "
        "errados, o dataset passa e continua irrealista."
    )
    if provisional:
        add(
            f"- **Parametros ainda provisorios:** `{'`, `'.join(provisional)}`. "
            "Sao valores de ordem de grandeza plausivel, nao derivados das fontes publicas."
        )
    add(
        "- **Nao afirma desempenho em producao.** Resultado obtido em dado sintetico nao "
        "demonstra como um modelo se comporta com dado real."
    )
    add("- **Nao substitui revisao juridica** antes de uma release publica.")
    add("")
    add("---")
    add("")
    add("Reproduza este certificado com:")
    add("")
    add("```bash")
    add(f"laranjix certify {certificate.dataset}")
    add("```")
    return "\n".join(lines) + "\n"
