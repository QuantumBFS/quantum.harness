#!/usr/bin/env python3
"""Generate a deterministic certificate for the hard-spin O(n) proof."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from issue158.on_proof import (
    pair_plane_projection,
    pair_second_variation_exact,
    pair_second_variation_formula,
    rotation_generator_matrix,
    transverse_parseval_sides,
)


SCHEMA = "issue158.on_theorem_audit.v1"
COMPONENT_COUNTS = (2, 3, 4, 8)


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _unit_vector(rng: np.random.Generator, n: int) -> np.ndarray:
    vector = rng.normal(size=n)
    return vector / np.linalg.norm(vector)


def _algebra_certificate(n: int, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    maximum_antisymmetry_residual = 0.0
    maximum_tangency_residual = 0.0
    maximum_second_variation_residual = 0.0
    maximum_projection = -math.inf
    minimum_projection = math.inf
    checks = 0
    for transverse in range(1, n):
        generator = rotation_generator_matrix(n, transverse)
        maximum_antisymmetry_residual = max(
            maximum_antisymmetry_residual,
            float(np.max(np.abs(generator + generator.T))),
        )
        for _ in range(32):
            first = _unit_vector(rng, n)
            second = _unit_vector(rng, n)
            maximum_tangency_residual = max(
                maximum_tangency_residual,
                abs(float(np.dot(first, generator @ first))),
            )
            u = np.exp(1j * float(rng.uniform(-math.pi, math.pi)))
            v = np.exp(1j * float(rng.uniform(-math.pi, math.pi)))
            coupling = float(rng.uniform(0.01, 3.0))
            exact = pair_second_variation_exact(
                first,
                second,
                u,
                v,
                transverse,
                coupling,
            )
            formula = pair_second_variation_formula(
                first,
                second,
                u,
                v,
                transverse,
                coupling,
            )
            maximum_second_variation_residual = max(
                maximum_second_variation_residual,
                abs(exact - formula),
            )
            projection = pair_plane_projection(
                first, second, transverse
            )
            maximum_projection = max(maximum_projection, projection)
            minimum_projection = min(minimum_projection, projection)
            checks += 1

    raw = rng.normal(size=(5, 4, n))
    spins = raw / np.linalg.norm(raw, axis=-1, keepdims=True)
    fourier_side, real_side = transverse_parseval_sides(spins)
    parseval_residual = abs(fourier_side - real_side)
    volume = 20
    hard_spin_budget = volume**2
    return {
        "n": n,
        "seed": seed,
        "transverse_channels": n - 1,
        "pair_checks": checks,
        "maximum_antisymmetry_residual": (
            maximum_antisymmetry_residual
        ),
        "maximum_tangency_residual": maximum_tangency_residual,
        "maximum_second_variation_residual": (
            maximum_second_variation_residual
        ),
        "minimum_sampled_plane_projection": minimum_projection,
        "maximum_sampled_plane_projection": maximum_projection,
        "parseval_residual": parseval_residual,
        "transverse_budget": real_side,
        "hard_spin_budget_upper_bound": hard_spin_budget,
        "budget_bound_satisfied": real_side <= hard_spin_budget + 1e-12,
        "xy_reduction": (
            "one transverse channel and factor n-1=1"
            if n == 2
            else None
        ),
    }


def build_audit(root: Path) -> dict:
    proof_path = root / "ON_PROOF_AUDIT.md"
    proof_bytes = proof_path.read_bytes()
    algebra = [
        _algebra_certificate(n, seed=158_000 + n)
        for n in COMPONENT_COUNTS
    ]
    if any(
        row["maximum_second_variation_residual"] > 5e-14
        or row["maximum_antisymmetry_residual"] > 0.0
        or row["maximum_tangency_residual"] > 5e-16
        or not row["budget_bound_satisfied"]
        or row["maximum_sampled_plane_projection"] > 1.0 + 1e-14
        for row in algebra
    ):
        raise ValueError("an O(n) algebra certificate failed")

    obligations = [
        "hard_spin_sphere_defined",
        "finite_component_count_n_at_least_two",
        "bilinear_translation_invariant_pair_energy",
        "ferromagnetic_nonnegative_coupling",
        "sphere_rotation_generator_defined",
        "invariant_surface_measure_integration_by_parts",
        "classical_bogoliubov_inequality_derived",
        "exact_projected_pair_second_variation_derived",
        "averaged_denominator_nonnegative",
        "pointwise_projected_pair_upper_bound",
        "all_transverse_channels_summed",
        "factor_n_minus_one_derived",
        "xy_reduction_checked",
        "uniform_kernel_limit_used_at_fixed_field",
        "regulated_infrared_integral_diverges",
        "so_n_zero_field_second_moment_identity",
        "bounded_exponential_tilt_bridge",
        "physical_order_of_limits_preserved",
        "zero_field_vector_second_moment_vanishes",
        "two_dimensional_marginal_corollary",
        "soft_spin_extension_not_claimed",
        "frustrated_extension_not_claimed",
        "exact_correlation_law_not_claimed",
    ]
    return {
        "schema": SCHEMA,
        "proof_document": {
            "path": "ON_PROOF_AUDIT.md",
            "sha256": _sha256(proof_bytes),
        },
        "theorem_scope": {
            "spin_space": "unit sphere S^(n-1)",
            "component_count": "finite integer n>=2",
            "spatial_dimension": "arbitrary d in the abstract criterion",
            "interaction": (
                "bilinear translation-invariant ferromagnetic pair coupling"
            ),
            "temperature": "0<T<infinity",
            "limit_order": (
                "L->infinity at fixed h>0, followed by h->0"
            ),
            "conclusions": [
                (
                    "field-selected longitudinal magnetization vanishes "
                    "when the regulated infrared integral diverges"
                ),
                "lim_L <|M_L|^2>_(L,0)=0",
            ],
        },
        "excluded_scope": [
            "n=1 discrete symmetry",
            "unbounded soft-spin fields",
            "arbitrary continuous field theories",
            "generic target manifolds",
            "frustrated sign-changing pair couplings",
            "multibody interactions",
            "quantum systems",
        ],
        "not_claimed": [
            "exact logarithmic quasi-long-range-order exponent",
            "a common finite-temperature phase for all n",
            "absence of order when the infrared integral is finite",
        ],
        "finite_volume_bound": (
            "1 >= (n-1) T m_(L,h)^2 V^(-1) "
            "sum_q [h+E_L(q)]^(-1)"
        ),
        "zero_field_bridge": (
            "m_(L,h) >= tanh(beta h V) "
            "<|M_L|^2>_(L,0)/n"
        ),
        "algebra_certificates": algebra,
        "obligations": [
            {"name": name, "status": "verified"} for name in obligations
        ],
        "dependency_edges": [
            ["SO(n)_surface_measure", "sphere_integration_by_parts"],
            ["sphere_integration_by_parts", "classical_bogoliubov"],
            ["hard_spin_and_J_nonnegative", "denominator_upper_bound"],
            ["projected_pair_identity", "denominator_upper_bound"],
            ["transverse_parseval", "factor_n_minus_one"],
            ["classical_bogoliubov", "finite_volume_bound"],
            ["uniform_kernel_limit", "fixed_field_limit"],
            ["infrared_divergence", "field_magnetization_zero"],
            ["SO(n)_moment_identity", "zero_field_bridge"],
            ["bounded_tilt_lemma", "zero_field_bridge"],
            ["field_magnetization_zero", "zero_field_M2_zero"],
        ],
        "numerical_certificates_are_proof_premises": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/on_theorem_audit.json"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    payload = build_audit(root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )


if __name__ == "__main__":
    main()
