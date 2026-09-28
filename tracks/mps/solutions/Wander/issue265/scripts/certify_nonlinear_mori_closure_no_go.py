#!/usr/bin/env python3
"""Certify what the microscopic moments can and cannot fix in GAP 6."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.heisenberg_burgers_bridge import (  # noqa: E402
    mori_kernel_from_lanczos_terminator,
    mori_lanczos_stieltjes_bounds,
    xxx_mori_long_wave_lanczos,
)


SOURCES = (
    "docs/xxx_mori_mu26_certificate.json",
    "docs/mori_uv_local_counterterm_audit.json",
    "docs/mu20_moment_preserving_one_loop_audit.json",
    "docs/mu22_prefix_moment_preserving_one_loop_audit.json",
    "docs/iterated_full_diffusion_limit_audit.json",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def derive() -> dict[str, object]:
    source_payload = {
        name: json.loads((ROOT / name).read_text()) for name in SOURCES
    }
    lanczos = xxx_mori_long_wave_lanczos()
    squared = np.asarray(lanczos["squared_recurrents"], dtype=float)
    mu0 = float(lanczos["mu0"])
    z = np.asarray([0.02, 0.05, 0.1], dtype=float)
    bounds = mori_lanczos_stieltjes_bounds(z, mu0, squared)

    # Two unit-mass positive symmetric spectral measures.  Both terminators
    # have T(z)=1/z+O(z^-3), hence reinserting either behind the exact prefix
    # preserves every known recurrent/moment; their low-frequency kernels are
    # nevertheless different.
    omega_slow = 0.5
    omega_fast = 5.0
    terminator_slow = z / (z**2 + omega_slow**2)
    terminator_fast = z / (z**2 + omega_fast**2)
    kernel_slow = mori_kernel_from_lanczos_terminator(
        z, terminator_slow, mu0, squared
    )
    kernel_fast = mori_kernel_from_lanczos_terminator(
        z, terminator_fast, mu0, squared
    )
    separation = np.abs(kernel_slow - kernel_fast)
    relative_separation = separation / np.maximum(
        0.5 * np.abs(kernel_slow + kernel_fast), np.finfo(float).tiny
    )

    uv = source_payload["docs/mori_uv_local_counterterm_audit.json"]
    mu20 = source_payload["docs/mu20_moment_preserving_one_loop_audit.json"]
    mu22 = source_payload["docs/mu22_prefix_moment_preserving_one_loop_audit.json"]
    gap1 = source_payload["docs/iterated_full_diffusion_limit_audit.json"]
    exact = source_payload["docs/xxx_mori_mu26_certificate.json"]
    premises = {
        "thirteen_exact_positive_recurrents": bool(
            exact["accepted"]
            and exact["maximum_even_moment_order"] == 26
            and squared.size == 13
            and np.all(squared > 0.0)
        ),
        "two_positive_unit_mass_terminators_preserve_prefix": True,
        "two_terminators_give_distinct_low_frequency_kernels": bool(
            np.all(separation > 0.0)
        ),
        "finite_local_orders_0_through_4_fail_common_uv_stability": bool(
            not uv["gates"]["some_single_local_order_stabilizes_all_probes"]
        ),
        "mu20_matching_fails_positivity_cutoff_gates": bool(
            not mu20["gates"]["physical_F1_perp_certified"]
        ),
        "mu22_extension_still_fails_matching_gates": bool(
            not mu22["gates"]["physical_F1_perp_certified"]
        ),
        "zero_field_boundary_input_not_yet_matched": bool(
            not gap1["gates"]["regulated_xi_boundary_counterterm_derived"]
        ),
    }
    no_go = bool(all(premises.values()))
    return {
        "schema": 1,
        "method": "constructive_positive_terminator_nonidentifiability_and_uv_gate",
        "uses_target_trajectory": False,
        "uses_target_a_or_D": False,
        "source_sha256": {name: _sha256(ROOT / name) for name in SOURCES},
        "exact_prefix": {
            "maximum_even_moment_order": 26,
            "recurrent_count": int(squared.size),
            "squared_recurrents": squared.tolist(),
        },
        "laplace_frequency": z.tolist(),
        "stieltjes_bounds": {
            "lower": np.asarray(bounds["lower"]).tolist(),
            "upper": np.asarray(bounds["upper"]).tolist(),
        },
        "constructive_counterexample": {
            "slow_atom_frequency": omega_slow,
            "fast_atom_frequency": omega_fast,
            "slow_kernel": np.asarray(kernel_slow).tolist(),
            "fast_kernel": np.asarray(kernel_fast).tolist(),
            "absolute_separation": separation.tolist(),
            "relative_separation": relative_separation.tolist(),
            "both_spectral_measures_positive": True,
            "both_spectral_measures_unit_mass": True,
            "both_preserve_all_known_recurrents": True,
        },
        "premises": premises,
        "gates": {
            "finite_microscopic_prefix_uniquely_determines_nonlinear_kernel": False,
            "tested_local_counterterms_renormalize_bare_one_loop": False,
            "current_hydrodynamic_vertices_define_physical_F1_perp": False,
            "unique_constant_burgers_pair_follows_analytically": False,
            "nonidentifiability_no_go_certified": no_go,
        },
        "scope": {
            "closed_statement": (
                "No regulator-independent nonlinear Mori correction or "
                "constant Burgers pair follows from the known finite moment "
                "prefix plus the bare hydrodynamic one-loop vertices."
            ),
            "not_claimed": (
                "The physical full Mori kernel is not absent; it requires an "
                "additional microscopic spectral/renormalization condition "
                "and the GAP-1 zero-field boundary match."
            ),
            "controlled_equation_retained": (
                "exact projected Mori equation with a positive continuum "
                "terminator constrained, but not fixed, by the exact prefix"
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs/nonlinear_mori_closure_no_go_certificate.json",
    )
    args = parser.parse_args()
    result = derive()
    encoded = json.dumps(result, indent=2) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(encoded)
    print(encoded, end="")


if __name__ == "__main__":
    main()
