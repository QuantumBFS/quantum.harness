from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

from .baseline import pauli_l1_second_order_constant
from .hamiltonian import four_matching_fragments
from .lattice import SquareLattice
from .resources import (
    fourth_order_four_matching_resources,
    four_matching_resources,
    required_steps,
    three_l_path_resources,
)
from .intervals import cube_root_four_interval
from .su2clusters import three_l_path_fragments


EXPECTED_NORMALIZATION = "(XX+YY+ZZ)/4"


def _fraction(pair: list[int]) -> Fraction:
    if len(pair) != 2:
        raise ValueError("fraction must be [numerator, denominator]")
    return Fraction(pair[0], pair[1])


def _verify_v1(data: dict[str, object]) -> dict[str, object]:
    benchmark = data["benchmark"]
    if benchmark["normalization"] != EXPECTED_NORMALIZATION:
        raise ValueError("Hamiltonian normalization mismatch")
    length = int(benchmark["length"])
    if length % 6:
        raise ValueError("benchmark length must be divisible by six")
    tolerance = _fraction(benchmark["tolerance"])
    reference_length = int(data["proof"]["reference_length"])
    if reference_length != 6:
        raise ValueError("the verifier currently pins reference length L=6")

    lattice = SquareLattice(reference_length)
    baseline_ref = pauli_l1_second_order_constant(
        four_matching_fragments(lattice)
    )
    candidate_ref = pauli_l1_second_order_constant(
        three_l_path_fragments(lattice)
    )
    baseline_density = baseline_ref / lattice.n_sites
    candidate_density = candidate_ref / lattice.n_sites
    if baseline_density != _fraction(data["proof"]["baseline_density"]):
        raise ValueError("baseline density summary is inconsistent")
    if candidate_density != _fraction(data["proof"]["candidate_density"]):
        raise ValueError("candidate density summary is inconsistent")

    n_sites = length * length
    baseline_constant = baseline_density * n_sites
    candidate_constant = candidate_density * n_sites
    baseline_steps = required_steps(baseline_constant, tolerance, 2)
    candidate_steps = required_steps(candidate_constant, tolerance, 2)
    baseline = four_matching_resources(n_sites, baseline_steps)
    candidate = three_l_path_resources(n_sites, candidate_steps)

    claimed = data["claimed_resources"]
    recomputed = {
        "baseline_steps": baseline.steps,
        "candidate_steps": candidate.steps,
        "baseline_local_propagators": baseline.local_propagators,
        "candidate_local_propagators": candidate.local_propagators,
        "baseline_cnot_upper": baseline.cnot_upper,
        "candidate_cnot_upper": candidate.cnot_upper,
    }
    if claimed != recomputed:
        raise ValueError("claimed resources do not match recomputation")
    local_ratio = Fraction(
        candidate.local_propagators,
        baseline.local_propagators,
    )
    return {
        "valid": True,
        "baseline_density": str(baseline_density),
        "candidate_density": str(candidate_density),
        "local_propagator_ratio": str(local_ratio),
        "local_propagator_improvement": float(1 / local_ratio),
        "compiled_cnot_improvement": (
            baseline.cnot_upper / candidate.cnot_upper
        ),
        "twofold_local_target_met": local_ratio <= Fraction(1, 2),
        "twofold_compiled_cnot_target_met": (
            candidate.cnot_upper * 2 <= baseline.cnot_upper
        ),
    }


