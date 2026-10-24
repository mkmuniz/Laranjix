"""What each typology rests on, and where it does not rest on anything.

``sources.yaml`` records, per typology, which published passage supports which
part of the signature -- and, separately, which parts no source supports. That
second list is the one that matters. A typology whose gaps are written down can
be argued with; one whose gaps live only in the author's head becomes fact the
moment someone trains on the dataset.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from laranjix.calibration.provenance import Provenance, parse

SOURCES_PATH = Path(__file__).parent / "sources.yaml"


@dataclass(frozen=True)
class Citation:
    """One published passage and the part of the signature it supports."""

    source: str
    supports: str
    provenance: Provenance
    page: int | None = None
    quote: str | None = None


@dataclass(frozen=True)
class TypologySources:
    """Everything backing one typology, including what is missing."""

    code: str
    name: str
    module: str
    citations: list[Citation]
    gaps: list[str]

    @property
    def grounded(self) -> bool:
        return bool(self.citations)

    @property
    def fully_grounded(self) -> bool:
        """No part of the signature is left resting on the generator alone."""
        return self.grounded and not self.gaps


def _citation(entry: dict[str, Any], code: str) -> Citation:
    return Citation(
        source=str(entry["source"]),
        supports=str(entry["supports"]),
        provenance=parse(entry.get("provenance"), f"{code}/{entry['source']}"),
        page=entry.get("page"),
        quote=entry.get("quote"),
    )


@lru_cache(maxsize=1)
def load_sources(path: Path | None = None) -> dict[str, TypologySources]:
    """Load and validate the typology source record."""
    document = yaml.safe_load((path or SOURCES_PATH).read_text(encoding="utf-8")) or {}
    meta = document.get("meta") or {}
    for field in ("source", "source_url", "retrieved_at"):
        if not meta.get(field):
            raise ValueError(f"sources.yaml: meta.{field} e obrigatorio")

    records: dict[str, TypologySources] = {}
    for code, entry in (document.get("typologies") or {}).items():
        citations = [_citation(item, code) for item in entry.get("grounded_by") or []]
        gaps = [str(item) for item in entry.get("not_supported_by_sources") or []]
        if not citations:
            raise ValueError(f"{code}: nenhuma fonte declarada em grounded_by")
        records[str(code)] = TypologySources(
            code=str(code),
            name=str(entry["name"]),
            module=str(entry["module"]),
            citations=citations,
            gaps=gaps,
        )
    return records
