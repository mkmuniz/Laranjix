"""The derivation has to produce a file the loader accepts as sourced.

No network here: CI must not fail because the IBGE API was slow. What is tested
is the part that can be wrong without anyone noticing -- the shape of the file
the script writes, and whether it still claims a public source after a change.
"""

from __future__ import annotations

import yaml

from laranjix.calibration.derive.population_uf import PARAMS_PATH, render
from laranjix.calibration.loader import load_calibration
from laranjix.calibration.params import __file__ as params_marker  # noqa: F401
from laranjix.calibration.provenance import Provenance

SAMPLE = {"SP": 44_411_238, "MG": 20_539_989, "RR": 636_707}
HASHES = {"states": "a" * 64, "population": "b" * 64}


def test_rendered_file_is_loadable_and_sourced(tmp_path) -> None:
    path = tmp_path / "population_uf.yaml"
    path.write_text(render(SAMPLE, HASHES, "2026-10-25"), encoding="utf-8")

    load_calibration.cache_clear()
    parameter_set = load_calibration(tmp_path)["population_uf"]
    load_calibration.cache_clear()

    assert parameter_set.provenance is Provenance.PUBLIC_STATISTIC
    assert parameter_set.grounded
    assert parameter_set.data["values"] == SAMPLE


def test_rendered_file_records_how_to_reproduce_it(tmp_path) -> None:
    meta = yaml.safe_load(render(SAMPLE, HASHES, "2026-10-25"))["meta"]
    # Without the command and the source hashes, "public_statistic" is a claim
    # nobody can check.
    assert "derivation" in meta
    assert meta["source_sha256"] == HASHES
    # YAML parses an ISO date into a date object, not a string.
    assert str(meta["retrieved_at"]) == "2026-10-25"


def test_rendering_is_deterministic() -> None:
    assert render(SAMPLE, HASHES, "2026-10-25") == render(SAMPLE, HASHES, "2026-10-25")


def test_values_are_ordered_by_population() -> None:
    # Keeps the diff readable when the census is re-read.
    values = yaml.safe_load(render(SAMPLE, HASHES, "2026-10-25"))["values"]
    assert list(values) == sorted(values, key=lambda uf: -values[uf])


def test_the_committed_file_is_the_derived_one() -> None:
    meta = yaml.safe_load(PARAMS_PATH.read_text(encoding="utf-8"))["meta"]
    assert meta["provenance"] == Provenance.PUBLIC_STATISTIC.value
    assert meta["source_sha256"]["population"]
    assert len(yaml.safe_load(PARAMS_PATH.read_text(encoding="utf-8"))["values"]) == 27