def _verify_v2(
    data: dict[str, object],
    *,
    deep: bool,
) -> dict[str, object]:
    benchmark = data["benchmark"]
    if benchmark["normalization"] != EXPECTED_NORMALIZATION:
        raise ValueError("Hamiltonian normalization mismatch")
    length = int(benchmark["length"])
    if length % 2:
        raise ValueError("four-matching benchmark requires even length")
    n_sites = length * length
    time = _fraction(benchmark["time"])
    tolerance = _fraction(benchmark["tolerance"])
    if time != 1:
        raise ValueError("schema v2 currently pins T=1")

    proof = data["proof"]
    if proof["formula"] != "five_copy_suzuki_fourth_order":
        raise ValueError("unexpected candidate formula")
    if int(proof["stage_count"]) != 31 or int(proof["center"]) != 17:
        raise ValueError("candidate formula structure mismatch")
    decimal_digits = int(proof["coefficient_interval_decimal_digits"])
    root = cube_root_four_interval(decimal_digits)
    claimed_root = proof["cube_root_four_interval"]
    if (
        root.lower != _fraction(claimed_root["lower"])
        or root.upper != _fraction(claimed_root["upper"])
        or not (root.lower**3 <= 4 <= root.upper**3)
    ):
        raise ValueError("cube-root enclosure is invalid")

    baseline_density = _fraction(proof["baseline_site_density"])
    if baseline_density <= 0 or baseline_density > Fraction(21, 8):
        raise ValueError("strengthened baseline density is outside the pinned range")
    candidate_density = _fraction(proof["candidate_site_density_upper"])
    if candidate_density <= 0:
        raise ValueError("candidate density must be positive")

    deep_verified = False
    if deep:
        from .baseline import strang_commutator_operators
        from .clusters import phase_partitioned_collatz_certificate
        from .rigorous_fourth import fourth_order_rational_pair_certificate

        reference_length = int(proof["baseline_reference_length"])
        if reference_length != 6:
            raise ValueError("deep baseline currently pins L=6")
        reference_lattice = SquareLattice(reference_length)
        baseline_total = Fraction()
        component_bounds: list[list[list[int]]] = []
        for block in strang_commutator_operators(
            four_matching_fragments(reference_lattice)
        ):
            repeated_fragment = phase_partitioned_collatz_certificate(
                block.repeated_fragment,
                reference_lattice,
                iterations=35,
            ).global_bound
            repeated_tail = phase_partitioned_collatz_certificate(
                block.repeated_tail,
                reference_lattice,
                iterations=35,
            ).global_bound
            baseline_total += repeated_fragment / 24 + repeated_tail / 12
            component_bounds.append(
                [
                    [repeated_fragment.numerator, repeated_fragment.denominator],
                    [repeated_tail.numerator, repeated_tail.denominator],
                ]
            )
        regenerated_baseline_density = (
            baseline_total / reference_lattice.n_sites
        )
        if regenerated_baseline_density != baseline_density:
            raise ValueError("deep regenerated baseline differs from certificate")
        if component_bounds != proof["baseline_component_bounds"]:
            raise ValueError("deep baseline component bounds differ")

        regenerated = fourth_order_rational_pair_certificate(
            center=17,
            decimal_digits=decimal_digits,
        )
        if regenerated.site_density_upper != candidate_density:
            raise ValueError("deep regenerated density differs from certificate")
        statistics = proof["statistics"]
        if (
            regenerated.theorem_terms != int(statistics["theorem_terms"])
            or regenerated.paired_terms != int(statistics["paired_terms"])
            or regenerated.singleton_terms != int(statistics["singleton_terms"])
        ):
            raise ValueError("deep proof statistics differ from certificate")
        deep_verified = True

    baseline_steps = required_steps(
        baseline_density * n_sites,
        tolerance,
        2,
        time,
    )
    candidate_steps = required_steps(
        candidate_density * n_sites,
        tolerance,
        4,
        time,
    )
    baseline = four_matching_resources(n_sites, baseline_steps)
    candidate = fourth_order_four_matching_resources(
        n_sites,
        candidate_steps,
        stage_count=31,
    )
    claimed = data["claimed_resources"]
    recomputed = {
        "baseline_steps": baseline.steps,
        "candidate_steps": candidate.steps,
        "baseline_group_exponentials": baseline.group_exponentials,
        "candidate_group_exponentials": candidate.group_exponentials,
        "baseline_bond_propagators": baseline.local_propagators,
        "candidate_bond_propagators": candidate.local_propagators,
        "baseline_cnot_upper": baseline.cnot_upper,
        "candidate_cnot_upper": candidate.cnot_upper,
    }
    if claimed != recomputed:
        raise ValueError("claimed resources do not match recomputation")

    ratio = Fraction(candidate.cnot_upper, baseline.cnot_upper)
    twofold = candidate.cnot_upper * 2 <= baseline.cnot_upper
    if bool(data["claims"]["compiled_cnot_improvement_exceeds_two"]) != twofold:
        raise ValueError("twofold claim is inconsistent")
    return {
        "valid": True,
        "verification_level": "deep" if deep_verified else "fast",
        "deep_proof_regenerated": deep_verified,
        "baseline_site_density": str(baseline_density),
        "candidate_site_density_upper": str(candidate_density),
        "baseline_steps": baseline.steps,
        "candidate_steps": candidate.steps,
        "compiled_cnot_ratio": str(ratio),
        "compiled_cnot_improvement": float(1 / ratio),
        "twofold_compiled_cnot_target_met": twofold,
    }


