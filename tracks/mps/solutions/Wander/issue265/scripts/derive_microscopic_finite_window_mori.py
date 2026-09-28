#!/usr/bin/env python3
"""Assemble the trajectory-free XXX finite-window Mori hierarchy.

The report keeps four logically different levels separate:

1. the exact giant-string TBA amplitude ``D0=5*pi/27``;
2. the thermal-fluctuation/KPZ self-consistency used to obtain ``lambda``;
3. a *candidate* first scale correction obtained from the analytically
   tractable spectral regulator, not from the full finite-field diffusion
   matrix;
4. constant Burgers coefficients obtained by declared finite-window
   projections of the resulting theoretical wall.

No Heisenberg trajectory and no target ``a,D`` are accepted as inputs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.derive_kpz_lanczos_terminator import (  # noqa: E402
    _load_table,
    scale_correction_structure_laplace,
    scaled_structure_laplace,
)
from scripts.derive_theory_only_hierarchy import derive as derive_hierarchy  # noqa: E402
from src.heisenberg_burgers_bridge import (  # noqa: E402
    EXACT_D0_INFINITY_T,
    SPECTRAL_REGULATOR_D1_INFINITY_T,
    finite_field_scale_correction,
    giant_string_diffusion_amplitude_quadrature,
    kpz_lambda_from_tba,
    kpz_mori_laplace_first_correction,
    xxx_mori_long_wave_lanczos,
)


def derive(
    table: np.ndarray,
    *,
    t_start: float,
    t_stop: float,
    scaled_frequencies: np.ndarray,
    quadrature_order: int,
) -> dict[str, object]:
    if not 0.0 < t_start < t_stop:
        raise ValueError("Require 0<t_start<t_stop")
    scaled_frequencies = np.asarray(scaled_frequencies, dtype=float)
    if (
        scaled_frequencies.ndim != 1
        or scaled_frequencies.size == 0
        or np.any(~np.isfinite(scaled_frequencies))
        or np.any(scaled_frequencies <= 0.0)
    ):
        raise ValueError("scaled frequencies must be a positive finite vector")

    d0_quadrature = giant_string_diffusion_amplitude_quadrature(
        quadrature_order=quadrature_order
    )
    lam = kpz_lambda_from_tba()
    scale_correction = finite_field_scale_correction()
    phi0 = scaled_structure_laplace(
        table, scaled_frequencies, quadrature_order=quadrature_order
    )
    phi1 = scale_correction_structure_laplace(
        table,
        scaled_frequencies,
        scale_correction,
        quadrature_order=quadrature_order,
    )
    # The correction is k-independent at this order; a nonzero dummy k only
    # enforces the domain of the exact inversion helper.
    delta_kernel = kpz_mori_laplace_first_correction(
        np.ones_like(scaled_frequencies), phi0, phi1, lambda_kpz=lam
    )
    lanczos = xxx_mori_long_wave_lanczos()

    return {
        "schema_version": 1,
        "inputs": {
            "microscopic_model": "spin-1/2 isotropic Heisenberg chain, J=1",
            "state": "infinite temperature, zero magnetization",
            "initial_condition_for_wall_projection": (
                "infinitesimal sharp magnetization wall"
            ),
            "time_window": [float(t_start), float(t_stop)],
            "trajectory_data_used": False,
            "target_coefficients_used": False,
        },
        "exact_tba": {
            "D0_closed_form": float(EXACT_D0_INFINITY_T),
            "D0_giant_string_quadrature": d0_quadrature,
            "relative_quadrature_error": float(
                d0_quadrature / EXACT_D0_INFINITY_T - 1.0
            ),
            "identity": "D0=lim_{h->0} h D(h)=5*pi/27",
        },
        "kpz_self_consistency": {
            "lambda": float(lam),
            "status": (
                "uses giant-string thermal-fluctuation self-consistency and "
                "the universal stationary-KPZ variance; not a TBA identity"
            ),
        },
        "candidate_first_correction": {
            "source": "analytic finite-field spectral regulator",
            "D1_spectral": float(SPECTRAL_REGULATOR_D1_INFINITY_T),
            "front_scale_correction": float(scale_correction),
            "physical_full_diffusion_D1_claimed": False,
            "scaled_frequency": scaled_frequencies.tolist(),
            "Phi0": np.asarray(phi0).tolist(),
            "Phi1": np.asarray(phi1).tolist(),
            "delta_K1": np.asarray(delta_kernel).tolist(),
            "formula": "delta_K1=-lambda^(4/3)*Phi1/Phi0^2",
        },
        "exact_microscopic_short_time_end": {
            "maximum_even_moment": 26,
            "mu0": float(lanczos["mu0"]),
            "mu18": float(lanczos["mu18"]),
            "mu20": float(lanczos["mu20"]),
            "mu22": float(lanczos["mu22"]),
            "mu24": float(lanczos["mu24"]),
            "mu26": float(lanczos["mu26"]),
            "squared_lanczos_recurrents": np.asarray(
                lanczos["squared_recurrents"]
            ).tolist(),
            "continuum_terminator_still_required": True,
        },
        "finite_window_projection": derive_hierarchy(t_start, t_stop),
        "identifiability": {
            "physical_F1_uniquely_fixed": False,
            "reason": (
                "the exact moments through mu26 and the KPZ low-frequency "
                "tail do not determine the intermediate-frequency spectral "
                "measure; the spectral-regulator F1 is one microscopic "
                "candidate rather than a proof of the full finite-time kernel"
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kpz-table", type=Path)
    parser.add_argument("--t-start", type=float, default=50.0)
    parser.add_argument("--t-stop", type=float, default=200.0)
    parser.add_argument(
        "--scaled-frequencies",
        type=float,
        nargs="+",
        default=[0.5, 0.75, 1.0, 1.5, 2.0],
    )
    parser.add_argument("--quadrature-order", type=int, default=600)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = derive(
        _load_table(args.kpz_table),
        t_start=args.t_start,
        t_stop=args.t_stop,
        scaled_frequencies=np.asarray(args.scaled_frequencies),
        quadrature_order=args.quadrature_order,
    )
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
