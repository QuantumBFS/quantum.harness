"""Strict configuration loading and deterministic result persistence."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping, Sequence, TYPE_CHECKING

import numpy as np
import yaml

from .model import ModelParameters

if TYPE_CHECKING:
    from .workflows import UScanRecord


class UniqueKeyLoader(yaml.SafeLoader):
    """YAML loader that rejects silently overwritten mapping keys."""


def _construct_unique_mapping(
    loader: UniqueKeyLoader,
    node,
    deep: bool = False,
):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ValueError(f"duplicate YAML key: {key}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def load_yaml(path: Path | str) -> dict[str, Any]:
    config_path = Path(path)
    with config_path.open(encoding="utf-8") as stream:
        loaded = yaml.load(stream, Loader=UniqueKeyLoader)
    if not isinstance(loaded, dict):
        raise ValueError("configuration root must be a mapping")
    return loaded


def _number_token(value: int | float) -> str:
    if isinstance(value, int):
        return str(value)
    readable = f"{float(value):+.6f}".replace("+", "p").replace("-", "neg").replace(
        ".",
        "d",
    )
    bits = int(np.asarray(float(value), dtype=np.float64).view(np.uint64))
    return f"{readable}_{bits:016x}"


def deterministic_grid_filename(
    parameters: ModelParameters,
    *,
    n_theta: int,
    n_phi: int,
) -> str:
    """Name a grid using every physical parameter that changes its data."""
    fields = [
        f"L{parameters.L}",
        f"Nup{parameters.N_up}",
        f"Ndown{parameters.N_down}",
        f"t_{_number_token(parameters.t)}",
        f"delta0_{_number_token(parameters.delta0)}",
        f"Delta0_{_number_token(parameters.Delta0)}",
        f"U_{_number_token(parameters.U)}",
        f"Ntheta{n_theta}",
        f"Nphi{n_phi}",
    ]
    return "grid_" + "_".join(fields) + ".npz"


def parameters_dict(parameters: ModelParameters) -> dict[str, int | float]:
    return {
        "L": parameters.L,
        "U": parameters.U,
        "t": parameters.t,
        "delta0": parameters.delta0,
        "Delta0": parameters.Delta0,
        "N_up": parameters.N_up,
        "N_down": parameters.N_down,
    }


def save_chern_grid(record: "UScanRecord", output_dir: Path | str) -> Path:
    """Persist a complete Chern grid, including reusable ground states."""
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    result = record.result
    path = directory / deterministic_grid_filename(
        record.parameters,
        n_theta=result.N_theta,
        n_phi=result.N_phi,
    )
    np.savez_compressed(
        path,
        ground_states=result.states,
        berry_flux=result.fhs.flux,
        ground_state_energies=result.ground_state_energies,
        first_excited_energies=result.first_excited_energies,
        gaps=result.gaps,
        hermiticity_errors=result.hermiticity_errors,
        residuals=result.residuals,
        basis_fingerprint=result.basis_fingerprint,
        parameters_json=json.dumps(parameters_dict(record.parameters), sort_keys=True),
    )
    return path


def save_scan_summary(
    records: Sequence["UScanRecord"],
    output_dir: Path | str,
) -> tuple[Path, Path]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    rows = [record.as_dict() for record in records]
    json_path = directory / "scan_summary.json"
    csv_path = directory / "scan_summary.csv"
    json_path.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n")
    if rows:
        fields = [
            "L",
            "U",
            "t",
            "delta0",
            "Delta0",
            "N_up",
            "N_down",
            "N_theta",
            "N_phi",
            "C_raw",
            "C_rounded",
            "chern_error",
            "gap_min",
            "theta_gap_min",
            "phi_gap_min",
            "min_link_overlap",
            "max_abs_berry_curvature",
            "maximum_link_modulus_error",
            "solver_residual",
            "converged",
            "diagonalization_count",
            "total_diagonalizations",
            "wall_time_s",
        ]
        with csv_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    else:
        csv_path.write_text("")
    return json_path, csv_path


def require_mapping(config: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = config.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"configuration section {key!r} must be a mapping")
    return value
