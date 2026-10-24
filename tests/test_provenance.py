"""Every calibration number has to say where it came from.

The failure these tests guard against is not a crash. It is a number that
defines what "normal" looks like, written by whoever set up the file, that
nobody ever checks -- and that every model trained on the dataset then learns as
if it were a measurement.
"""

from __future__ import annotations

import pytest
import yaml

from laranjix.calibration.loader import PARAMS_DIR, load_calibration
from laranjix.calibration.provenance import (
    GROUNDED,
    REQUIRED_EVIDENCE,
    Provenance,
    missing_evidence,
    parse,
)


def test_every_parameter_file_declares_a_provenance(calibration) -> None:
    for parameter_id, parameter_set in calibration.sets.items():
        assert isinstance(parameter_set.provenance, Provenance), parameter_id


def test_a_file_without_provenance_is_refused(tmp_path) -> None:
    path = tmp_path / "thing.yaml"
    path.write_text("meta:\n  parameter_id: thing\nvalues:\n  a: 1\n", encoding="utf-8")
    load_calibration.cache_clear()
    with pytest.raises(ValueError, match="provenance e obrigatorio"):
        load_calibration(tmp_path)
    load_calibration.cache_clear()


def test_an_unknown_provenance_is_refused() -> None:
    with pytest.raises(ValueError, match="nao existe"):
        parse("vibes", "thing")


def test_each_provenance_demands_its_own_evidence() -> None:
    # Claiming a public source without saying which one, or when it was read,
    # is the same as claiming nothing.
    assert "source_url" in missing_evidence(Provenance.PUBLIC_STATISTIC, {"source": "BCB"})
    assert "reviewed_by" in missing_evidence(Provenance.EXPERT_REVIEW, {})
    assert missing_evidence(Provenance.REGULATORY, {"source": "Resolucao BCB 142/2021"}) == []


def test_a_claim_without_its_evidence_is_refused(tmp_path) -> None:
    path = tmp_path / "thing.yaml"
    path.write_text(
        "meta:\n  parameter_id: thing\n  provenance: public_statistic\n  source: BCB\n"
        "values:\n  a: 1\n",
        encoding="utf-8",
    )
    load_calibration.cache_clear()
    with pytest.raises(ValueError, match="exige meta"):
        load_calibration(tmp_path)
    load_calibration.cache_clear()


def test_unverified_parameters_are_not_counted_as_grounded(calibration) -> None:
    for parameter_id, parameter_set in calibration.sets.items():
        if parameter_set.provenance is Provenance.UNVERIFIED:
            assert not parameter_set.grounded, parameter_id
            assert parameter_id in calibration.provisional_ids()


def test_every_unverified_parameter_says_how_to_ground_it() -> None:
    # An ungrounded number is acceptable while building. An ungrounded number
    # with no plan to ground it is how it becomes permanent.
    for path in sorted(PARAMS_DIR.glob("*.yaml")):
        meta = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("meta", {})
        if meta.get("provenance") == Provenance.UNVERIFIED.value:
            assert meta.get("to_ground"), f"{path.name}: falta meta.to_ground"


def test_the_release_gate_blocks_while_anything_is_unverified(calibration) -> None:
    if calibration.provisional_ids():
        with pytest.raises(ValueError, match="sem fundamento externo"):
            calibration.require_grounded()
    else:  # pragma: no cover - reached once every parameter is sourced
        calibration.require_grounded()


def test_grounded_means_sourced_reviewed_or_regulatory() -> None:
    assert Provenance.UNVERIFIED not in GROUNDED
    assert set(Provenance) - {Provenance.UNVERIFIED} == GROUNDED
    assert set(REQUIRED_EVIDENCE) == set(Provenance)
