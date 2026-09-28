"""Dataset manifest: what it takes to reproduce a dataset byte for byte."""

from __future__ import annotations

import hashlib
import json
import platform
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from laranjix import __version__
from laranjix.calibration.loader import Calibration
from laranjix.config import GenerationConfig

MANIFEST_NAME = "manifest.json"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(
    config: GenerationConfig,
    calibration: Calibration,
    files: list[Path],
    counts: dict[str, int],
) -> dict[str, Any]:
    """Return the manifest payload for one generated dataset."""
    return {
        "laranjix_version": __version__,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "python": platform.python_version(),
        "seed": config.seed,
        "config": config.to_dict(),
        "calibration": {
            "fingerprint": calibration.fingerprint(),
            "parameter_sets": {
                pid: {
                    "sha256": pset.sha256,
                    "source": pset.meta.get("source"),
                    "provisional": pset.provisional,
                }
                for pid, pset in sorted(calibration.sets.items())
            },
            "provisional": calibration.provisional_ids(),
        },
        "row_counts": counts,
        "files": {
            path.name: {"sha256": file_sha256(path), "bytes": path.stat().st_size}
            for path in sorted(files)
        },
        "synthetic": True,
        "disclaimer": (
            "Dataset 100% sintetico. Nenhum dado pessoal real foi usado. "
            "Resultados obtidos aqui nao demonstram desempenho em producao."
        ),
    }


def write_manifest(directory: Path, payload: dict[str, Any]) -> Path:
    path = directory / MANIFEST_NAME
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
