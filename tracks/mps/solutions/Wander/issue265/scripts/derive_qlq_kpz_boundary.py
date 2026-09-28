#!/usr/bin/env python3
"""Match the KPZ current-tail amplitude to the microscopic QLQ resolvent.

For a stationary KPZ density with second scaled moment m2 and
ell(t)=(lambda*t)^(2/3), continuity fixes the long-time total-current
correlator.  The exact slow-current norm and QLP force norm then convert this
tail into the absolute small-z coefficient of the normalized QLQ resolvent.
No transport trajectory or target Burgers coefficient is used.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
from scipy.special import gamma


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_theory_finite_size_lattice import _load_spline  # noqa: E402
from src.heisenberg_burgers_bridge import kpz_lambda_from_tba  # noqa: E402


def derive(table: Path | None, microscopic: Path) -> dict[str, object]:
    spline = _load_spline(table)
    y = np.linspace(0.0, float(spline.x[-1]), 20001)
    density = np.maximum(np.asarray(spline(y, 2), dtype=float) / 4.0, 0.0)
    raw_normalization = float(2.0 * np.trapezoid(density, y))
    density /= raw_normalization
    scaled_second_moment = float(2.0 * np.trapezoid(y**2 * density, y))

    payload = json.loads(microscopic.read_text(encoding="utf-8"))
    analytic = payload["analytic_infinite_tail_first_recurrent"]
    current_norm = float(analytic["projected_current_norm"])
    force_norm = float(analytic["qlp_force_norm"])
    beta_zero_squared = force_norm / current_norm
    susceptibility = 0.25
    lambda_kpz = float(kpz_lambda_from_tba())

    # M2=m2*(lambda*t)^(4/3), and continuity gives
    # C_jj(t)=chi*M2''(t)/2.
    current_tail_time_amplitude = float(
        susceptibility
        * (2.0 / 9.0)
        * scaled_second_moment
        * lambda_kpz ** (4.0 / 3.0)
    )
    current_tail_laplace_amplitude = float(
        current_tail_time_amplitude * gamma(1.0 / 3.0)
    )

    # C_P(z)=wP/[z+beta0^2 R_Q(z)].  Matching C_P~A*z^(-1/3)
    # fixes R_Q~r0*z^(1/3).
    qlq_resolvent_amplitude = float(
        current_norm / (beta_zero_squared * current_tail_laplace_amplitude)
    )
    # If dnu=rho(omega)domega and rho~c*omega^(1/3), then
    # R_Q=int z/(z^2+omega^2)dnu ~ c*pi/sqrt(3)*z^(1/3).
    qlq_density_amplitude = float(
        qlq_resolvent_amplitude * np.sqrt(3.0) / np.pi
    )
    return {
        "schema_version": 1,
        "method": "continuity_KPZ_second_moment_to_microscopic_QLQ_boundary",
        "inputs": {
            "trajectory_data_used": False,
            "target_coefficients_used": False,
            "slow_projector_cutoff": float(payload["inputs"]["cutoff_wave_number"]),
            "susceptibility": susceptibility,
        },
        "kpz": {
            "table_raw_density_normalization": raw_normalization,
            "scaled_second_moment_m2": scaled_second_moment,
            "lambda": lambda_kpz,
            "current_tail": {
                "time_domain": f"C_jj(t)~{current_tail_time_amplitude:.17g}*t^(-2/3)",
                "time_amplitude": current_tail_time_amplitude,
                "laplace_domain": f"C_jj(z)~{current_tail_laplace_amplitude:.17g}*z^(-1/3)",
                "laplace_amplitude": current_tail_laplace_amplitude,
            },
        },
        "microscopic_slow_current": {
            "norm": current_norm,
            "qlp_force_norm": force_norm,
            "beta_zero_squared": beta_zero_squared,
        },
        "qlq_low_frequency_boundary": {
            "normalized_resolvent": f"R_Q(z)~{qlq_resolvent_amplitude:.17g}*z^(1/3)",
            "resolvent_amplitude": qlq_resolvent_amplitude,
            "positive_symmetric_spectral_density": f"rho_Q(omega)~{qlq_density_amplitude:.17g}*omega^(1/3)",
            "spectral_density_amplitude": qlq_density_amplitude,
        },
        "gates": {
            "microscopic_norms_positive": bool(current_norm > 0.0 and force_norm > 0.0),
            "kpz_density_normalized": bool(abs(raw_normalization - 1.0) < 1.0e-5),
            "absolute_low_frequency_amplitude_fixed": True,
            "intermediate_frequency_continuum_uniquely_fixed": False,
        },
        "scope": {
            "assumption": "stationary_KPZ_scaling_and_slow_projector_carries_the_full_long_time_current_tail",
            "remaining_unknown": "positive_QLQ_spectral_density_away_from_omega_to_zero",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kpz-table", type=Path)
    parser.add_argument(
        "--microscopic",
        type=Path,
        default=ROOT / "docs/xxx_thermodynamic_qlq_pi4_R128_steps5.json",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = derive(args.kpz_table, args.microscopic)
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
