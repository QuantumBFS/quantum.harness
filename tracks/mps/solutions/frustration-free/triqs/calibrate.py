"""Hash-bound CT-HYB calibration plans, execution, and statistical gates."""

from __future__ import annotations

import argparse
import copy
import math
from pathlib import Path
import shlex
from statistics import mean, stdev
from typing import Sequence

from scipy.stats import chi2, t

from artifacts import atomic_write_bytes, canonical_json, sha256_bytes, strict_json_load


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
PRODUCTION_SEEDS = {810001, 810002, 810003, 810004}
_WARMUPS = (12500, 25000, 50000)
_CYCLES = (10, 25, 50, 100)


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
    expected = {(level, replica) for level in _WARMUPS for replica in range(4)}
    _inventory(cells, expected, "warmup_cycles", "warmup")
    if any(
        cell.get("cell_kind") != "warmup" or cell.get("estimator") != "direct"
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
        se25, se50 = stdev(groups[25000]) / 2, stdev(groups[50000]) / 2
        a, b = se25**2, se50**2
        delta, se_delta = mean50 - mean25, math.sqrt(a + b)
        denominator = a**2 / 3 + b**2 / 3
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
    return {
        "candidate_lengths": list(_CYCLES),
        "selected_cycle_length": selected,
        "maximum_allowed_autocorrelation": 5.0,
        "passed": selected == 50,
    }


def analyze_batch_means(cells: Sequence[dict[str, object]]) -> dict[str, object]:
    if len(cells) != 32:
        raise ValueError("increment cell count mismatch")
    identities = {cell.get("input_identity") for cell in cells}
    seeds = [cell.get("seed") for cell in cells]
    expected = {(group, increment) for group in range(4) for increment in range(8)}
    actual = {(cell.get("group"), cell.get("increment")) for cell in cells}
    if (
        len(identities) != 1
        or len(seeds) != len(set(seeds))
        or set(seeds) & PRODUCTION_SEEDS
        or actual != expected
        or any(
            cell.get("cell_kind") != "increment"
            or cell.get("estimator") != "direct_increment"
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
        for group in range(4)
    }
    result = {}
    drift_quantile = float(t.ppf(1 - 0.01 / 16, 3))
    variance_quantile = float(chi2.ppf(0.01, 28))
    for name in OBSERVABLES:
        groups = [[_values(cell)[name] for cell in ordered[group]] for group in range(4)]
        differences = [mean(group[4:]) - mean(group[:4]) for group in groups]
        drift, drift_se = mean(differences), stdev(differences) / 2
        interval = [
            drift - drift_quantile * drift_se,
            drift + drift_quantile * drift_se,
        ]
        variances = [stdev(group) ** 2 for group in groups]
        pooled = sum(7 * value for value in variances) / 28
        upper = math.sqrt(28 * pooled / (variance_quantile * 64))
        bound = _bound(name)
        result[name] = {
            "batch_means": groups,
            "paired_differences": differences,
            "mean_drift": drift,
            "drift_standard_error": drift_se,
            "drift_degrees_of_freedom": 3,
            "drift_quantile": drift_quantile,
            "drift_interval": interval,
            "pooled_within_group_variance": pooled,
            "variance_degrees_of_freedom": 28,
            "production_batch_equivalents": 64,
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


def build_calibration_plan(bindings: dict[str, object]) -> dict[str, object]:
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
    identity = sha256_bytes(canonical_json(bindings))
    cells, index = [], 0
    for level, warmup in enumerate(_WARMUPS):
        for replica in range(4):
            cells.append(
                _cell(
                    index,
                    "warmup",
                    820000 + level * 10 + replica,
                    identity,
                    {
                        "warmup_cycles": warmup,
                        "measurement_cycles": 100000,
                        "cycle_length": 50,
                        "replica": replica,
                        "estimator": "direct",
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
                    821000 + level * 10 + replica,
                    identity,
                    {
                        "warmup_cycles": 50000,
                        "measurement_cycles": 100000,
                        "cycle_length": cycle,
                        "replica": replica,
                    },
                )
            )
            index += 1
    for group in range(4):
        for increment in range(8):
            cells.append(
                _cell(
                    index,
                    "increment",
                    822000 + group * 10 + increment,
                    identity,
                    {
                        "warmup_cycles": 50000,
                        "measurement_cycles": 62500,
                        "cycle_length": 50,
                        "group": group,
                        "increment": increment,
                        "estimator": "direct_increment",
                    },
                )
            )
            index += 1
    return _artifact(
        {
            "artifact_type": "cthyb_calibration_plan",
            "schema_version": 2,
            "bindings": copy.deepcopy(bindings),
            "input_identity": identity,
            "cell_count": 60,
            "cells": cells,
        }
    )


def validate_calibration_plan(plan: object) -> None:
    if not isinstance(plan, dict) or set(plan) != {"payload", "sha256"}:
        raise ValueError("calibration plan artifact is malformed")
    payload = plan["payload"]
    if not isinstance(payload, dict) or plan["sha256"] != sha256_bytes(canonical_json(payload)):
        raise ValueError("calibration plan hash mismatch")
    expected = build_calibration_plan(payload.get("bindings"))
    if canonical_json(plan) != canonical_json(expected):
        raise ValueError("calibration plan differs from canonical plan")


def validate_calibration(artifact: object, calibration_plan: object) -> None:
    validate_calibration_plan(calibration_plan)
    if not isinstance(artifact, dict) or set(artifact) != {"payload", "sha256"}:
        raise ValueError("calibration artifact is malformed")
    payload = artifact["payload"]
    if artifact["sha256"] != sha256_bytes(canonical_json(payload)):
        raise ValueError("calibration hash mismatch")
    if payload.get("plan") != calibration_plan or len(payload.get("cell_results", [])) != 60:
        raise ValueError("calibration plan or result inventory mismatch")
    results = payload["cell_results"]
    if any(
        result.get("sha256") != sha256_bytes(canonical_json(result.get("payload")))
        for result in results
    ):
        raise ValueError("calibration result hash mismatch")
    cells = [result["payload"] for result in results]
    expected_analysis = {
        "warmup": analyze_warmup(cells[:12]),
        "cycle": select_cycle_length(cells[12:28]),
        "batch": analyze_batch_means(cells[28:]),
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
    accepted = all(value["passed"] for value in expected_analysis.values())
    if payload.get("status") != ("accepted" if accepted else "failed"):
        raise ValueError("calibration status disagrees with gates")


def calibration_cluster_commands(
    micromamba: Path, prefix: Path, plan: Path, run_directory: Path
) -> dict[str, str]:
    if not all(path.is_absolute() for path in (micromamba, prefix, plan, run_directory)):
        raise ValueError("cluster paths must be absolute")
    script = Path(__file__).resolve()
    wrapper = script.with_name("cthyb_calibration_slurm_array.sh")
    base = (
        f"{shlex.quote(str(micromamba))} run --offline --prefix "
        f"{shlex.quote(str(prefix))} python {shlex.quote(str(script))}"
    )
    export = (
        "ALL,OMP_NUM_THREADS=1,OPENBLAS_NUM_THREADS=1,MKL_NUM_THREADS=1,"
        f"CTHYB_MICROMAMBA={micromamba},CTHYB_ENV={prefix},"
        f"CTHYB_CAL_PLAN={plan},CTHYB_CAL_RUN={run_directory}"
    )
    return {
        "validate": f"{base} validate-plan --plan {shlex.quote(str(plan))}",
        "array": (
            "sbatch --array=0-59 --ntasks=1 --cpus-per-task=1 --mem=4G "
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


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate-plan")
    validate.add_argument("--plan", type=Path, required=True)
    existing = commands.add_parser("validate-existing")
    existing.add_argument("--plan", type=Path, required=True)
    existing.add_argument("--run-directory", type=Path, required=True)
    existing.add_argument("--calibration", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.command == "validate-plan":
        validate_calibration_plan(strict_json_load(arguments.plan))
    else:
        validate_calibration(
            strict_json_load(arguments.calibration),
            strict_json_load(arguments.plan),
        )


if __name__ == "__main__":
    main()
