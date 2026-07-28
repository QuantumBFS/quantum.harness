from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path

import numpy as np

from .exact import thermal_from_spectrum
from .run_ed import (
    config_digest,
    load_config,
    logical_sectors,
    sector_directory,
)


def _beta_grid(config: dict) -> np.ndarray:
    grid = config["beta_grid"]
    count = int(
        round((grid["stop"] - grid["start"]) / grid["step"])
    ) + 1
    values = grid["start"] + np.arange(count) * grid["step"]
    if not np.isclose(values[-1], grid["stop"], atol=1e-14):
        raise ValueError("beta grid does not end exactly at stop")
    return values


def _complete_spectrum(
    config_path: Path,
    config: dict,
    root: Path,
) -> np.ndarray:
    config_hash = config_digest(config)
    pieces = []
    recovered = 0
    sectors = logical_sectors(config)
    if len(set(sectors)) != len(sectors):
        raise ValueError("duplicate logical sector")
    if len(sectors) != 10:
        raise ValueError("expected ten logical sectors")
    for irrep, parity in sectors:
        directory = sector_directory(
            root,
            config["field"],
            irrep,
            parity,
        )
        manifest_path = directory / "manifest.json"
        spectrum_path = directory / "eigenvalues.npz"
        if not manifest_path.exists() or not spectrum_path.exists():
            raise ValueError(
                f"missing successful sector {irrep},{parity}"
            )
        manifest = json.loads(
            manifest_path.read_text(encoding="utf-8")
        )
        if manifest.get("status") != "success":
            raise ValueError(
                f"missing successful sector {irrep},{parity}"
            )
        expected_params = {
            "field": config["field"],
            "irrep": irrep,
            "parity": parity,
        }
        if manifest["params"] != expected_params:
            raise ValueError("sector parameter mismatch")
        expected_settings = {
            "l": config["l"],
            "j": config["j"],
            "boundary": config["boundary"],
            "operator": config["operator"],
        }
        if manifest["settings"] != expected_settings:
            raise ValueError("sector convention mismatch")
        if manifest["provenance"]["config_sha256"] != config_hash:
            raise ValueError("configuration hash mismatch")
        actual_hash = hashlib.sha256(
            spectrum_path.read_bytes()
        ).hexdigest()
        if actual_hash != manifest["provenance"]["spectrum_sha256"]:
            raise ValueError("spectrum hash mismatch")
        with np.load(spectrum_path) as payload:
            eigenvalues = np.asarray(
                payload["eigenvalues"],
                dtype=np.float64,
            )
        diagnostics = manifest["diagnostics"]
        multiplicity = int(diagnostics["spectral_multiplicity"])
        expected_multiplicity = 2 if irrep == "E" else 1
        if multiplicity != expected_multiplicity:
            raise ValueError("spectral multiplicity mismatch")
        if len(eigenvalues) != diagnostics["matrix_dimension"]:
            raise ValueError("stored matrix dimension mismatch")
        if (
            diagnostics["recovered_dimension"]
            != len(eigenvalues) * multiplicity
        ):
            raise ValueError("recovered sector dimension mismatch")
        residual = float(diagnostics["hermiticity_residual"])
        if not np.isfinite(residual) or residual > 1e-12:
            raise ValueError("invalid Hermiticity residual")
        if (
            not np.isfinite(eigenvalues).all()
            or np.any(np.diff(eigenvalues) < 0)
        ):
            raise ValueError("invalid sector spectrum")
        pieces.append(np.repeat(eigenvalues, multiplicity))
        recovered += len(eigenvalues) * multiplicity
    if recovered != 1 << (config["l"] ** 2):
        raise ValueError("recovered spectrum is incomplete")
    return np.sort(np.concatenate(pieces))


def assemble(
    config_path: Path,
    run_root: Path,
    output: Path,
) -> int:
    config_path = Path(config_path)
    run_root = Path(run_root)
    output = Path(output)
    config = load_config(config_path)
    spectrum = _complete_spectrum(config_path, config, run_root)
    rows = []
    nsites = config["l"] ** 2
    for beta in _beta_grid(config):
        point = thermal_from_spectrum(
            spectrum,
            beta=float(beta),
            nsites=nsites,
        )
        rows.append(
            {
                "beta": point.beta,
                "log_z_per_site": point.log_z / nsites,
                "f": point.f,
                "u": point.u,
                "c": point.c,
            }
        )
    output.mkdir(parents=True, exist_ok=True)
    destination = output / "thermodynamics.csv"
    temporary = destination.with_suffix(".csv.tmp")
    with temporary.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("beta", "log_z_per_site", "f", "u", "c"),
        )
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, destination)
    manifest = {
        "status": "success",
        "state_count": len(spectrum),
        "field": config["field"],
        "thermodynamics_sha256": hashlib.sha256(
            destination.read_bytes()
        ).hexdigest(),
    }
    manifest_path = output / "manifest.json"
    temp_manifest = manifest_path.with_suffix(".json.tmp")
    temp_manifest.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temp_manifest, manifest_path)
    return 0


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    return assemble(args.config, args.run_root, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
