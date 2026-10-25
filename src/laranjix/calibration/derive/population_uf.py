"""Derive the population-by-UF parameter from the IBGE API.

Run with::

    python -m laranjix.calibration.derive.population_uf

It rewrites ``params/population_uf.yaml`` from two public endpoints and records
what it read: the URLs, the day it read them, and a hash of each response. The
hash is the part that matters later -- it is how a future run can tell that the
source itself changed rather than that someone edited the file.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import urllib.request
import zlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PARAMS_PATH = Path(__file__).resolve().parents[1] / "params" / "population_uf.yaml"

STATES_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/estados"
# Aggregate 4714, variable 93: resident population, 2022 Census, by federative unit.
POPULATION_URL = (
    "https://servicodados.ibge.gov.br/api/v3/agregados/4714/periodos/2022"
    "/variaveis/93?localidades=N3[all]"
)
TIMEOUT_SECONDS = 90
EXPECTED_STATES = 27  # 26 states and the Federal District


def fetch(url: str) -> tuple[Any, str]:
    """Return the parsed response and the SHA-256 of the decompressed content.

    The hash has to identify the content, not whichever compression the
    transport chose that day, so it is taken after decoding. The IBGE API gzips
    regardless of what the request asks for.
    """
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        raw = response.read()
        encoding = response.headers.get("Content-Encoding", "").lower()

    if encoding == "gzip":
        raw = gzip.decompress(raw)
    elif encoding == "deflate":
        raw = zlib.decompress(raw)
    elif encoding not in ("", "identity"):
        raise ValueError(f"{url}: Content-Encoding inesperado: {encoding}")

    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def population_by_uf() -> tuple[dict[str, int], dict[str, str]]:
    """Return population keyed by UF abbreviation, plus the hashes of the sources."""
    states, states_hash = fetch(STATES_URL)
    population, population_hash = fetch(POPULATION_URL)

    abbreviation = {str(state["id"]): str(state["sigla"]) for state in states}
    series = population[0]["resultados"][0]["series"]

    values: dict[str, int] = {}
    for entry in series:
        code = str(entry["localidade"]["id"])
        if code not in abbreviation:
            raise ValueError(f"UF {code} nao esta na lista de estados do IBGE")
        values[abbreviation[code]] = int(entry["serie"]["2022"])

    if len(values) != EXPECTED_STATES:
        raise ValueError(f"esperava {EXPECTED_STATES} UFs, a API devolveu {len(values)}")
    return values, {"states": states_hash, "population": population_hash}


def render(values: dict[str, int], hashes: dict[str, str], retrieved_at: str) -> str:
    """Return the parameter file, ordered by population so diffs stay readable."""
    lines = [
        "# Distribuicao da populacao brasileira por unidade federativa.",
        "#",
        "# NAO EDITE A MAO. Este arquivo e gerado por:",
        "#   python -m laranjix.calibration.derive.population_uf",
        "#",
        "# Uso no Laranjix: sortear a UF das contas PF, de modo que a distribuicao",
        "# geografica do dataset se pareca com a do pais (ESCOPO.md, secao 6.2).",
        "meta:",
        "  parameter_id: population_uf",
        "  provenance: public_statistic",
        "  source: IBGE - Censo Demografico 2022, populacao residente por UF",
        f"  source_url: {POPULATION_URL}",
        f"  retrieved_at: {retrieved_at}",
        "  unit: pessoas",
        "  derivation: python -m laranjix.calibration.derive.population_uf",
        "  source_endpoints:",
        f"    states: {STATES_URL}",
        f"    population: {POPULATION_URL}",
        "  source_sha256:",
        f"    states: {hashes['states']}",
        f"    population: {hashes['population']}",
        "values:",
    ]
    for uf, people in sorted(values.items(), key=lambda item: -item[1]):
        lines.append(f"  {uf}: {people}")
    return "\n".join(lines) + "\n"


def main() -> None:
    values, hashes = population_by_uf()
    retrieved_at = datetime.now(UTC).date().isoformat()
    PARAMS_PATH.write_text(render(values, hashes, retrieved_at), encoding="utf-8")
    total = sum(values.values())
    print(f"{PARAMS_PATH.name}: {len(values)} UFs, {total:,} pessoas, lido em {retrieved_at}")


if __name__ == "__main__":  # pragma: no cover
    main()
