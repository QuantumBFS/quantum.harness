"""Hash-bound CT-HYB calibration plans, execution, and statistical gates."""

from __future__ import annotations

import argparse
import copy
import math
import os
from pathlib import Path
import shlex
from statistics import mean, stdev
import time
from typing import Sequence
import uuid

import numpy as np
from scipy.stats import chi2, t

from artifacts import (
    atomic_write_bytes,
    canonical_json,
    sha256_bytes,
    sha256_file,
    strict_json_load,
)
import make_input
from hybridization import install_g0
import run_chain
from source_manifest import build_source_manifest


SOLUTION_DIR = Path(__file__).resolve().parent


OBSERVABLES = (
    "n_d",
    "double_occupancy",
    "G_up_4",
    "G_up_8",
    "G_up_12",
    "G_down_4",
    "G_down_8",
    "G_down_12",
)
GREEN_OBSERVABLES = OBSERVABLES[2:]
PRODUCTION_SEEDS = {810001, 810002, 810003, 810004}
_WARMUPS = (25000, 50000)
_CYCLES = (10, 25, 50, 100)
_WARMUP_REPLICAS = 16
_BATCH_GROUPS = 8
_ESTIMATOR_REPLICAS = 8


def _artifact(payload: dict[str, object]) -> dict[str, object]:
    return {"payload": payload, "sha256": sha256_bytes(canonical_json(payload))}


def _bound(name: str) -> float:
    return 5e-4 if name in {"n_d", "double_occupancy"} else 1e-3


def _inventory(cells, expected, key, kind):
    if len(cells) != len(expected):
        raise ValueError(f"{kind} cell count mismatch")
    identities = {cell.get("input_identity") for cell in cells}
    seeds = [cell.get("seed") for cell in cells]
    if len(identities) != 1 or not all(isinstance(seed, int) for seed in seeds):
        raise ValueError(f"{kind} identity or seed is invalid")
    if len(seeds) != len(set(seeds)) or set(seeds) & PRODUCTION_SEEDS:
        raise ValueError(f"{kind} seeds are reused")
    if {(cell.get(key), cell.get("replica")) for cell in cells} != expected:
        raise ValueError(f"{kind} inventory mismatch")


def _values(cell):
    values = cell.get("values")
    if not isinstance(values, dict) or set(values) != set(OBSERVABLES):
        raise ValueError("observable inventory mismatch")
    result = {name: float(values[name]) for name in OBSERVABLES}
    if not all(math.isfinite(value) for value in result.values()):
        raise ValueError("observables must be finite")
    return result


def analyze_warmup(cells: Sequence[dict[str, object]]) -> dict[str, object]:
    expected = {
        (level, replica)
        for level in _WARMUPS
        for replica in range(_WARMUP_REPLICAS)
    }
    _inventory(cells, expected, "warmup_cycles", "warmup")
    if any(
        cell.get("cell_kind") != "warmup" or cell.get("estimator") != "legendre"
        for cell in cells
    ):
        raise ValueError("warmup estimators must be direct independent means")
    result = {}
    for name in OBSERVABLES:
        groups = {
            level: [_values(cell)[name] for cell in cells if cell["warmup_cycles"] == level]
            for level in _WARMUPS
        }
        mean25, mean50 = mean(groups[25000]), mean(groups[50000])
        se25 = stdev(groups[25000]) / math.sqrt(_WARMUP_REPLICAS)
        se50 = stdev(groups[50000]) / math.sqrt(_WARMUP_REPLICAS)
        a, b = se25**2, se50**2
        delta, se_delta = mean50 - mean25, math.sqrt(a + b)
        denominator = a**2 / 15 + b**2 / 15
        if denominator == 0:
            degrees, quantile, interval = "infinite", 0.0, [delta, delta]
        else:
            degrees = (a + b) ** 2 / denominator
            quantile = float(t.ppf(1 - 0.01 / 16, degrees))
            interval = [delta - quantile * se_delta, delta + quantile * se_delta]
        bound = _bound(name)
        result[name] = {
            "mean_25000": mean25,
            "mean_50000": mean50,
            "delta": delta,
            "se_25000": se25,
            "se_50000": se50,
            "se_delta": se_delta,
            "degrees_of_freedom": degrees,
            "quantile": quantile,
            "interval": interval,
            "equivalence_bound": bound,
            "passed": interval[0] >= -bound and interval[1] <= bound,
        }
    return {
        "multiplicity": 8,
        "family_wise_confidence": 0.99,
        "observables": result,
        "passed": all(item["passed"] for item in result.values()),
    }


def select_cycle_length(cells: Sequence[dict[str, object]]) -> dict[str, object]:
    expected = {(length, replica) for length in _CYCLES for replica in range(4)}
    _inventory(cells, expected, "cycle_length", "cycle")
    if any(cell.get("cell_kind") != "cycle" for cell in cells):
        raise ValueError("cycle cell kind mismatch")
    passing = []
    for length in _CYCLES:
        group = [cell for cell in cells if cell["cycle_length"] == length]
        if all(
            cell.get("auto_corr_time_converged") is True
            and float(cell["auto_corr_time"]) <= 5.0
            for cell in group
        ):
            passing.append(length)
    selected = min(passing) if passing else None
    locked_group = [cell for cell in cells if cell["cycle_length"] == 50]
    locked_passed = all(
        cell.get("auto_corr_time_converged") is True
        and float(cell["auto_corr_time"]) <= 5.0
        for cell in locked_group
    )
    return {
        "candidate_lengths": list(_CYCLES),
        "empirical_minimum_cycle_length": selected,
        "locked_production_cycle_length": 50,
        "locked_production_cycle_passed": locked_passed,
        "maximum_allowed_autocorrelation": 5.0,
        "passed": locked_passed,
    }


