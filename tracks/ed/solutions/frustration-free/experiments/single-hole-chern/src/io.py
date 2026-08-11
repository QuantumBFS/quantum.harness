"""IO utilities for single-hole Chern experiment.

Uses .npz files for numeric arrays + .json for metadata, consistent
with the existing hubbard-pump-2 experiment conventions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np


def save_spectrum_result(
    path: Path,
    energies: np.ndarray,
    K_values: np.ndarray,
    phi_values: np.ndarray,
    isolation_gaps: np.ndarray,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Save K-resolved spectrum data.

    Parameters
    ----------
    path : Path
        Output .npz file path.
    energies : np.ndarray
        Shape (N_K, N_phi, n_eigenvalues). E_alpha(K, phi).
    K_values : np.ndarray
        Shape (N_K,). Crystal momentum values.
    phi_values : np.ndarray
        Shape (N_phi,). Pump phase values.
    isolation_gaps : np.ndarray
        Shape (N_K, N_phi). Gap from M-th to (M+1)-th eigenvalue.
    metadata : dict, optional
        Additional metadata saved alongside arrays.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        energies=energies,
        K_values=K_values,
        phi_values=phi_values,
        isolation_gaps=isolation_gaps,
    )
    if metadata is not None:
        meta_path = path.with_suffix(".json")
        meta_path.write_text(json.dumps(metadata, indent=2, default=str) + "\n")


def load_spectrum_result(path: Path) -> dict[str, np.ndarray]:
    """Load K-resolved spectrum data from .npz."""
    data = np.load(path, allow_pickle=True)
    result = {key: data[key] for key in data.files}
    data.close()
    return result


def save_chern_result(
    path: Path,
    chern_raw: float,
    chern_integer: int,
    berry_curvature: np.ndarray,
    wilson_phases: np.ndarray | None,
    theta_values: np.ndarray,
    phi_values: np.ndarray,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Save Chern number computation results.

    Parameters
    ----------
    path : Path
        Output .npz file path.
    chern_raw : float
        Raw (floating-point) Chern number.
    chern_integer : int
        Rounded Chern number.
    berry_curvature : np.ndarray
        Shape (N_theta, N_phi). Berry curvature F(θ, φ).
    wilson_phases : np.ndarray or None
        Shape (N_phi, M). Wilson loop eigenphases ν_a(φ).
    theta_values : np.ndarray
        Shape (N_theta,). Boundary twist values.
    phi_values : np.ndarray
        Shape (N_phi,). Pump phase values.
    metadata : dict, optional
        Additional metadata.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    save_dict: dict[str, Any] = {
        "chern_raw": chern_raw,
        "chern_integer": chern_integer,
        "berry_curvature": berry_curvature,
        "theta_values": theta_values,
        "phi_values": phi_values,
    }
    if wilson_phases is not None:
        save_dict["wilson_phases"] = wilson_phases
    np.savez_compressed(path, **save_dict)
    if metadata is not None:
        meta_path = path.with_suffix(".json")
        meta_path.write_text(json.dumps(metadata, indent=2, default=str) + "\n")


def load_chern_result(path: Path) -> dict[str, Any]:
    """Load Chern number computation results from .npz."""
    data = np.load(path, allow_pickle=True)
    result = {key: data[key] for key in data.files}
    data.close()
    return result
