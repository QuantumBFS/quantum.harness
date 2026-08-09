#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from math import lcm
from pathlib import Path

from trottercert.anticommuting import (
    AnticommutingPartitionCertificate,
    certify_anticommuting_partition,
    discover_anticommuting_partition,
)
from trottercert.pareto import minimum_published_suzuki_point
from trottercert.refined_error import (
    build_refined_fourth_order_constants,
    certified_d4_cell_coefficients,
    evaluate_refined_fourth_order_bound,
)
from trottercert.resources import required_steps
from trottercert.rigorous_fourth import (
    fourth_order_published_triangle_certificate,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "certificates" / "issue128-certificate.json"
D4_OUTPUT = ROOT / "certificates" / "issue128-d4-groups.json"


def pair(value: Fraction) -> list[int]:
    return [value.numerator, value.denominator]


def canonical_json_bytes(payload: dict[str, object]) -> bytes:
    return (
        json.dumps(payload, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()


def d4_sidecar_payload(
    certificate: AnticommutingPartitionCertificate,
) -> dict[str, object]:
    coefficient_denominator = 1
    for interval in certificate.coefficients:
        coefficient_denominator = lcm(
            coefficient_denominator,
            interval.lower.denominator,
            interval.upper.denominator,
        )
    sqrt_denominator = 1
    for group in certificate.groups:
        sqrt_denominator = lcm(
            sqrt_denominator,
            group.bound.denominator,
        )
    return {
        "schema_version": 1,
        "coefficient_denominator": coefficient_denominator,
        "terms": [
            [
                pauli[0],
                pauli[1],
                interval.lower.numerator
                * (
                    coefficient_denominator
                    // interval.lower.denominator
                ),
                interval.upper.numerator
                * (
                    coefficient_denominator
                    // interval.upper.denominator
                ),
            ]
            for pauli, interval in zip(
                certificate.paulis,
                certificate.coefficients,
            )
        ],
        "sqrt_denominator": sqrt_denominator,
        "groups": [
            [
                list(group.term_indices),
                group.bound.numerator
                * (sqrt_denominator // group.bound.denominator),
            ]
            for group in certificate.groups
        ],
        "cell_bound": pair(certificate.bound),
    }


def main() -> None:
    n_sites = 144
    tolerance = Fraction(1, 10**6)

    published = fourth_order_published_triangle_certificate(
        center=20,
        decimal_digits=18,
    )
    published_steps = required_steps(
        published.site_density_upper * n_sites,
        tolerance,
        4,
    )
    published_groups = 30 * published_steps + 1

    constants = build_refined_fourth_order_constants(
        decimal_digits=12,
        quantization_digits=18,
    )
    d4_coefficients = certified_d4_cell_coefficients(
        constants.stages,
        quantization_digits=18,
    )
    d4_groups = discover_anticommuting_partition(
        d4_coefficients,
        max_group_size=10,
    )
    d4_partition = certify_anticommuting_partition(
        d4_coefficients,
        d4_groups,
    )
    d4_payload = d4_sidecar_payload(d4_partition)
    d4_bytes = canonical_json_bytes(d4_payload)
    D4_OUTPUT.write_bytes(d4_bytes)
    d4_site_bound = d4_partition.bound / 4

    low = 1
    high = published_steps
    while low < high:
        middle = (low + high) // 2
        if (
            evaluate_refined_fourth_order_bound(
                constants,
                n_sites,
                middle,
                d4_site_override=d4_site_bound,
            ).global_error_bound
            <= tolerance
        ):
            high = middle
        else:
            low = middle + 1
    candidate_steps = low
    candidate = evaluate_refined_fourth_order_bound(
        constants,
        n_sites,
        candidate_steps,
        d4_site_override=d4_site_bound,
    )
    previous = evaluate_refined_fourth_order_bound(
        constants,
        n_sites,
        candidate_steps - 1,
        d4_site_override=d4_site_bound,
    )
    candidate_groups = 30 * candidate_steps + 1

    recursive_points = []
    for order in (2, 4, 6, 8):
        point = minimum_published_suzuki_point(
            order,
            n_sites=n_sites,
            tolerance=tolerance,
            decimal_digits=12,
        )
        recursive_points.append(
            {
                "order": point.order,
                "steps": point.steps,
                "stages_per_step": point.stages_per_step,
                "group_exponentials": point.group_exponentials,
                "global_error_upper_decimal_summary": format(
                    float(point.global_error_bound),
                    ".17g",
                ),
            }
        )

    baseline_bonds = published_groups * n_sites // 2
    candidate_bonds = candidate_groups * n_sites // 2
    certificate = {
        "schema_version": 3,
        "benchmark": {
            "model": "periodic_square_spin_half_isotropic_heisenberg",
            "normalization": "(XX+YY+ZZ)/4",
            "length": 12,
            "time": [1, 1],
            "tolerance": [1, 10**6],
            "primary_certified_metric": "compiled_cnot_upper",
        },
        "published_baseline": {
            "source_theorem": "Childs_Su_Tran_Wiebe_Zhu_high_order_commutator_bound",
            "formula": "five_copy_suzuki_fourth_order",
            "formula_order": 4,
            "stage_count": 31,
            "theorem_center": 20,
            "coefficient_interval_decimal_digits": 18,
            "norm_method": "expand_partial_sums_then_local_Pauli_l1",
            "site_density_upper": pair(published.site_density_upper),
            "theorem_terms": published.theorem_terms,
            "expanded_commutator_keys": published.expanded_commutator_keys,
            "steps": published_steps,
            "group_exponentials": published_groups,
        },
        "candidate": {
            "formula": "five_copy_suzuki_fourth_order",
            "proof_method": (
                "local_log_E5_grouped_D4_plus_E7_majorant"
                "_plus_exact_generator_tail"
            ),
            "coefficient_interval_decimal_digits": 12,
            "e5_quantization_digits": 18,
            "e5_site_l1_upper": pair(constants.e5_site_l1),
            "e7_site_majorant": pair(constants.e7_site_majorant),
            "d4_certificate": {
                "path": D4_OUTPUT.name,
                "sha256": hashlib.sha256(d4_bytes).hexdigest(),
                "max_group_size": 10,
                "term_count": len(d4_partition.paulis),
                "group_count": len(d4_partition.groups),
                "cell_norm_upper": pair(d4_partition.bound),
            },
            "steps": candidate_steps,
            "group_exponentials": candidate_groups,
            "contributions": {
                "degree4": pair(candidate.degree_four_contribution),
                "degree5": pair(candidate.degree_five_contribution),
                "degree6": pair(candidate.degree_six_contribution),
                "degree7": pair(candidate.degree_seven_contribution),
                "tail": pair(candidate.tail_contribution),
            },
            "global_error_upper": pair(candidate.global_error_bound),
            "previous_step_error_upper": pair(previous.global_error_bound),
        },
        "cost_model": {
            "bonds_per_matching": n_sites // 2,
            "cnots_per_bond_propagator": 3,
            "inter_step_merge_rule": "30*r+1",
        },
        "claimed_resources": {
            "published_steps": published_steps,
            "candidate_steps": candidate_steps,
            "published_group_exponentials": published_groups,
            "candidate_group_exponentials": candidate_groups,
            "published_bond_propagators": baseline_bonds,
            "candidate_bond_propagators": candidate_bonds,
            "published_cnot_upper": 3 * baseline_bonds,
            "candidate_cnot_upper": 3 * candidate_bonds,
        },
        "published_recursive_suzuki_audit": recursive_points,
        "claims": {
            "global_twofold_target_met": published_groups >= 2 * candidate_groups,
            "global_fourfold_target_met": (
                published_groups >= 4 * candidate_groups
            ),
            "exact_improvement_ratio": pair(
                Fraction(published_groups, candidate_groups)
            ),
        },
    }
    OUTPUT.write_text(json.dumps(certificate, indent=2) + "\n")
    print(D4_OUTPUT)
    print(OUTPUT)
    print(
        json.dumps(
            {
                "published_groups": published_groups,
                "candidate_groups": candidate_groups,
                "improvement": published_groups / candidate_groups,
                "candidate_error": float(candidate.global_error_bound),
                "previous_error": float(previous.global_error_bound),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
