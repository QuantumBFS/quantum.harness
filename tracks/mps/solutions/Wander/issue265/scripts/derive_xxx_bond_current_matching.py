#!/usr/bin/env python3
"""Fix the microscopic XXX bond-current side of Mori/GHD matching.

This certificate starts from the exchange Hamiltonian, not from a lattice
regularization of a continuum GHD equation.  It proves the exact bond-centred
Fourier continuity identity, records the finite-momentum microscopic Mori
moments available in closed form, and states precisely which part still has
to be supplied by a no-double-counting slow/orthogonal spectral projection.
No transport trajectory or target Burgers coefficient is read.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.derive_xxx_mori_lanczos import (  # noqa: E402
    microscopic_bond_current_continuity_certificate,
)
from src.heisenberg_burgers_bridge import (  # noqa: E402
    xxx_mori_even_moments,
    xxx_mori_lanczos_recurrents,
    xxx_mori_long_wave_lanczos,
)


def derive(length: int, modes: tuple[int, ...]) -> dict[str, object]:
    if length < 4 or not modes:
        raise ValueError("length and modes must be non-empty")
    if min(modes) <= 0 or max(modes) >= length:
        raise ValueError("modes must be nonzero periodic Fourier indices")

    rows = []
    for mode in modes:
        continuity = microscopic_bond_current_continuity_certificate(
            length, mode
        )
        k = float(continuity["k"])
        moments = xxx_mori_even_moments(np.asarray(k))
        rows.append(
            {
                "mode": int(mode),
                "k": k,
                "khat": float(continuity["khat"]),
                "continuity_relative_operator_residual": float(
                    continuity["relative_operator_residual"]
                ),
                "density_susceptibility": float(
                    continuity["density_susceptibility"]
                ),
                "bond_current_norm": float(continuity["bond_current_norm"]),
                "density_commutator_norm": float(
                    continuity["density_commutator_norm"]
                ),
                "closed_mori_even_moments": {
                    str(order): float(value)
                    for order, value in moments.items()
                },
                "finite_k_squared_lanczos_recurrents": (
                    np.asarray(xxx_mori_lanczos_recurrents(np.asarray(k)))
                    .astype(float)
                    .tolist()
                ),
            }
        )

    long_wave = xxx_mori_long_wave_lanczos()
    return {
        "schema": 1,
        "method": "exact_xxx_bond_current_pauli_continuity_and_mori_prefix",
        "inputs": {
            "length": int(length),
            "modes": list(modes),
            "exchange": 1.0,
            "temperature": "infinite",
            "trajectory_data_used": False,
            "target_coefficients_used": False,
        },
        "microscopic_identity": {
            "hamiltonian": "H=sum_x S_x dot S_{x+1}",
            "bond_current": (
                "j_{x+1/2}=S_x^x S_{x+1}^y-S_x^y S_{x+1}^x"
            ),
            "fourier_continuity": (
                "d_t S^z_k=-i*2*sin(k/2)*j_{k,bond-centred}"
            ),
            "external_lattice_symbol_fixed_exactly": True,
            "replacement_of_internal_ghd_momenta_fixed_by_identity": False,
        },
        "rows": rows,
        "long_wave_exact_prefix": {
            "mu0": float(long_wave["mu0"]),
            "mu18": float(long_wave["mu18"]),
            "mu20": float(long_wave["mu20"]),
            "mu22": float(long_wave["mu22"]),
            "mu24": float(long_wave["mu24"]),
            "mu26": float(long_wave["mu26"]),
            "squared_recurrents": (
                np.asarray(long_wave["squared_recurrents"])
                .astype(float)
                .tolist()
            ),
        },
        "matching_equation": {
            "exact_current_split": "j=P_slow j+Q_slow j",
            "no_double_counting_condition": "<P_slow j,Q_slow j>_Kubo=0",
            "slow_part": (
                "full infinite-mode GHD projection, including all non-diagonal "
                "diffusion and FDT noise"
            ),
            "orthogonal_part": (
                "positive Mori continuum constrained by the exact finite-k "
                "moments and the long-wave mu26 prefix"
            ),
        },
        "gates": {
            "all_microscopic_continuity_residuals_zero": bool(
                all(row["continuity_relative_operator_residual"] == 0.0 for row in rows)
            ),
            "microscopic_short_time_side_fixed": True,
            "slow_orthogonal_spectral_split_evaluated": False,
            "finite_window_kernel_unique": False,
            "unique_a_D_claimed": False,
        },
        "conclusion": (
            "The XXX lattice fixes the external bond-divergence symbol and the "
            "microscopic Mori prefix exactly.  It does not license replacing "
            "every internal continuum-GHD momentum by 2*sin(p/2).  The next "
            "required operation is the Kubo-orthogonal P/Q spectral split."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--length", type=int, default=400)
    parser.add_argument("--modes", type=int, nargs="+", default=[1, 2, 3, 4])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = derive(args.length, tuple(args.modes))
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(encoded, end="")
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
