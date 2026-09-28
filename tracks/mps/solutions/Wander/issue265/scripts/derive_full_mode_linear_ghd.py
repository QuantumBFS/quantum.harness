#!/usr/bin/env python3
"""Propagate the complete finite-cutoff linear fluctuating-GHD operator.

Every retained string/rapidity mode, the non-diagonal diffusion kernel, and
the FDT noise covariance are included.  The nonlinear state dependence of
the velocities is deliberately reported as missing: that is the next term
needed for the physical KPZ ``F1_perp`` and is not replaced by a two-mode fit.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
from scipy.linalg import eigvalsh
from scipy.sparse.linalg import expm_multiply


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.evaluate_full_tba_diffusion import (  # noqa: E402
    full_diffusion_operator_field,
)


def derive(
    *,
    field: float,
    xi_cutoff: float,
    xi_buffer: float,
    u_extent: float,
    rapidity_points: int,
    wave_numbers: np.ndarray,
    times: np.ndarray,
) -> dict[str, object]:
    modes = full_diffusion_operator_field(
        field,
        string_xi_cutoff=xi_cutoff,
        string_xi_buffer=xi_buffer,
        rapidity_u_extent=u_extent,
        rapidity_points=rapidity_points,
        string_boundary="robin",
    )
    diffusion = np.asarray(modes["diffusion_operator"])
    covariance = np.asarray(modes["static_covariance"])
    noise = np.asarray(modes["noise_covariance"])
    velocity = np.asarray(modes["velocity"])
    spin = np.asarray(modes["spin_projection"])
    source = covariance @ spin
    normalization = float(spin @ source)
    if not normalization > 0.0:
        raise RuntimeError("non-positive projected static susceptibility")
    times = np.asarray(times, dtype=int)
    if np.any(times < 0) or np.any(np.diff(times) < 0):
        raise ValueError("times must be non-negative and sorted")

    rows: list[dict[str, object]] = []
    for wave_number in np.asarray(wave_numbers, dtype=float):
        generator = (
            -1j * wave_number * np.diag(velocity)
            -0.5 * wave_number**2 * diffusion
        )
        propagated = expm_multiply(
            generator,
            source,
            start=0.0,
            stop=float(times[-1]),
            num=int(times[-1]) + 1,
            endpoint=True,
        )
        structure = np.real(propagated[times] @ spin) / normalization
        rows.append(
            {
                "k": float(wave_number),
                "times": times.astype(float).tolist(),
                "structure_factor_over_chi": structure.tolist(),
            }
        )

    noise_eigenvalues = eigvalsh(noise)
    fdt_rhs = 0.5 * (
        diffusion @ covariance + covariance @ diffusion.T
    )
    return {
        "schema_version": 1,
        "inputs": {
            "field": field,
            "string_xi_cutoff": xi_cutoff,
            "string_xi_buffer": xi_buffer,
            "rapidity_u_extent": u_extent,
            "rapidity_points": rapidity_points,
            "wave_numbers": np.asarray(wave_numbers).tolist(),
            "times": times.tolist(),
            "trajectory_data_used": False,
            "target_coefficients_used": False,
        },
        "operator": {
            "dimension": int(diffusion.shape[0]),
            "full_off_diagonal_diffusion_retained": True,
            "fdt_noise_covariance_retained": True,
            "minimum_noise_covariance_eigenvalue": float(noise_eigenvalues[0]),
            "maximum_noise_covariance_eigenvalue": float(noise_eigenvalues[-1]),
            "relative_fdt_identity_residual": float(
                np.linalg.norm(noise - fdt_rhs)
                / max(np.linalg.norm(noise), np.finfo(float).tiny)
            ),
        },
        "structure_factor": rows,
        "scope": {
            "linearized_full_mode_fluctuating_ghd": True,
            "nonlinear_state_dependent_velocity_propagated": False,
            "physical_F1_perp_claimed": False,
            "interpretation": (
                "all finite-cutoff modes, off-diagonal diffusion and FDT noise "
                "are propagated; nonlinear giant-mode feedback remains required"
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--field", type=float, default=0.2)
    parser.add_argument("--xi-cutoff", type=float, default=1.2)
    parser.add_argument("--xi-buffer", type=float, default=1.2)
    parser.add_argument("--u-extent", type=float, default=3.0)
    parser.add_argument("--rapidity-points", type=int, default=32)
    parser.add_argument("--wave-numbers", nargs="+", type=float, default=[0.04, 0.08])
    parser.add_argument("--times", nargs="+", type=int, default=[0, 10, 25, 50])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = derive(
        field=args.field,
        xi_cutoff=args.xi_cutoff,
        xi_buffer=args.xi_buffer,
        u_extent=args.u_extent,
        rapidity_points=args.rapidity_points,
        wave_numbers=np.asarray(args.wave_numbers),
        times=np.asarray(args.times),
    )
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(encoded, end="")
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