def analyze_batch_means(cells: Sequence[dict[str, object]]) -> dict[str, object]:
    if len(cells) != 64:
        raise ValueError("increment cell count mismatch")
    identities = {cell.get("input_identity") for cell in cells}
    seeds = [cell.get("seed") for cell in cells]
    expected = {
        (group, increment) for group in range(_BATCH_GROUPS) for increment in range(8)
    }
    actual = {(cell.get("group"), cell.get("increment")) for cell in cells}
    if (
        len(identities) != 1
        or len(seeds) != len(set(seeds))
        or set(seeds) & PRODUCTION_SEEDS
        or actual != expected
        or any(
            cell.get("cell_kind") != "increment"
            or cell.get("estimator") != "legendre_direct_increment"
            or cell.get("warmup_cycles") != 50000
            or cell.get("measurement_cycles") != 62500
            for cell in cells
        )
    ):
        raise ValueError("increment identity, seed, estimator, or inventory is invalid")
    ordered = {
        group: sorted(
            (cell for cell in cells if cell["group"] == group),
            key=lambda cell: cell["increment"],
        )
        for group in range(_BATCH_GROUPS)
    }
    result = {}
    drift_quantile = float(t.ppf(1 - 0.01 / 16, 7))
    variance_quantile = float(chi2.ppf(0.01, 56))
    for name in OBSERVABLES:
        groups = [
            [_values(cell)[name] for cell in ordered[group]]
            for group in range(_BATCH_GROUPS)
        ]
        differences = [mean(group[4:]) - mean(group[:4]) for group in groups]
        drift = mean(differences)
        drift_se = stdev(differences) / math.sqrt(_BATCH_GROUPS)
        interval = [
            drift - drift_quantile * drift_se,
            drift + drift_quantile * drift_se,
        ]
        variances = [stdev(group) ** 2 for group in groups]
        pooled = sum(7 * value for value in variances) / 56
        upper = math.sqrt(56 * pooled / (variance_quantile * 32))
        bound = _bound(name)
        result[name] = {
            "batch_means": groups,
            "paired_differences": differences,
            "mean_drift": drift,
            "drift_standard_error": drift_se,
            "drift_degrees_of_freedom": 7,
            "drift_quantile": drift_quantile,
            "drift_interval": interval,
            "pooled_within_group_variance": pooled,
            "variance_degrees_of_freedom": 56,
            "production_batch_equivalents": 32,
            "chi_square_lower_quantile": variance_quantile,
            "projected_error_upper_99": upper,
            "equivalence_bound": bound,
            "drift_passed": interval[0] >= -bound and interval[1] <= bound,
            "error_passed": upper <= bound,
        }
        result[name]["passed"] = result[name]["drift_passed"] and result[name]["error_passed"]
    return {
        "multiplicity": 8,
        "family_wise_confidence": 0.99,
        "observables": result,
        "passed": all(item["passed"] for item in result.values()),
    }


def legendre_reported_values(
    coefficients: Sequence[complex],
    *,
    beta: float,
    tau: Sequence[float],
    truncation: int,
) -> list[float]:
    data = np.asarray(coefficients, dtype=np.complex128)
    if (
        isinstance(truncation, bool)
        or truncation <= 0
        or truncation > len(data)
        or not math.isfinite(float(beta))
        or beta <= 0
    ):
        raise ValueError("invalid Legendre reconstruction controls")
    indices = np.arange(truncation, dtype=np.float64)
    weighted = np.sqrt(2 * indices + 1) * data[:truncation] / beta
    result = []
    for point in tau:
        if not math.isfinite(float(point)) or point < 0 or point > beta:
            raise ValueError("reported tau lies outside [0,beta]")
        value = np.polynomial.legendre.legval(2 * float(point) / beta - 1, weighted)
        if abs(value.imag) > 1e-10:
            raise ValueError("Legendre reconstruction is not real within tolerance")
        result.append(float(value.real))
    return result


MEASURED_N_L = 100
RECONSTRUCTION_CUTOFFS = [20, 40, 60, 80, 100]
PRODUCTION_CANDIDATE_CUTOFF = 20
TRUNCATION_BIAS_BOUND = 2.5e-4


def build_estimator_plan(
    bindings: dict[str, object],
    *,
    measurement_cycles: int,
) -> dict[str, object]:
    required = {
        "model",
        "meshes",
        "formulas",
        "source_manifest",
        "source_manifest_sha256",
        "conda_lock_sha256",
        "environment_yml_sha256",
        "model_json_sha256",
    }
    if set(bindings) != required:
        raise ValueError("estimator bindings are incomplete")
    if (
        isinstance(measurement_cycles, bool)
        or not isinstance(measurement_cycles, int)
        or measurement_cycles <= 0
    ):
        raise ValueError("qualification measurement cycles must be positive")
    identity = sha256_bytes(
        canonical_json(
            {
                "bindings": bindings,
                "profile": "legendre_estimator_qualification",
                "measured_n_l": MEASURED_N_L,
                "cutoffs": RECONSTRUCTION_CUTOFFS,
                "candidate_cutoff": PRODUCTION_CANDIDATE_CUTOFF,
                "measurement_cycles": measurement_cycles,
            }
        )
    )
    cells = [
        _cell(
            replica,
            "estimator_qualification",
            828000 + replica,
            identity,
            {
                "warmup_cycles": 50000,
                "measurement_cycles": measurement_cycles,
                "cycle_length": 50,
                "replica": replica,
                "estimator": "legendre",
                "measured_n_l": MEASURED_N_L,
                "cutoffs": list(RECONSTRUCTION_CUTOFFS),
                "candidate_cutoff": PRODUCTION_CANDIDATE_CUTOFF,
            },
        )
        for replica in range(_ESTIMATOR_REPLICAS)
    ]
    return _artifact(
        {
            "artifact_type": "cthyb_estimator_plan",
            "schema_version": 2,
            "bindings": copy.deepcopy(bindings),
            "input_identity": identity,
            "cell_count": _ESTIMATOR_REPLICAS,
            "experiment_kind": "qualification",
            "measurement_cycles": measurement_cycles,
            "measured_n_l": MEASURED_N_L,
            "cutoffs": list(RECONSTRUCTION_CUTOFFS),
            "candidate_cutoff": PRODUCTION_CANDIDATE_CUTOFF,
            "cells": cells,
        }
    )


