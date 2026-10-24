"""A typology has to say what backs it, and what nothing backs."""

from __future__ import annotations

import pytest
import yaml

from laranjix.calibration.provenance import Provenance
from laranjix.dataset import TYPOLOGIES
from laranjix.typologies.sources import SOURCES_PATH, load_sources


def test_every_implemented_typology_has_a_source_record() -> None:
    records = load_sources()
    for module in TYPOLOGIES:
        assert module.CODE in records, f"{module.CODE} nao tem registro de fonte"


def test_each_record_points_at_the_module_it_describes() -> None:
    for record in load_sources().values():
        module = next(m for m in TYPOLOGIES if record.code == m.CODE)
        assert record.module == module.__name__


def test_every_citation_names_a_source_and_what_it_supports() -> None:
    for record in load_sources().values():
        assert record.citations, record.code
        for citation in record.citations:
            assert citation.source.strip()
            assert citation.supports.strip()
            assert isinstance(citation.provenance, Provenance)
            # A typology may not be grounded on something ungrounded.
            assert citation.provenance is not Provenance.UNVERIFIED


def test_public_statistic_citations_carry_a_quote_and_a_page() -> None:
    # Citing a 223-page document without saying where is not a citation.
    for record in load_sources().values():
        for citation in record.citations:
            if citation.provenance is Provenance.PUBLIC_STATISTIC:
                assert citation.page, f"{record.code}: {citation.source} sem pagina"
                assert citation.quote, f"{record.code}: {citation.source} sem citacao literal"


def test_the_record_declares_what_no_source_supports() -> None:
    # The honest part. A typology with no declared gaps is claiming every detail
    # of its signature came from a publication, which would be remarkable.
    for record in load_sources().values():
        assert record.gaps, f"{record.code}: nenhuma lacuna declarada"
        assert not record.fully_grounded


def test_a_record_without_any_source_is_refused(tmp_path) -> None:
    path = tmp_path / "sources.yaml"
    path.write_text(
        "meta:\n  source: x\n  source_url: http://x\n  retrieved_at: 2026-01-01\n"
        "typologies:\n  T9:\n    name: n\n    module: m\n    grounded_by: []\n",
        encoding="utf-8",
    )
    load_sources.cache_clear()
    with pytest.raises(ValueError, match="nenhuma fonte declarada"):
        load_sources(path)
    load_sources.cache_clear()


def test_the_record_says_where_the_document_was_read_from() -> None:
    meta = yaml.safe_load(SOURCES_PATH.read_text(encoding="utf-8"))["meta"]
    assert meta["source_url"].startswith("https://www.gov.br/coaf/")
    assert meta["retrieved_at"]
    # The canonical URL serves HTML, so where the PDF actually came from is
    # itself part of the provenance.
    assert "retrieval_note" in meta
