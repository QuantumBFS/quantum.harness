from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import yaml

from .diagonalization import DiagonalizationResult
from .model import RiceMeleModel


REQUIRED_CONFIG_FIELDS = {
    "L",
    "t",
    "delta",
    "Delta",
    "theta",
    "N_up",
    "N_down",
    "full_spectrum",
    "output_dir",
}
MODEL_FIELDS = ("L", "t", "delta", "Delta", "theta", "N_up", "N_down")


class UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects ambiguous duplicate mapping keys."""


def _construct_unique_mapping(loader: UniqueKeyLoader, node, deep: bool = False):
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


def load_config(path: Path | str) -> dict[str, Any]:
    config_path = Path(path)
    payload = yaml.load(config_path.read_text(), Loader=UniqueKeyLoader)
    if not isinstance(payload, dict):
        raise ValueError("configuration must be a YAML mapping")
    missing = REQUIRED_CONFIG_FIELDS - payload.keys()
    extra = payload.keys() - REQUIRED_CONFIG_FIELDS
    if missing or extra:
        raise ValueError(
            f"configuration fields mismatch: missing={sorted(missing)}, extra={sorted(extra)}"
        )
    if payload["full_spectrum"] is not True:
        raise ValueError("this project currently requires full_spectrum: true")
    if not isinstance(payload["output_dir"], str) or not payload["output_dir"]:
        raise ValueError("output_dir must be a non-empty string")
    return payload


def model_from_config(config: Mapping[str, Any]) -> RiceMeleModel:
    return RiceMeleModel(**{name: config[name] for name in MODEL_FIELDS})


def _number_token(value: int | float) -> str:
    text = repr(float(value))
    return text.replace("-", "m").replace("+", "").replace(".", "p")


def deterministic_filename(model: RiceMeleModel) -> str:
    return (
        f"rice_mele_L{model.L}_Nup{model.N_up}_Ndown{model.N_down}"
        f"_t{_number_token(model.t)}_delta{_number_token(model.delta)}"
        f"_Delta{_number_token(model.Delta)}_theta{_number_token(model.theta)}.npz"
    )


def save_result(
    model: RiceMeleModel,
    result: DiagonalizationResult,
    output_dir: Path | str,
) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    output_path = directory / deterministic_filename(model)
    diagnostics = {
        "basis_dimension": model.basis.Ns,
        "hermiticity_error": model.hermiticity_error(),
        "orthogonality_error": result.orthogonality_error,
        "maximum_residual": result.maximum_residual,
    }
    np.savez_compressed(
        output_path,
        eigenvalues=result.eigenvalues,
        eigenvectors=result.eigenvectors,
        parameters_json=json.dumps(model.parameters(), sort_keys=True),
        diagnostics_json=json.dumps(diagnostics, sort_keys=True),
    )
    return output_path