def validate_estimator_plan(plan: object) -> None:
    if not isinstance(plan, dict) or set(plan) != {"payload", "sha256"}:
        raise ValueError("estimator plan artifact is malformed")
    payload = plan["payload"]
    if (
        not isinstance(payload, dict)
        or plan["sha256"] != sha256_bytes(canonical_json(payload))
        or payload.get("artifact_type") != "cthyb_estimator_plan"
    ):
        raise ValueError("estimator plan hash or type mismatch")
    expected = build_estimator_plan(
        payload.get("bindings"),
        measurement_cycles=payload.get("measurement_cycles"),
    )
    if canonical_json(plan) != canonical_json(expected):
        raise ValueError("estimator plan differs from canonical plan")


def _analyze_cutoff_comparisons(
    cell_results: Sequence[dict[str, object]],
    plan: dict[str, object],
) -> dict[str, object]:
    if len(cell_results) != _ESTIMATOR_REPLICAS:
        raise ValueError("estimator qualification requires exactly eight results")
    cells = []
    for result in cell_results:
        if (
            not isinstance(result, dict)
            or result.get("sha256") != sha256_bytes(canonical_json(result.get("payload")))
        ):
            raise ValueError("estimator result hash mismatch")
        cells.append(result["payload"])
    expected_inventory = set(range(_ESTIMATOR_REPLICAS))
    if (
        {cell.get("replica") for cell in cells} != expected_inventory
        or len({cell.get("seed") for cell in cells}) != _ESTIMATOR_REPLICAS
        or {cell.get("input_identity") for cell in cells}
        != {plan["payload"]["input_identity"]}
        or {cell.get("measured_n_l") for cell in cells}
        != {plan["payload"]["measured_n_l"]}
        or {cell.get("measurement_cycles") for cell in cells}
        != {plan["payload"]["measurement_cycles"]}
        or {tuple(cell.get("cutoffs", [])) for cell in cells}
        != {tuple(plan["payload"]["cutoffs"])}
    ):
        raise ValueError("estimator result inventory mismatch")
    candidate = str(plan["payload"]["candidate_cutoff"])
    larger = [
        str(cutoff)
        for cutoff in plan["payload"]["cutoffs"]
        if cutoff > plan["payload"]["candidate_cutoff"]
    ]
    comparison_count = len(GREEN_OBSERVABLES) * len(larger)
    quantile = float(t.ppf(1 - 0.01 / (2 * comparison_count), 7))
    comparisons = {}
    for name in GREEN_OBSERVABLES:
        comparisons[name] = {}
        for cutoff in larger:
            differences = [
                float(cell["truncated_values"][candidate][name])
                - float(cell["truncated_values"][cutoff][name])
                for cell in cells
            ]
            center = mean(differences)
            standard_error = stdev(differences) / math.sqrt(_ESTIMATOR_REPLICAS)
            interval = [
                center - quantile * standard_error,
                center + quantile * standard_error,
            ]
            comparisons[name][cutoff] = {
                "differences": differences,
                "mean_difference": center,
                "standard_error": standard_error,
                "degrees_of_freedom": 7,
                "quantile": quantile,
                "interval": interval,
                "equivalence_bound": TRUNCATION_BIAS_BOUND,
                "passed": (
                    interval[0] >= -TRUNCATION_BIAS_BOUND
                    and interval[1] <= TRUNCATION_BIAS_BOUND
                ),
            }
    passed = all(
        gate["passed"]
        for by_cutoff in comparisons.values()
        for gate in by_cutoff.values()
    )
    return {
        "family_wise_confidence": 0.99,
        "comparison_count": comparison_count,
        "candidate_cutoff": plan["payload"]["candidate_cutoff"],
        "larger_cutoffs": [int(value) for value in larger],
        "comparisons": comparisons,
        "passed": passed,
    }


def analyze_estimator_qualification(
    cell_results: Sequence[dict[str, object]],
    plan: dict[str, object],
) -> dict[str, object]:
    validate_estimator_plan(plan)
    analysis = _analyze_cutoff_comparisons(cell_results, plan)
    passed = analysis["passed"]
    payload = {
        "artifact_type": "cthyb_estimator_qualification",
        "schema_version": 2,
        "status": "accepted" if passed else "failed",
        "measured_n_l": plan["payload"]["measured_n_l"],
        "cutoffs": plan["payload"]["cutoffs"],
        "candidate_cutoff": plan["payload"]["candidate_cutoff"],
        "production_reconstruction_cutoff": (
            plan["payload"]["candidate_cutoff"] if passed else None
        ),
        "plan": plan,
        "cell_results": list(cell_results),
        "analysis": analysis,
    }
    return _artifact(payload)


def _validate_scaling_reference(reference: object) -> dict[str, float]:
    if (
        not isinstance(reference, dict)
        or set(reference) != {"payload", "sha256"}
        or reference["sha256"]
        != sha256_bytes(canonical_json(reference["payload"]))
    ):
        raise ValueError("scaling reference is hash-invalid")
    payload = reference["payload"]
    if (
        payload.get("artifact_type") != "cthyb_estimator_qualification"
        or payload.get("qualified_n_l") != 100
        or payload.get("truncations") != [60, 80, 100]
        or len(payload.get("cell_results", [])) != 8
        or any(
            result.get("sha256")
            != sha256_bytes(canonical_json(result.get("payload")))
            for result in payload["cell_results"]
        )
    ):
        raise ValueError("scaling reference is not the reviewed 1M artifact")
    observables = payload.get("analysis", {}).get("observables")
    if not isinstance(observables, dict) or set(observables) != set(GREEN_OBSERVABLES):
        raise ValueError("scaling reference observable inventory mismatch")
    standard_errors = {
        name: float(observables[name]["standard_error"])
        for name in GREEN_OBSERVABLES
    }
    if not all(math.isfinite(value) and value > 0 for value in standard_errors.values()):
        raise ValueError("scaling reference standard errors are invalid")
    return standard_errors


