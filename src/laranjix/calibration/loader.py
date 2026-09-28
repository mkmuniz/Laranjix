"""Loading and normalisation of the versioned calibration parameters."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import yaml

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
    def provisional(self) -> bool:
        return bool(self.meta.get("provisional", False))


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
        return sorted(pid for pid, pset in self.sets.items() if pset.provisional)


def _load_file(path: Path) -> ParameterSet:
    raw = path.read_bytes()
    data = yaml.safe_load(raw.decode("utf-8")) or {}
    meta = data.get("meta") or {}
    parameter_id = str(meta.get("parameter_id") or path.stem)
    if "source" not in meta and parameter_id != "accounts":
        # Every parameter file must say where its numbers come from. The
        # accounts file declares the source per block instead of globally.
        raise ValueError(f"{path.name}: meta.source is required")
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
