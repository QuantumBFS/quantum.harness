#!/usr/bin/env python3
"""Freeze the exact, finite-regulator statements closing GAPs 3, 4, 5 and 7."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    "docs/full_mode_mori_certificate.json",
    "docs/xxx_mori_mu26_certificate.json",
    "docs/nonlinear_mori_closure_no_go_certificate.json",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def derive() -> dict[str, object]:
    payload = {name: json.loads((ROOT / name).read_text()) for name in SOURCES}
    full = payload["docs/full_mode_mori_certificate.json"]
    moments = payload["docs/xxx_mori_mu26_certificate.json"]
    no_go = payload["docs/nonlinear_mori_closure_no_go_certificate.json"]

    ou = full["ou_covariance"]
    projected = full["projected_mori"]
    spin_flip = full["spin_flip_certificate"]
    wall = full["sharp_product_wall_mori_certificate"]
    recurrent_count = int(no_go["exact_prefix"]["recurrent_count"])

    statements = {
        "gap3": {
            "closed_statement": (
                "For every declared finite GHD regulator, the linear fluctuating "
                "theory is an Ornstein-Uhlenbeck process with exact covariance "
                "Sigma(t)=C+exp(Lt)[Sigma(0)-C]exp(L^dagger t)."
            ),
            "stationary_covariance_relative_residual": float(
                ou["stationary_initial_covariance_relative_residual"]
            ),
            "maximum_hermiticity_residual": float(
                ou["maximum_hermiticity_residual"]
            ),
            "closed": bool(
                ou["stationary_initial_covariance_relative_residual"] < 1e-13
                and ou["maximum_hermiticity_residual"] < 1e-13
                and min(ou["accumulated_noise_minimum_eigenvalues"]) >= -1e-13
            ),
            "not_claimed": "uniform convergence of the h->0 infinite-mode limit",
        },
        "gap4": {
            "closed_statement": (
                "Schur elimination of every retained non-spin mode gives the "
                "exact frequency-dependent scalar Mori resolvent.  The exact "
                "mu26 prefix gives thirteen positive recurrents but does not "
                "choose a unique positive terminator."
            ),
            "maximum_resolvent_inversion_residual": float(
                projected["maximum_resolvent_inversion_residual"]
            ),
            "maximum_even_moment_order": int(moments["maximum_even_moment_order"]),
            "exact_recurrent_count": recurrent_count,
            "constructive_terminator_nonidentifiability": bool(
                no_go["gates"]["nonidentifiability_no_go_certified"]
            ),
            "closed": bool(
                projected["maximum_resolvent_inversion_residual"] < 1e-13
                and moments["accepted"]
                and recurrent_count == 13
                and no_go["gates"]["nonidentifiability_no_go_certified"]
            ),
            "not_claimed": "a unique physical low-frequency terminator",
        },
        "gap5": {
            "closed_statement": (
                "Global pi spin rotation makes the physical current odd in the "
                "magnetic source, so the zero-field quadratic Kubo vertex "
                "vanishes.  A one-sided, orientation-conditioned wall coordinate "
                "is a different observable and may be nonzero."
            ),
            "physical_zero_field_quadratic_kubo_vertex": float(
                spin_flip["physical_zero_field_quadratic_kubo_vertex"]
            ),
            "conditional_coordinate_may_be_nonzero": bool(
                spin_flip["conditional_quadratic_basis_coordinate_may_be_nonzero"]
            ),
            "closed": bool(
                spin_flip["physical_zero_field_quadratic_kubo_vertex"] == 0.0
                and spin_flip["objects_are_identical"] is False
            ),
            "not_claimed": "universality of the conditional finite-window coordinate",
        },
        "gap7": {
            "closed_statement": (
                "The orientation-odd tangent of a sharp product wall is a linear "
                "combination of spin-density Fourier modes.  With those modes in "
                "the Mori projector, its linear initial slip is exactly zero."
            ),
            "linear_mori_initial_slip": float(wall["linear_mori_initial_slip"]),
            "maximum_bare_mu6": float(wall["maximum_bare_power_mu6"]),
            "closed": bool(
                wall["linear_operator_inside_spin_density_mori_subspace"]
                and wall["linear_mori_initial_slip"] == 0.0
            ),
            "not_claimed": (
                "a bound on the unknown O(mu^6) coefficient or a sharp-wall "
                "pointwise local-GGE expansion"
            ),
        },
    }
    return {
        "schema": 1,
        "method": "exact_finite_regulator_algebra_and_scoped_no_go",
        "uses_target_trajectory": False,
        "uses_target_a_or_D": False,
        "source_sha256": {name: _sha256(ROOT / name) for name in SOURCES},
        "statements": statements,
        "gates": {
            "gap3_scoped_statement_closed": statements["gap3"]["closed"],
            "gap4_scoped_statement_closed": statements["gap4"]["closed"],
            "gap5_scoped_statement_closed": statements["gap5"]["closed"],
            "gap7_scoped_statement_closed": statements["gap7"]["closed"],
            "all_four_scoped_statements_closed": bool(
                all(item["closed"] for item in statements.values())
            ),
        },
        "interpretation": (
            "Closure means the stated algebraic theorem is complete.  It does "
            "not silently promote a finite regulator, a conditional wall "
            "coordinate, or a finite moment prefix to a unique asymptotic "
            "constant-coefficient Burgers equation."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs/gap_3_4_5_7_completion_audit.json",
    )
    args = parser.parse_args()
    result = derive()
    encoded = json.dumps(result, indent=2) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(encoded)
    print(encoded, end="")


if __name__ == "__main__":
    main()