def build_scaling_plan(
    bindings: dict[str, object],
    reference: dict[str, object],
) -> dict[str, object]:
    reference_standard_errors = _validate_scaling_reference(reference)
    base = build_estimator_plan(bindings, measurement_cycles=4_000_000)
    payload = copy.deepcopy(base["payload"])
    identity = sha256_bytes(
        canonical_json(
            {
                "bindings": bindings,
                "profile": "legendre_estimator_scaling",
                "measured_n_l": MEASURED_N_L,
                "cutoffs": RECONSTRUCTION_CUTOFFS,
                "candidate_cutoff": PRODUCTION_CANDIDATE_CUTOFF,
                "measurement_cycles": 4_000_000,
                "reference_sha256": reference["sha256"],
            }
        )
    )
    payload.update(
        {
            "artifact_type": "cthyb_estimator_scaling_plan",
            "experiment_kind": "scaling",
            "input_identity": identity,
            "reference": copy.deepcopy(reference),
            "reference_sha256": reference["sha256"],
            "reference_high_mode_standard_errors": reference_standard_errors,
        }
    )
    payload["cells"] = [
        _cell(
            replica,
            "estimator_scaling",
            829000 + replica,
            identity,
            {
                "warmup_cycles": 50000,
                "measurement_cycles": 4_000_000,
                "cycle_length": 50,
                "replica": replica,
                "estimator": "legendre",
                "measured_n_l": MEASURED_N_L,
                "cutoffs": list(RECONSTRUCTION_CUTOFFS),
                "candidate_cutoff": PRODUCTION_CANDIDATE_CUTOFF,
            },
        )
        for replica in range(_ESTIMATOR_REPLICAS)
    ]
    return _artifact(payload)


def validate_scaling_plan(plan: object) -> None:
    if not isinstance(plan, dict) or set(plan) != {"payload", "sha256"}:
        raise ValueError("scaling plan artifact is malformed")
    payload = plan["payload"]
    if (
        not isinstance(payload, dict)
        or plan["sha256"] != sha256_bytes(canonical_json(payload))
        or payload.get("artifact_type") != "cthyb_estimator_scaling_plan"
    ):
        raise ValueError("scaling plan hash or type mismatch")
    expected = build_scaling_plan(payload.get("bindings"), payload.get("reference"))
    if canonical_json(plan) != canonical_json(expected):
        raise ValueError("scaling plan differs from canonical plan")


def _power_from_comparisons(
    analysis: dict[str, object],
    measurement_cycles: int,
) -> dict[str, object]:
    variance_only = []
    observed_margin = []
    limiting = None
    largest = -1
    for name, by_cutoff in analysis["comparisons"].items():
        for cutoff, gate in by_cutoff.items():
            half_width = gate["quantile"] * gate["standard_error"]
            required = math.ceil(
                measurement_cycles
                * (half_width / TRUNCATION_BIAS_BOUND) ** 2
            )
            variance_only.append(max(1, required))
            margin = TRUNCATION_BIAS_BOUND - abs(gate["mean_difference"])
            if margin <= 0:
                observed_margin.append(None)
                candidate = math.inf
            else:
                candidate = max(
                    1,
                    math.ceil(measurement_cycles * (half_width / margin) ** 2),
                )
                observed_margin.append(candidate)
            if candidate > largest:
                largest = candidate
                limiting = {"observable": name, "larger_cutoff": int(cutoff)}
    finite_margin = (
        None if any(value is None for value in observed_margin) else max(observed_margin)
    )
    return {
        "fixed_independent_seeds": _ESTIMATOR_REPLICAS,
        "truncation_bias_bound": TRUNCATION_BIAS_BOUND,
        "variance_only_measurement_cycles_per_seed": max(variance_only),
        "required_measurement_cycles_per_seed": finite_margin,
        "required_total_measurement_cycles": (
            None if finite_margin is None else _ESTIMATOR_REPLICAS * finite_margin
        ),
        "limiting_comparison": limiting,
    }


def analyze_estimator_scaling(
    cell_results: Sequence[dict[str, object]],
    plan: dict[str, object],
) -> dict[str, object]:
    validate_scaling_plan(plan)
    analysis = _analyze_cutoff_comparisons(cell_results, plan)
    high_mode = {}
    for name in GREEN_OBSERVABLES:
        differences = [
            float(result["payload"]["truncated_values"]["80"][name])
            - float(result["payload"]["truncated_values"]["100"][name])
            for result in cell_results
        ]
        high_mode[name] = {
            "standard_error": stdev(differences) / math.sqrt(_ESTIMATOR_REPLICAS),
            "reference_standard_error": plan["payload"][
                "reference_high_mode_standard_errors"
            ][name],
        }
        high_mode[name]["ratio"] = (
            high_mode[name]["standard_error"]
            / high_mode[name]["reference_standard_error"]
        )
    ratios = [value["ratio"] for value in high_mode.values()]
    analysis["high_mode_scaling"] = {
        "observables": high_mode,
        "mean_ratio": mean(ratios),
        "approximately_inverse_sqrt_cycles": all(
            0.35 <= ratio <= 0.65 for ratio in ratios
        ),
    }
    analysis["power"] = _power_from_comparisons(
        analysis, plan["payload"]["measurement_cycles"]
    )
    payload = {
        "artifact_type": "cthyb_estimator_scaling",
        "schema_version": 2,
        "status": "diagnostic",
        "measured_n_l": plan["payload"]["measured_n_l"],
        "cutoffs": plan["payload"]["cutoffs"],
        "candidate_cutoff": plan["payload"]["candidate_cutoff"],
        "production_reconstruction_cutoff": None,
        "reference_sha256": plan["payload"]["reference_sha256"],
        "plan": plan,
        "cell_results": list(cell_results),
        "analysis": analysis,
    }
    return _artifact(payload)


def _cell(index, kind, seed, identity, controls):
    return _artifact(
        {
            "artifact_type": "cthyb_calibration_cell_input",
            "schema_version": 2,
            "cell_index": index,
            "cell_kind": kind,
            "seed": seed,
            "input_identity": identity,
            **controls,
        }
    )


