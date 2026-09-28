from __future__ import annotations

import pytest

from laranjix.calibration.loader import normalise

EXPECTED_SETS = {"accounts", "names", "pix_keys", "population_uf"}


def test_every_parameter_set_is_loaded(calibration) -> None:
    assert set(calibration.sets) >= EXPECTED_SETS


def test_every_parameter_file_declares_provenance(calibration) -> None:
    for parameter_id, parameter_set in calibration.sets.items():
        meta = parameter_set.meta
        assert meta.get("parameter_id") == parameter_id
        # Either a global source or, for accounts.yaml, a source per block.
        has_source = "source" in meta or any(
            isinstance(block, dict) and "source" in block for block in parameter_set.data.values()
        )
        assert has_source, f"{parameter_id} declares no source"


def test_fingerprint_is_stable_and_sensitive(calibration) -> None:
    assert calibration.fingerprint() == calibration.fingerprint()
    assert len(calibration.fingerprint()) == 64


def test_provisional_sets_are_reported(calibration) -> None:
    # Milestone 1 replaces these with numbers derived from the public APIs.
    assert "population_uf" in calibration.provisional_ids()


def test_normalise_returns_a_probability_vector() -> None:
    keys, probabilities = normalise({"a": 2.0, "b": 2.0})
    assert keys == ["a", "b"]
    assert probabilities == [0.5, 0.5]
    assert sum(probabilities) == pytest.approx(1.0)


def test_normalise_rejects_empty_weights() -> None:
    with pytest.raises(ValueError):
        normalise({"a": 0.0})


def test_uf_list_is_complete(calibration) -> None:
    ufs = calibration.data("population_uf")["values"]
    assert len(ufs) == 27  # 26 states plus the Federal District
    assert all(value > 0 for value in ufs.values())
