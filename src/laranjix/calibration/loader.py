"""Loading and normalisation of the versioned calibration parameters."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import yaml

from laranjix.calibration.provenance import (
    GROUNDED,
    Provenance,
    missing_evidence,
    parse,
)

PARAMS_DIR = Path(__file__).parent / "params"


@dataclass(frozen=True)
class ParameterSet:
    """One parameter file: its payload, its declared source and its hash."""

    parameter_id: str
    path: Path
    data: dict[str, Any]
    sha256: str

    @property
    def meta(self) -> dict[str, Any]:
        return dict(self.data.get("meta", {}))

    @property
    def provenance(self) -> Provenance:
        return parse(self.meta.get("provenance"), self.parameter_id)

    @property
    def grounded(self) -> bool:
        """Whether this parameter rests on something outside the project."""
        return self.provenance in GROUNDED

    @property
    def provisional(self) -> bool:
        """Kept as the older name for "not yet grounded"."""
        return not self.grounded


@dataclass(frozen=True)
class Calibration:
    """Every parameter set available to the generator."""

    sets: dict[str, ParameterSet]

    def __getitem__(self, parameter_id: str) -> ParameterSet:
        return self.sets[parameter_id]

    def data(self, parameter_id: str) -> dict[str, Any]:
        return self.sets[parameter_id].data

    def fingerprint(self) -> str:
        """Stable hash of all parameter files, recorded in the manifest."""
        digest = hashlib.sha256()
        for parameter_id in sorted(self.sets):
            digest.update(parameter_id.encode())
            digest.update(self.sets[parameter_id].sha256.encode())
        return digest.hexdigest()

    def provisional_ids(self) -> list[str]:
        """Parameter ids not yet grounded in anything outside the project."""
        return sorted(pid for pid, pset in self.sets.items() if not pset.grounded)

    def require_grounded(self) -> None:
        """Raise unless every parameter rests on a source, a norm or a reviewer.

        The gate a release has to pass. Shipping a dataset whose idea of normal
        was written by whoever set up the files, and never checked, is the
        failure this whole module exists to prevent.
        """
        ungrounded = self.provisional_ids()
        if ungrounded:
            raise ValueError(
                "parametros ainda sem fundamento externo: "
                + ", ".join(ungrounded)
                + ". Rode `laranjix calibration` para ver o que falta em cada um."
            )


def _load_file(path: Path) -> ParameterSet:
    raw = path.read_bytes()
    data = yaml.safe_load(raw.decode("utf-8")) or {}
    meta = data.get("meta") or {}
    parameter_id = str(meta.get("parameter_id") or path.stem)

    # A parameter file has to say where its numbers came from, and show whatever
    # that claim requires. Without this, an unsourced guess is indistinguishable
    # from a measurement once it is in the file.
    provenance = parse(meta.get("provenance"), parameter_id)
    missing = missing_evidence(provenance, meta)
    if missing:
        raise ValueError(
            f"{path.name}: provenance '{provenance.value}' exige meta.{', meta.'.join(missing)}"
        )
    return ParameterSet(
        parameter_id=parameter_id,
        path=path,
        data=data,
        sha256=hashlib.sha256(raw).hexdigest(),
    )


@cache
def load_calibration(params_dir: Path | None = None) -> Calibration:
    """Load every ``*.yaml`` parameter file from ``params_dir``."""
    directory = params_dir or PARAMS_DIR
    sets: dict[str, ParameterSet] = {}
    for path in sorted(directory.glob("*.yaml")):
        parameter_set = _load_file(path)
        sets[parameter_set.parameter_id] = parameter_set
    if not sets:
        raise FileNotFoundError(f"no calibration parameters found in {directory}")
    return Calibration(sets=sets)


def normalise(weights: dict[str, float]) -> tuple[list[str], list[float]]:
    """Return the keys and a probability vector summing to 1."""
    keys = list(weights)
    total = float(sum(float(weights[key]) for key in keys))
    if total <= 0:
        raise ValueError("weights must sum to a positive number")
    return keys, [float(weights[key]) / total for key in keys]