def _validate_qualification(
    qualification: object,
    bindings: dict[str, object],
) -> dict[str, object]:
    if (
        not isinstance(qualification, dict)
        or set(qualification) != {"payload", "sha256"}
        or qualification["sha256"]
        != sha256_bytes(canonical_json(qualification["payload"]))
    ):
        raise ValueError("estimator qualification artifact is hash-invalid")
    payload = qualification["payload"]
    if (
        payload.get("artifact_type") != "cthyb_estimator_qualification"
        or payload.get("status") != "accepted"
        or payload.get("measured_n_l") != MEASURED_N_L
        or payload.get("cutoffs") != RECONSTRUCTION_CUTOFFS
        or payload.get("candidate_cutoff") != PRODUCTION_CANDIDATE_CUTOFF
        or payload.get("production_reconstruction_cutoff")
        != PRODUCTION_CANDIDATE_CUTOFF
        or payload.get("analysis", {}).get("passed") is not True
    ):
        raise ValueError("accepted estimator qualification is required")
    plan = payload.get("plan")
    if (
        not isinstance(plan, dict)
        or plan.get("payload", {}).get("bindings") != bindings
        or not isinstance(payload.get("cell_results"), list)
    ):
        raise ValueError("estimator qualification provenance mismatch")
    expected = analyze_estimator_qualification(payload["cell_results"], plan)
    if canonical_json(qualification) != canonical_json(expected):
        raise ValueError("estimator qualification does not reproduce")
    return payload


def build_calibration_plan(
    bindings: dict[str, object],
    qualification: dict[str, object],
) -> dict[str, object]:
    required = {
        "model",
        "meshes",
        "formulas",
        "source_manifest",
        "source_manifest_sha256",
        "conda_lock_sha256",
        "environment_yml_sha256",
        "model_json_sha256",
    }
    if set(bindings) != required:
        raise ValueError("calibration bindings are incomplete")
    qualification_payload = _validate_qualification(qualification, bindings)
    measured_n_l = qualification_payload["measured_n_l"]
    production_cutoff = qualification_payload["production_reconstruction_cutoff"]
    identity = sha256_bytes(
        canonical_json(
            {
                "bindings": bindings,
                "qualification_sha256": qualification["sha256"],
            }
        )
    )
    cells, index = [], 0
    for level, warmup in enumerate(_WARMUPS):
        for replica in range(_WARMUP_REPLICAS):
            cells.append(
                _cell(
                    index,
                    "warmup",
                    824000 + level * 100 + replica,
                    identity,
                    {
                        "warmup_cycles": warmup,
                        "measurement_cycles": 100000,
                        "cycle_length": 50,
                        "replica": replica,
                        "estimator": "legendre",
                        "n_l": measured_n_l,
                        "truncation": production_cutoff,
                    },
                )
            )
            index += 1
    for level, cycle in enumerate(_CYCLES):
        for replica in range(4):
            cells.append(
                _cell(
                    index,
                    "cycle",
                    825000 + level * 10 + replica,
                    identity,
                    {
                        "warmup_cycles": 50000,
                        "measurement_cycles": 100000,
                        "cycle_length": cycle,
                        "replica": replica,
                        "estimator": "legendre",
                        "n_l": measured_n_l,
                        "truncation": production_cutoff,
                    },
                )
            )
            index += 1
    for group in range(_BATCH_GROUPS):
        for increment in range(8):
            cells.append(
                _cell(
                    index,
                    "increment",
                    826000 + group * 10 + increment,
                    identity,
                    {
                        "warmup_cycles": 50000,
                        "measurement_cycles": 62500,
                        "cycle_length": 50,
                        "group": group,
                        "increment": increment,
                        "estimator": "legendre_direct_increment",
                        "n_l": measured_n_l,
                        "truncation": production_cutoff,
                    },
                )
            )
            index += 1
    return _artifact(
        {
            "artifact_type": "cthyb_calibration_plan",
            "schema_version": 2,
            "bindings": copy.deepcopy(bindings),
            "qualification": copy.deepcopy(qualification),
            "qualification_sha256": qualification["sha256"],
            "input_identity": identity,
            "cell_count": 112,
            "measured_n_l": measured_n_l,
            "production_reconstruction_cutoff": production_cutoff,
            "cells": cells,
        }
    )


def validate_calibration_plan(plan: object) -> None:
    if not isinstance(plan, dict) or set(plan) != {"payload", "sha256"}:
        raise ValueError("calibration plan artifact is malformed")
    payload = plan["payload"]
    if not isinstance(payload, dict) or plan["sha256"] != sha256_bytes(canonical_json(payload)):
        raise ValueError("calibration plan hash mismatch")
    expected = build_calibration_plan(
        payload.get("bindings"),
        payload.get("qualification"),
    )
    if canonical_json(plan) != canonical_json(expected):
        raise ValueError("calibration plan differs from canonical plan")


def validate_calibration(artifact: object, calibration_plan: object) -> None:
    validate_calibration_plan(calibration_plan)
    if not isinstance(artifact, dict) or set(artifact) != {"payload", "sha256"}:
        raise ValueError("calibration artifact is malformed")
    payload = artifact["payload"]
    if artifact["sha256"] != sha256_bytes(canonical_json(payload)):
        raise ValueError("calibration hash mismatch")
    if (
        payload.get("plan") != calibration_plan
        or len(payload.get("cell_results", [])) != 112
    ):
        raise ValueError("calibration plan or result inventory mismatch")
    results = payload["cell_results"]
    if any(
        result.get("sha256") != sha256_bytes(canonical_json(result.get("payload")))
        for result in results
    ):
        raise ValueError("calibration result hash mismatch")
    cells = [result["payload"] for result in results]
    if {cell.get("input_identity") for cell in cells} != {
        calibration_plan["payload"]["input_identity"]
    }:
        raise ValueError("calibration result input identity mismatch")
    expected_analysis = {
        "warmup": analyze_warmup(cells[:32]),
        "cycle": select_cycle_length(cells[32:48]),
        "batch": analyze_batch_means(cells[48:]),
    }
    if canonical_json(payload.get("analysis")) != canonical_json(expected_analysis):
        raise ValueError("calibration analysis does not reproduce cell results")
    bindings = calibration_plan["payload"]["bindings"]
    for key in (
        "model",
        "source_manifest",
        "source_manifest_sha256",
        "conda_lock_sha256",
        "environment_yml_sha256",
        "model_json_sha256",
    ):
        if payload.get(key) != bindings[key]:
            raise ValueError(f"calibration binding mismatch: {key}")
    if payload.get("qualification_sha256") != calibration_plan["payload"][
        "qualification_sha256"
    ]:
        raise ValueError("calibration qualification binding mismatch")
    accepted = all(value["passed"] for value in expected_analysis.values())
    if payload.get("status") != ("accepted" if accepted else "failed"):
        raise ValueError("calibration status disagrees with gates")


