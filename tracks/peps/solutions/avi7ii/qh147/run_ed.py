from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import traceback

import numpy as np
import psutil
import scipy

from .ed import sector_eigenvalues
from .symmetry_ed import sector_basis


def load_config(path: Path) -> dict:
    config = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "l",
        "j",
        "field",
        "boundary",
        "operator",
        "irreps",
        "parities",
        "beta_grid",
    }
    if (
        set(config) != required
        or config["boundary"] != "open"
        or config["operator"] != "pauli"
    ):
        raise ValueError("invalid ED configuration")
    return config


def logical_sectors(config: dict):
    return tuple(
        (irrep, parity)
        for irrep in config["irreps"]
        for parity in config["parities"]
    )


def field_directory(root: Path, field: float) -> Path:
    return root / f"h-{field:g}"


def sector_directory(
    root: Path,
    field: float,
    irrep: str,
    parity: int,
) -> Path:
    return field_directory(root, field) / f"{irrep}-p{parity:+d}"


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _atomic_spectrum(path: Path, eigenvalues: np.ndarray) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        np.savez_compressed(handle, eigenvalues=eigenvalues)
    os.replace(temporary, path)


def config_digest(config: dict) -> str:
    canonical = json.dumps(
        config,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _peak_memory() -> int:
    if os.name == "posix":
        import resource

        return int(
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        ) * 1024
    return int(psutil.Process().memory_info().rss)


def _rehearse(
    config_path: Path,
    config: dict,
    root: Path,
) -> int:
    cells = []
    for index, (irrep, parity) in enumerate(
        logical_sectors(config),
        start=1,
    ):
        basis = sector_basis(config["l"], irrep, parity)
        dimension = basis.q.shape[1]
        cells.append(
            {
                "cell_index": index,
                "irrep": irrep,
                "parity": parity,
                "matrix_dimension": dimension,
                "recovered_dimension": basis.recovered_dimension,
                "spectral_multiplicity": basis.spectral_multiplicity,
                "matrix_bytes": 8 * dimension * dimension,
                "dense_flops_upper": 4 * dimension**3 / 3,
            }
        )
        print(json.dumps(cells[-1]), flush=True)
    recovered = sum(
        cell["recovered_dimension"] for cell in cells
    )
    if recovered != 1 << (config["l"] ** 2):
        raise ValueError("rehearsal sector dimensions are incomplete")
    _atomic_json(
        field_directory(root, config["field"]) / "rehearsal.json",
        {
            "status": "rehearsed",
            "config_sha256": config_digest(config),
            "cells": cells,
        },
    )
    return 0


def _existing_success(output: Path, expected_hash: str) -> bool:
    manifest_path = output / "manifest.json"
    spectrum_path = output / "eigenvalues.npz"
    if not manifest_path.exists() or not spectrum_path.exists():
        return False
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return (
        manifest.get("status") == "success"
        and manifest.get("provenance", {}).get("config_sha256")
        == expected_hash
        and manifest.get("provenance", {}).get("spectrum_sha256")
        == hashlib.sha256(spectrum_path.read_bytes()).hexdigest()
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--cell-index", type=int)
    parser.add_argument("--rehearse-all", action="store_true")
    args = parser.parse_args(argv)
    config = load_config(args.config)
    if args.rehearse_all:
        return _rehearse(args.config, config, args.run_root)
    raw_index = (
        args.cell_index
        if args.cell_index is not None
        else int(os.environ["SLURM_ARRAY_TASK_ID"])
    )
    sectors = logical_sectors(config)
    if not 1 <= raw_index <= len(sectors):
        raise ValueError(
            "cell index is outside the ten logical sectors"
        )
    irrep, parity = sectors[raw_index - 1]
    output = sector_directory(
        args.run_root,
        config["field"],
        irrep,
        parity,
    )
    output.mkdir(parents=True, exist_ok=True)
    config_hash = config_digest(config)
    if _existing_success(output, config_hash):
        print(
            json.dumps(
                {"status": "reused", "cell_index": raw_index}
            ),
            flush=True,
        )
        return 0
    started = time.perf_counter()
    try:
        basis = sector_basis(config["l"], irrep, parity)
        dimension = basis.q.shape[1]
        print(
            json.dumps(
                {
                    "event": "preflight",
                    "cell_index": raw_index,
                    "irrep": irrep,
                    "parity": parity,
                    "matrix_dimension": dimension,
                    "matrix_bytes": 8 * dimension * dimension,
                    "dense_flops_upper": 4 * dimension**3 / 3,
                }
            ),
            flush=True,
        )
        result = sector_eigenvalues(
            config["l"],
            j=config["j"],
            h=config["field"],
            irrep=irrep,
            parity=parity,
        )
        spectrum_path = output / "eigenvalues.npz"
        _atomic_spectrum(spectrum_path, result.eigenvalues)
        manifest = {
            "status": "success",
            "params": {
                "field": config["field"],
                "irrep": irrep,
                "parity": parity,
            },
            "settings": {
                "l": config["l"],
                "j": config["j"],
                "boundary": config["boundary"],
                "operator": config["operator"],
            },
            "diagnostics": {
                "matrix_dimension": result.matrix_dimension,
                "recovered_dimension": result.recovered_dimension,
                "spectral_multiplicity": (
                    result.spectral_multiplicity
                ),
                "hermiticity_residual": (
                    result.hermiticity_residual
                ),
            },
            "resources": {
                "wall_seconds": time.perf_counter() - started,
                "peak_memory_bytes": _peak_memory(),
            },
            "provenance": {
                "git_commit": subprocess.check_output(
                    ["git", "rev-parse", "HEAD"],
                    text=True,
                ).strip(),
                "config_sha256": config_hash,
                "spectrum_sha256": hashlib.sha256(
                    spectrum_path.read_bytes()
                ).hexdigest(),
                "numpy": np.__version__,
                "scipy": scipy.__version__,
            },
        }
        _atomic_json(output / "manifest.json", manifest)
        print(
            json.dumps(
                {"status": "success", "cell_index": raw_index}
            ),
            flush=True,
        )
        return 0
    except Exception as error:
        _atomic_json(
            output / "manifest.json",
            {
                "status": "failed",
                "error": type(error).__name__,
                "traceback": traceback.format_exc(),
            },
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
