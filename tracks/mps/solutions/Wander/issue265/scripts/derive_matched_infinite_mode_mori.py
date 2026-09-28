#!/usr/bin/env python3
"""Match full-mode fluctuating-GHD one-loop kernels to exact XXX Mori moments.

The inputs are theory certificates, not spin-chain trajectories.  The script
adds the complete colored quadratic correction and the causal half-weight of
the multiplicative-noise contact to the exact full-mode linear Mori kernel.
It then tests whether every Fourier regulator can be represented by a positive
continuum terminator behind the selected exact microscopic Lanczos prefix
(currently available through thirteen recurrents / mu26).
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.mori_moment_matching import match_kernels_to_exact_lanczos  # noqa: E402


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _jsonable(value):
    if isinstance(value, np.ndarray):
        return _jsonable(value.tolist())
    if isinstance(value, np.generic):
        return _jsonable(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _laplace(times: np.ndarray, values: np.ndarray, frequencies: np.ndarray) -> np.ndarray:
    return np.asarray(
        [np.trapezoid(np.exp(-z * times) * values, times) for z in frequencies]
    )


def derive(
    linear_path: Path,
    one_loop_path: Path,
    *,
    spectral_nodes: int,
    spectral_maximum: float,
    spectral_relative_tolerance: float,
    cutoff_relative_tolerance: float,
) -> dict[str, object]:
    linear = json.loads(linear_path.read_text())
    loop = json.loads(one_loop_path.read_text())
    for label, payload in [("linear", linear), ("one-loop", loop)]:
        inputs = payload.get("inputs", {})
        if inputs.get("trajectory_data_used") or inputs.get("target_coefficients_used"):
            raise RuntimeError(f"{label} certificate contains forbidden target data")
    linear_inputs = linear["inputs"]
    loop_inputs = loop["inputs"]
    for key in [
        "field",
        "string_xi_cutoff",
        "string_xi_buffer",
        "rapidity_u_extent",
        "rapidity_points",
        "wave_number",
    ]:
        if linear_inputs[key] != loop_inputs[key]:
            raise ValueError(f"certificate mismatch in {key}")

    projected = linear["projected_mori"]
    z = np.asarray(projected["laplace_values"], dtype=float)
    base = np.asarray(projected["mori_kernel"]["real"], dtype=float)
    times = np.asarray(loop["times"], dtype=float)
    candidates = []
    corrections = []
    cutoff_labels = []
    for row in loop["uv_rows"]:
        memory = np.asarray(
            row["colored_memory"]["total_colored_continuity_memory"]["values"],
            dtype=float,
        )
        if memory.shape != times.shape:
            raise ValueError("one-loop time and memory grids disagree")
        colored = _laplace(times, memory, z)
        contact = 0.5 * float(row["multiplicative_noise_delta_memory"])
        delta = colored + contact
        candidates.append(base + delta)
        corrections.append(delta)
        cutoff_labels.append(
            {
                "fourier_points": int(row["fourier_points"]),
                "maximum_resolved_wave_number": float(
                    row["maximum_resolved_wave_number"]
                ),
                "colored_laplace_correction": colored.tolist(),
                "causal_half_delta_contact": contact,
            }
        )

    spectral_frequencies = np.concatenate(
        ([0.0], np.geomspace(float(np.min(z)) / 20.0, spectral_maximum, spectral_nodes - 1))
    )
    matching = match_kernels_to_exact_lanczos(
        z,
        np.asarray(candidates),
        spectral_frequencies=spectral_frequencies,
        spectral_relative_tolerance=spectral_relative_tolerance,
        cutoff_relative_tolerance=cutoff_relative_tolerance,
    )
    linear_infinite_mode = bool(
        linear.get("scope", {}).get("zero_field_infinite_mode_limit_complete", False)
    )
    loop_infinite_mode = bool(
        loop.get("scope", {}).get("zero_field_infinite_mode_limit_complete", False)
    )
    physical_complete = bool(
        matching["matching_complete"] and linear_infinite_mode and loop_infinite_mode
    )
    return {
        "schema": 1,
        "method": "positive_continuum_terminator_behind_exact_mu26_lanczos_prefix",
        "sources": {
            str(linear_path): _sha256(linear_path),
            str(one_loop_path): _sha256(one_loop_path),
        },
        "inputs": {
            "trajectory_data_used": False,
            "target_coefficients_used": False,
            "spectral_nodes": spectral_nodes,
            "spectral_maximum": spectral_maximum,
            "spectral_relative_tolerance": spectral_relative_tolerance,
            "cutoff_relative_tolerance": cutoff_relative_tolerance,
            "causal_delta_endpoint_weight": 0.5,
        },
        "laplace_frequency": z.tolist(),
        "linear_full_mode_mori_kernel": base.tolist(),
        "cutoffs": cutoff_labels,
        "one_loop_corrections": np.asarray(corrections).tolist(),
        "bare_total_candidate_kernels": np.asarray(candidates).tolist(),
        "matching": _jsonable(matching),
        "gates": {
            "full_non_diagonal_diffusion_in_source": bool(
                loop.get("operator", {}).get("diffusion_vertex", False)
            ),
            "full_fdt_noise_in_source": bool(
                loop.get("operator", {}).get("multiplicative_noise_vertex", False)
            ),
            "exact_mu26_prefix_preserved_if_reconstructed": True,
            "continuum_terminator_matching_complete": bool(
                matching["matching_complete"]
            ),
            "linear_zero_field_infinite_mode_limit_complete": linear_infinite_mode,
            "nonlinear_zero_field_infinite_mode_limit_complete": loop_infinite_mode,
            "physical_F1_perp_certified": physical_complete,
        },
        "conclusion": (
            "The exact microscopic prefix is imposed algebraically, while the "
            "remaining spectrum is not assigned a pole count.  A failed gate "
            "means that this regulator sequence cannot yet determine the "
            "finite-window correction; it is not evidence for a second mode."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("linear_certificate", type=Path)
    parser.add_argument("one_loop_certificate", type=Path)
    parser.add_argument("--spectral-nodes", type=int, default=256)
    parser.add_argument("--spectral-maximum", type=float, default=20.0)
    parser.add_argument("--spectral-relative-tolerance", type=float, default=0.02)
    parser.add_argument("--cutoff-relative-tolerance", type=float, default=0.1)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = derive(
        args.linear_certificate,
        args.one_loop_certificate,
        spectral_nodes=args.spectral_nodes,
        spectral_maximum=args.spectral_maximum,
        spectral_relative_tolerance=args.spectral_relative_tolerance,
        cutoff_relative_tolerance=args.cutoff_relative_tolerance,
    )
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(encoded, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