def build_calibration_artifact(
    calibration_plan: dict[str, object],
    cell_results: Sequence[dict[str, object]],
) -> dict[str, object]:
    validate_calibration_plan(calibration_plan)
    if len(cell_results) != 112:
        raise ValueError("calibration requires exactly 112 cell results")
    cells = []
    for result in cell_results:
        if (
            not isinstance(result, dict)
            or set(result) != {"payload", "sha256"}
            or result["sha256"] != sha256_bytes(canonical_json(result["payload"]))
        ):
            raise ValueError("calibration cell result hash mismatch")
        cells.append(result["payload"])
    if {cell.get("input_identity") for cell in cells} != {
        calibration_plan["payload"]["input_identity"]
    }:
        raise ValueError("calibration result input identity mismatch")
    analysis = {
        "warmup": analyze_warmup(cells[:32]),
        "cycle": select_cycle_length(cells[32:48]),
        "batch": analyze_batch_means(cells[48:]),
    }
    bindings = calibration_plan["payload"]["bindings"]
    payload = {
        "artifact_type": "cthyb_calibration",
        "schema_version": 2,
        "status": (
            "accepted" if all(value["passed"] for value in analysis.values()) else "failed"
        ),
        "model": bindings["model"],
        "source_manifest": bindings["source_manifest"],
        "source_manifest_sha256": bindings["source_manifest_sha256"],
        "conda_lock_sha256": bindings["conda_lock_sha256"],
        "environment_yml_sha256": bindings["environment_yml_sha256"],
        "model_json_sha256": bindings["model_json_sha256"],
        "qualification_sha256": calibration_plan["payload"][
            "qualification_sha256"
        ],
        "plan": calibration_plan,
        "cell_results": list(cell_results),
        "analysis": analysis,
    }
    artifact = _artifact(payload)
    validate_calibration(artifact, calibration_plan)
    return artifact


def calibration_cluster_commands(
    micromamba: Path, prefix: Path, plan: Path, run_directory: Path
) -> dict[str, str]:
    if not all(path.is_absolute() for path in (micromamba, prefix, plan, run_directory)):
        raise ValueError("cluster paths must be absolute")
    script = Path(__file__).resolve()
    wrapper = script.with_name("cthyb_calibration_slurm_array.sh")
    base = (
        f"{shlex.quote(str(micromamba))} --offline run --prefix "
        f"{shlex.quote(str(prefix))} python {shlex.quote(str(script))}"
    )
    export = (
        "ALL,OMP_NUM_THREADS=1,OPENBLAS_NUM_THREADS=1,MKL_NUM_THREADS=1,"
        f"CTHYB_MICROMAMBA={micromamba},CTHYB_ENV={prefix},"
        f"CTHYB_CAL_PLAN={plan},CTHYB_CAL_RUN={run_directory},"
        f"CTHYB_SOURCE={Path(__file__).resolve().parent}"
    )
    return {
        "validate": f"{base} validate-plan --plan {shlex.quote(str(plan))}",
        "array": (
            "sbatch --array=0-111 --ntasks=1 --cpus-per-task=1 --mem=4G "
            f"--time=04:00:00 --export={export} {wrapper}"
        ),
        "analyze": (
            f"{base} analyze --plan {shlex.quote(str(plan))} "
            f"--run-directory {shlex.quote(str(run_directory))}"
        ),
        "validate_existing": (
            f"{base} validate-existing --plan {shlex.quote(str(plan))} "
            f"--run-directory {shlex.quote(str(run_directory))} "
            f"--calibration {shlex.quote(str(run_directory / 'calibration.json'))}"
        ),
    }


def _default_bindings() -> dict[str, object]:
    repository_root = SOLUTION_DIR.parents[4]
    manifest = build_source_manifest(repository_root)
    model, _ = make_input._load_model(SOLUTION_DIR)
    hashes = make_input._provenance_hashes(manifest)
    return {
        "model": model,
        "meshes": {
            "n_iw": make_input.N_IW,
            "n_tau": make_input.N_TAU,
            "reported_tau": [0.0, 4.0, 8.0, 12.0, 16.0],
        },
        "formulas": {
            "delta_iw": "Delta(iw) = i*(Gamma/D)*(w-sign(w)*sqrt(w*w+D*D))"
        },
        "source_manifest": manifest,
        "source_manifest_sha256": hashes["source_manifest_sha256"],
        "conda_lock_sha256": hashes["conda_lock_sha256"],
        "environment_yml_sha256": hashes["environment_yml_sha256"],
        "model_json_sha256": hashes["model_json_sha256"],
    }


def _solver_payload(cell: dict[str, object]) -> dict[str, object]:
    payload = copy.deepcopy(
        run_chain.make_source_bound_test_pilot_input(SOLUTION_DIR)["payload"]
    )
    payload["monte_carlo"].update(
        {
            "warmup_cycles": cell["warmup_cycles"],
            "measurement_cycles": cell["measurement_cycles"],
            "cycle_length": cell["cycle_length"],
            "measure_G_tau": False,
            "measure_G_l": True,
        }
    )
    payload["gates"].update(
        {
            "minimum_average_sign": 0.0,
            "maximum_integrated_autocorrelation_cycles": 1.0e300,
            "minimum_effective_samples_per_chain": 0,
        }
    )
    return payload


def _calibration_solve_parameters(
    payload: dict[str, object],
    seed: int,
) -> dict[str, object]:
    parameters = run_chain._solve_parameters(payload, seed)
    parameters["measure_G_l"] = True
    parameters["measure_G_tau"] = False
    return parameters


def _legendre_coefficients(solver) -> dict[str, np.ndarray]:
    result = {}
    for spin in ("up", "down"):
        data = np.asarray(solver.G_l[spin].data, dtype=np.complex128)
        if data.ndim != 3 or data.shape[1:] != (1, 1):
            raise ValueError(f"unexpected G_l target shape for {spin}: {data.shape}")
        result[spin] = data[:, 0, 0].copy()
    return result