def _verify_v3(
    data: dict[str, object],
    *,
    deep: bool,
) -> dict[str, object]:
    benchmark = data["benchmark"]
    if benchmark["normalization"] != EXPECTED_NORMALIZATION:
        raise ValueError("Hamiltonian normalization mismatch")
    length = int(benchmark["length"])
    if length % 2:
        raise ValueError("four-matching benchmark requires even length")
    n_sites = length * length
    if _fraction(benchmark["time"]) != 1:
        raise ValueError("schema v3 pins T=1")
    tolerance = _fraction(benchmark["tolerance"])

    published = data["published_baseline"]
    if (
        published["formula"] != "five_copy_suzuki_fourth_order"
        or int(published["formula_order"]) != 4
        or int(published["stage_count"]) != 31
        or int(published["theorem_center"]) != 20
    ):
        raise ValueError("published baseline structure mismatch")
    published_density = _fraction(published["site_density_upper"])
    published_steps = required_steps(
        published_density * n_sites,
        tolerance,
        4,
    )
    if published_steps != int(published["steps"]):
        raise ValueError("published baseline step count mismatch")
    published_groups = 30 * published_steps + 1
    if published_groups != int(published["group_exponentials"]):
        raise ValueError("published baseline group count mismatch")

    candidate = data["candidate"]
    if (
        candidate["formula"] != "five_copy_suzuki_fourth_order"
        or candidate["proof_method"]
        != "local_log_E5_plus_E7_majorant_plus_exact_generator_tail"
    ):
        raise ValueError("candidate structure mismatch")
    candidate_steps = int(candidate["steps"])
    candidate_error = _fraction(candidate["global_error_upper"])
    previous_error = _fraction(candidate["previous_step_error_upper"])
    if candidate_error > tolerance:
        raise ValueError("candidate does not meet the requested tolerance")
    if previous_error <= tolerance:
        raise ValueError("candidate step count is not minimal for this certificate")
    candidate_groups = 30 * candidate_steps + 1
    if candidate_groups != int(candidate["group_exponentials"]):
        raise ValueError("candidate group count mismatch")
    contributions = candidate["contributions"]
    contribution_sum = sum(
        (_fraction(contributions[key]) for key in ("degree4", "degree5", "degree6", "degree7", "tail")),
        Fraction(),
    )
    if contribution_sum != candidate_error:
        raise ValueError("candidate contribution sum mismatch")

    claimed = data["claimed_resources"]
    baseline_bonds = published_groups * n_sites // 2
    candidate_bonds = candidate_groups * n_sites // 2
    recomputed = {
        "published_steps": published_steps,
        "candidate_steps": candidate_steps,
        "published_group_exponentials": published_groups,
        "candidate_group_exponentials": candidate_groups,
        "published_bond_propagators": baseline_bonds,
        "candidate_bond_propagators": candidate_bonds,
        "published_cnot_upper": 3 * baseline_bonds,
        "candidate_cnot_upper": 3 * candidate_bonds,
    }
    if claimed != recomputed:
        raise ValueError("schema v3 resource summary mismatch")

    deep_verified = False
    if deep:
        from .refined_error import (
            build_refined_fourth_order_constants,
            evaluate_refined_fourth_order_bound,
        )
        from .rigorous_fourth import (
            fourth_order_published_triangle_certificate,
        )

        published_rebuilt = fourth_order_published_triangle_certificate(
            center=20,
            decimal_digits=int(published["coefficient_interval_decimal_digits"]),
        )
        if published_rebuilt.site_density_upper != published_density:
            raise ValueError("deep published baseline regeneration mismatch")

        constants = build_refined_fourth_order_constants(
            decimal_digits=int(candidate["coefficient_interval_decimal_digits"]),
            quantization_digits=int(candidate["e5_quantization_digits"]),
        )
        if constants.e5_site_l1 != _fraction(candidate["e5_site_l1_upper"]):
            raise ValueError("deep E5 regeneration mismatch")
        if constants.e7_site_majorant != _fraction(candidate["e7_site_majorant"]):
            raise ValueError("deep E7 regeneration mismatch")
        rebuilt = evaluate_refined_fourth_order_bound(
            constants,
            n_sites,
            candidate_steps,
        )
        rebuilt_previous = evaluate_refined_fourth_order_bound(
            constants,
            n_sites,
            candidate_steps - 1,
        )
        if rebuilt.global_error_bound != candidate_error:
            raise ValueError("deep candidate bound regeneration mismatch")
        if rebuilt_previous.global_error_bound != previous_error:
            raise ValueError("deep candidate minimality regeneration mismatch")
        deep_verified = True

    ratio = Fraction(published_groups, candidate_groups)
    claimed_ratio = _fraction(data["claims"]["exact_improvement_ratio"])
    if ratio != claimed_ratio:
        raise ValueError("claimed improvement ratio mismatch")
    if bool(data["claims"]["global_twofold_target_met"]) != (ratio >= 2):
        raise ValueError("global twofold claim mismatch")
    return {
        "valid": True,
        "verification_level": "deep" if deep_verified else "fast",
        "deep_proof_regenerated": deep_verified,
        "published_steps": published_steps,
        "candidate_steps": candidate_steps,
        "published_group_exponentials": published_groups,
        "candidate_group_exponentials": candidate_groups,
        "candidate_error_upper": str(candidate_error),
        "previous_step_error_upper": str(previous_error),
        "exact_improvement_ratio": str(ratio),
        "improvement": float(ratio),
        "global_twofold_target_met": ratio >= 2,
    }


def verify_certificate(
    path: str | Path,
    *,
    deep: bool = False,
) -> dict[str, object]:
    data = json.loads(Path(path).read_text())
    schema = data.get("schema_version")
    if schema == 1:
        if deep:
            raise ValueError("deep verification is available only for schema v2")
        return _verify_v1(data)
    if schema == 2:
        return _verify_v2(data, deep=deep)
    if schema == 3:
        return _verify_v3(data, deep=deep)
    raise ValueError("unsupported certificate schema")