def _serialized_coefficients(
    coefficients: dict[str, np.ndarray],
) -> dict[str, dict[str, list[float]]]:
    return {
        spin: {
            "real": values.real.astype(np.float64).tolist(),
            "imag": values.imag.astype(np.float64).tolist(),
        }
        for spin, values in coefficients.items()
    }


def _result_values(
    solver,
    payload: dict[str, object],
    truncations: Sequence[int],
) -> dict[str, object]:
    up = run_chain._number_operator("up", 0)
    down = run_chain._number_operator("down", 0)
    n_up = float(
        run_chain._trace_rho_op(
            solver.density_matrix, up, solver.h_loc_diagonalization
        )
    )
    n_down = float(
        run_chain._trace_rho_op(
            solver.density_matrix, down, solver.h_loc_diagonalization
        )
    )
    double = float(
        run_chain._trace_rho_op(
            solver.density_matrix,
            up * down,
            solver.h_loc_diagonalization,
        )
    )
    coefficients = _legendre_coefficients(solver)
    tau = payload["meshes"]["reported_tau"][1:-1]
    truncated_values = {}
    for truncation in truncations:
        values = {"n_d": n_up + n_down, "double_occupancy": double}
        for spin in ("up", "down"):
            reconstructed = legendre_reported_values(
                coefficients[spin],
                beta=payload["model"]["beta"],
                tau=tau,
                truncation=truncation,
            )
            for point, value in zip((4, 8, 12), reconstructed, strict=True):
                values[f"G_{spin}_{point}"] = value
        truncated_values[str(truncation)] = values
    return {
        "values": truncated_values[str(truncations[-1])],
        "truncated_values": truncated_values,
        "legendre_coefficients": _serialized_coefficients(coefficients),
        "auto_corr_time_converged": solver.auto_corr_time_converged is True,
    }


def _calibration_raw_state(
    solver,
    input_bytes: bytes,
    input_artifact: dict[str, object],
    cell_index: int,
    seed: int,
    runtime: dict[str, object],
    solve_parameters: dict[str, object],
) -> dict[str, object]:
    payload = input_artifact["payload"]
    split_delta = payload["hybridization"]["delta_iw"]
    delta = np.asarray(split_delta["real"], dtype=np.float64) + 1j * np.asarray(
        split_delta["imag"], dtype=np.float64
    )
    return {
        "input_bytes": np.frombuffer(input_bytes, dtype=np.uint8).copy(),
        "input_sha256": input_artifact["sha256"],
        "input_payload_sha256": sha256_bytes(canonical_json(payload)),
        "cell_index": cell_index,
        "seed": seed,
        "G0_iw": run_chain._green_blocks(solver.G0_iw),
        "Delta_iw": {"up": delta.copy(), "down": delta.copy()},
        "G_l": solver.G_l,
        "density_matrix": solver.density_matrix,
        "h_loc_diagonalization": solver.h_loc_diagonalization,
        "perturbation_order": solver.perturbation_order,
        "average_sign": solver.average_sign,
        "auto_corr_time": solver.auto_corr_time,
        "auto_corr_time_converged": solver.auto_corr_time_converged,
        "solve_parameters": run_chain._normalized_solve_parameters(
            solve_parameters
        ),
        "runtime": runtime,
    }


def _write_calibration_raw(path: Path, state: dict[str, object]) -> None:
    archive_type = run_chain._archive_class()
    with archive_type(str(path), "w") as archive:
        for name, value in state.items():
            archive[name] = value


def _cell_truncations(cell: dict[str, object]) -> list[int]:
    if "cutoffs" in cell:
        truncations = cell["cutoffs"]
    elif "truncations" in cell:
        truncations = cell["truncations"]
    elif "truncation" in cell:
        truncations = [cell["truncation"]]
    else:
        raise ValueError("cell has no Legendre truncation controls")
    if (
        not isinstance(truncations, list)
        or not truncations
        or any(isinstance(value, bool) or not isinstance(value, int) for value in truncations)
    ):
        raise ValueError("cell Legendre truncations are invalid")
    return list(truncations)


def _cell_measured_n_l(cell: dict[str, object]) -> int:
    value = cell.get("measured_n_l", cell.get("n_l"))
    if isinstance(value, bool) or not isinstance(value, int) or value != MEASURED_N_L:
        raise ValueError("cell measured_n_l must equal 100")
    return value


def run_cell(plan: dict[str, object], cell_index: int, run_directory: Path) -> Path:
    plan_type = plan.get("payload", {}).get("artifact_type")
    if plan_type == "cthyb_estimator_plan":
        validate_estimator_plan(plan)
    elif plan_type == "cthyb_estimator_scaling_plan":
        validate_scaling_plan(plan)
    elif plan_type == "cthyb_calibration_plan":
        validate_calibration_plan(plan)
    else:
        raise ValueError("unsupported calibration plan type")
    cell_count = plan["payload"]["cell_count"]
    if isinstance(cell_index, bool) or cell_index not in range(cell_count):
        raise ValueError(f"cell index must be 0 through {cell_count - 1}")
    cell_artifact = plan["payload"]["cells"][cell_index]
    cell = cell_artifact["payload"]
    destination = run_directory / "cells" / f"cell-{cell_index:03d}"
    if destination.exists():
        result = strict_json_load(destination / "result.json")
        if result["payload"]["cell_input_sha256"] != cell_artifact["sha256"]:
            raise ValueError("existing calibration cell input mismatch")
        if result["payload"]["raw_h5_sha256"] != sha256_file(destination / "raw.h5"):
            raise ValueError("existing calibration raw hash mismatch")
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    attempt = destination.parent / f".attempt-cell-{cell_index:03d}-{uuid.uuid4().hex}"
    attempt.mkdir(mode=0o700)
    payload = _solver_payload(cell)
    threads = run_chain._require_runtime_shape()
    solver = run_chain._solver_class()(
        beta=payload["model"]["beta"],
        gf_struct=[("up", 1), ("down", 1)],
        n_iw=payload["hybridization"]["n_iw"],
        n_tau=payload["meshes"]["n_tau"],
        n_l=_cell_measured_n_l(cell),
    )
    install_g0(solver, payload)
    parameters = _calibration_solve_parameters(payload, cell["seed"])
    started_utc = run_chain._utc_now()
    started = time.monotonic()
    solver.solve(**parameters)
    wall = time.monotonic() - started
    runtime = {
        "versions": run_chain._runtime_identity(),
        "threads": threads,
        "resources": run_chain._resource_record(
            started_utc, run_chain._utc_now(), wall
        ),
    }
    input_artifact = _artifact(payload)
    raw_path = attempt / "raw.h5"
    raw_state = _calibration_raw_state(
        solver,
        canonical_json(input_artifact) + b"\n",
        input_artifact,
        cell_index,
        cell["seed"],
        runtime,
        parameters,
    )
    _write_calibration_raw(raw_path, raw_state)
    truncations = _cell_truncations(cell)
    extracted = _result_values(solver, payload, truncations)
    result_payload = {
        **{
            key: value
            for key, value in cell.items()
            if key not in {"artifact_type", "schema_version"}
        },
        "plan_sha256": plan["sha256"],
        "cell_input_sha256": cell_artifact["sha256"],
        "raw_h5_sha256": sha256_file(raw_path),
        **extracted,
        "average_sign": float(solver.average_sign),
        "auto_corr_time": float(solver.auto_corr_time),
    }
    result = _artifact(result_payload)
    atomic_write_bytes(attempt / "result.json", canonical_json(result) + b"\n")
    os.rename(attempt, destination)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    plan_command = commands.add_parser("plan")
    plan_command.add_argument("--output-root", type=Path, required=True)
    plan_command.add_argument(
        "--profile",
        choices=("qualification", "scaling", "calibration"),
        required=True,
    )
    plan_command.add_argument("--measurement-cycles", type=int)
    plan_command.add_argument("--reference", type=Path)
    plan_command.add_argument("--qualification", type=Path)
    validate = commands.add_parser("validate-plan")
    validate.add_argument("--plan", type=Path, required=True)
    cell = commands.add_parser("run-cell")
    cell.add_argument("--plan", type=Path, required=True)
    cell.add_argument("--run-directory", type=Path, required=True)
    cell.add_argument("--cell-index", type=int, required=True)
    analyze = commands.add_parser("analyze")
    analyze.add_argument("--plan", type=Path, required=True)
    analyze.add_argument("--run-directory", type=Path, required=True)
    existing = commands.add_parser("validate-existing")
    existing.add_argument("--plan", type=Path, required=True)
    existing.add_argument("--run-directory", type=Path, required=True)
    existing.add_argument("--calibration", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.command == "plan":
        if arguments.profile == "qualification":
            if (
                arguments.measurement_cycles is None
                or arguments.reference is not None
                or arguments.qualification is not None
            ):
                raise ValueError(
                    "qualification plan requires --measurement-cycles only"
                )
            plan = build_estimator_plan(
                _default_bindings(),
                measurement_cycles=arguments.measurement_cycles,
            )
            prefix = "estimator"
        elif arguments.profile == "scaling":
            if (
                arguments.measurement_cycles is not None
                or arguments.reference is None
                or arguments.qualification is not None
            ):
                raise ValueError("scaling plan requires --reference only")
            plan = build_scaling_plan(
                _default_bindings(), strict_json_load(arguments.reference)
            )
            prefix = "scaling"
        else:
            if (
                arguments.measurement_cycles is not None
                or arguments.reference is not None
                or arguments.qualification is None
            ):
                raise ValueError("calibration plan requires --qualification only")
            qualification = strict_json_load(arguments.qualification)
            plan = build_calibration_plan(_default_bindings(), qualification)
            prefix = "calibration"
        run_id = f"{prefix}-{plan['sha256'][:16]}"
        run_directory = arguments.output_root / "runs" / run_id
        atomic_write_bytes(
            run_directory / "plan.json", canonical_json(plan) + b"\n"
        )
        atomic_write_bytes(
            arguments.output_root / "current.json",
            canonical_json({"relative_path": f"runs/{run_id}"}) + b"\n",
        )
    elif arguments.command == "validate-plan":
        plan = strict_json_load(arguments.plan)
        if plan.get("payload", {}).get("artifact_type") == "cthyb_estimator_plan":
            validate_estimator_plan(plan)
        elif (
            plan.get("payload", {}).get("artifact_type")
            == "cthyb_estimator_scaling_plan"
        ):
            validate_scaling_plan(plan)
        else:
            validate_calibration_plan(plan)
    elif arguments.command == "run-cell":
        run_cell(
            strict_json_load(arguments.plan),
            arguments.cell_index,
            arguments.run_directory,
        )
    elif arguments.command == "analyze":
        plan = strict_json_load(arguments.plan)
        cell_count = plan["payload"]["cell_count"]
        results = [
            strict_json_load(arguments.run_directory / "cells" / f"cell-{index:03d}" / "result.json")
            for index in range(cell_count)
        ]
        if plan["payload"]["artifact_type"] == "cthyb_estimator_plan":
            artifact = analyze_estimator_qualification(results, plan)
            output_name = "qualification.json"
        elif plan["payload"]["artifact_type"] == "cthyb_estimator_scaling_plan":
            artifact = analyze_estimator_scaling(results, plan)
            output_name = "scaling.json"
        else:
            artifact = build_calibration_artifact(plan, results)
            output_name = "calibration.json"
        atomic_write_bytes(
            arguments.run_directory / output_name,
            canonical_json(artifact) + b"\n",
        )
    else:
        artifact = strict_json_load(arguments.calibration)
        plan = strict_json_load(arguments.plan)
        if artifact.get("payload", {}).get("artifact_type") == "cthyb_estimator_qualification":
            expected = analyze_estimator_qualification(
                artifact["payload"]["cell_results"], plan
            )
            if canonical_json(artifact) != canonical_json(expected):
                raise ValueError("estimator qualification does not reproduce")
        elif artifact.get("payload", {}).get("artifact_type") == "cthyb_estimator_scaling":
            expected = analyze_estimator_scaling(
                artifact["payload"]["cell_results"], plan
            )
            if canonical_json(artifact) != canonical_json(expected):
                raise ValueError("estimator scaling artifact does not reproduce")
        else:
            validate_calibration(artifact, plan)


if __name__ == "__main__":
    main()
