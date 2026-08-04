#!/usr/bin/env python3
"""Seal and score complete-realization SUSY Hodge predictions v7."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from run_susy_hodge_geometric_eth_v7 import (
    BASE_SEED,
    CHECKPOINT_ROOT,
    NULL_REPLICATES,
    OUTPUT_ROOT,
    VERSION,
    _atomic_json,
    _atomic_npz,
    _banked_complete_medians,
    _derived_seed,
    _validate_file_hash,
    panel_paths,
    registered_case_grid,
    seal_file_hash,
    sha256,
    unseal_outcomes,
    write_safe_covariates,
)
from run_susy_hodge_null_bank_v7 import (
    OUTPUT_ROOT as NULL_BANK_ROOT,
    null_bank_paths,
)


SCRIPT_ROOT = Path(__file__).resolve().parent
N14_SAFE_JSON = OUTPUT_ROOT / "susy_hodge_v7_N14_covariates.json"
N14_PREDICTION_JSON = OUTPUT_ROOT / "susy_hodge_v7_N14_prediction.json"
N14_PREDICTION_NPZ = OUTPUT_ROOT / "susy_hodge_v7_N14_prediction.npz"
N14_PREDICTION_SEAL = OUTPUT_ROOT / "susy_hodge_v7_N14_prediction.sha256"
N14_UNSEALED_JSON = OUTPUT_ROOT / "susy_hodge_v7_N14_unsealed.json"
N14_UNSEALED_NPZ = OUTPUT_ROOT / "susy_hodge_v7_N14_unsealed.npz"
N14_INFERENCE_JSON = OUTPUT_ROOT / "susy_hodge_v7_N14_inference.json"
PILOT_BANK_SAFE_JSON = OUTPUT_ROOT / "susy_hodge_v7_covariates_pilot_banked.json"
PILOT_BANK_JSON = OUTPUT_ROOT / "susy_hodge_v7_outcomes_pilot_banked.json"
PILOT_BANK_NPZ = OUTPUT_ROOT / "susy_hodge_v7_outcomes_pilot_banked.npz"
FORBIDDEN_PREDICTION_TOKENS = ("r4", "four_point", "connected")
PREDICTION_COVERAGE = 0.975
PREDICTION_QUANTILES = (0.0125, 0.5, 0.9875)
PHYSICAL_BOOTSTRAP_REPLICATES = 10_000


def _source_hashes() -> dict[str, str]:
    paths = (
        Path(__file__).resolve(),
        SCRIPT_ROOT / "run_susy_hodge_geometric_eth_v7.py",
        SCRIPT_ROOT / "run_susy_hodge_null_bank_v7.py",
        SCRIPT_ROOT / "lgeth" / "hodge_wick.py",
        SCRIPT_ROOT / "lgeth" / "wick_channels.py",
    )
    return {str(path.relative_to(SCRIPT_ROOT)): sha256(path) for path in paths}


def _array_hash(values: np.ndarray) -> str:
    contiguous = np.ascontiguousarray(values)
    import hashlib

    return hashlib.sha256(contiguous.view(np.uint8)).hexdigest()


def _group_cases(
    cases: list[tuple[int, str, int, str]],
) -> dict[tuple[int, str, str], list[int]]:
    groups: dict[tuple[int, str, str], list[int]] = {}
    if not cases:
        raise ValueError("prediction requires at least one case")
    for N, sector, realization, panel_kind in sorted(cases):
        key = (int(N), str(sector), str(panel_kind))
        groups.setdefault(key, []).append(int(realization))
    for key, realizations in groups.items():
        if len(realizations) != len(set(realizations)):
            raise ValueError(f"duplicate realization in prediction group {key}")
    return groups


def _load_group_banks(
    N: int,
    sector: str,
    panel_kind: str,
    realizations: list[int],
    *,
    null_bank_root: Path,
) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]]]:
    collapsed: list[np.ndarray] = []
    hodge: list[np.ndarray] = []
    records: list[dict[str, Any]] = []
    for realization in realizations:
        metadata_path, arrays_path = null_bank_paths(
            null_bank_root,
            N,
            sector,
            realization,
            panel_kind,
        )
        if not metadata_path.is_file() or not arrays_path.is_file():
            raise FileNotFoundError("missing safe null bank")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata.get("arrays_sha256") != sha256(arrays_path):
            raise ValueError("null-bank array hash mismatch")
        if not metadata.get("passed") or not all(metadata.get("checks", {}).values()):
            raise ValueError("null bank contains a failed gate")
        identity = metadata.get("identity", {})
        expected = (N, sector, realization, panel_kind)
        observed = tuple(
            identity.get(key)
            for key in ("N", "sector", "realization", "panel_kind")
        )
        if observed != expected:
            raise ValueError("null-bank case identity mismatch")
        with np.load(arrays_path) as arrays:
            collapsed_values = np.asarray(arrays["collapsed_null"], dtype=float)
            hodge_values = np.asarray(arrays["hodge_null"], dtype=float)
        if collapsed_values.ndim != 1 or hodge_values.shape != collapsed_values.shape:
            raise ValueError("null-bank draw shapes disagree")
        if not np.all(np.isfinite(collapsed_values)) or not np.all(
            np.isfinite(hodge_values)
        ):
            raise ValueError("null bank contains non-finite draws")
        collapsed.append(collapsed_values)
        hodge.append(hodge_values)
        records.append(
            {
                "realization": realization,
                "metadata_sha256": sha256(metadata_path),
                "arrays_sha256": sha256(arrays_path),
            }
        )
    return np.asarray(collapsed), np.asarray(hodge), records


def aggregate_pilot_from_banks(
    cases: list[tuple[int, str, int, str]],
    *,
    checkpoint_root: Path = CHECKPOINT_ROOT,
    null_bank_root: Path = NULL_BANK_ROOT,
    safe_covariates_json: Path = PILOT_BANK_SAFE_JSON,
    output_json: Path = PILOT_BANK_JSON,
    output_npz: Path = PILOT_BANK_NPZ,
    null_replicates: int = NULL_REPLICATES,
    bootstrap_replicates: int = PHYSICAL_BOOTSTRAP_REPLICATES,
    seed: int = BASE_SEED,
) -> dict[str, Any]:
    """Aggregate completed pilot sidecars using precomputed safe null banks."""

    null_count = int(null_replicates)
    bootstrap_count = int(bootstrap_replicates)
    if null_count < 1 or bootstrap_count < 1:
        raise ValueError("pilot aggregation requires positive replicate counts")
    groups = _group_cases(cases)
    write_safe_covariates(
        cases,
        root=checkpoint_root,
        output_json=safe_covariates_json,
    )
    output_arrays: dict[str, np.ndarray] = {}
    summaries: list[dict[str, Any]] = []
    for (N, sector, panel_kind), realizations in sorted(groups.items()):
        collapsed_banks, hodge_banks, bank_records = _load_group_banks(
            N,
            sector,
            panel_kind,
            realizations,
            null_bank_root=null_bank_root,
        )
        physical_values: list[float] = []
        balances: list[float] = []
        for realization in realizations:
            safe_path, arrays_path, outcome_path = panel_paths(
                checkpoint_root,
                N,
                sector,
                realization,
                panel_kind,
            )
            if not outcome_path.is_file():
                raise FileNotFoundError("missing sequential-pilot outcome sidecar")
            safe = json.loads(safe_path.read_text(encoding="utf-8"))
            outcome = json.loads(outcome_path.read_text(encoding="utf-8"))
            if (
                safe.get("arrays_sha256") != sha256(arrays_path)
                or outcome.get("safe_identity_hash") != safe.get("identity_hash")
                or outcome.get("safe_arrays_sha256") != safe.get("arrays_sha256")
            ):
                raise ValueError("pilot outcome identity mismatch")
            observed_case = tuple(
                outcome.get(key)
                for key in ("N", "sector", "realization", "panel_kind")
            )
            if observed_case != (N, sector, realization, panel_kind):
                raise ValueError("pilot outcome case identity mismatch")
            physical_values.append(float(outcome["R4"]))
            balances.append(float(safe["signature"]["hodge_balance"]))
        physical = np.asarray(physical_values, dtype=float)
        if not np.all(np.isfinite(physical)):
            raise ValueError("pilot physical outcome is not finite")
        physical_bootstrap = _bootstrap_median(
            physical,
            bootstrap_count,
            _derived_seed(seed, N, sector, panel_kind, "pilot_physical_bootstrap"),
        )
        collapsed = _banked_complete_medians(
            collapsed_banks,
            null_count,
            _derived_seed(seed, N, sector, panel_kind, "pilot_collapsed"),
        )
        hodge = _banked_complete_medians(
            hodge_banks,
            null_count,
            _derived_seed(seed, N, sector, panel_kind, "pilot_hodge"),
        )
        prefix = f"N{N}_{sector}_{panel_kind}"
        output_arrays[f"{prefix}_physical"] = physical
        output_arrays[f"{prefix}_physical_bootstrap"] = physical_bootstrap
        output_arrays[f"{prefix}_collapsed_null"] = collapsed
        output_arrays[f"{prefix}_hodge_null"] = hodge
        observed_median = float(np.median(physical))
        collapsed_interval = np.quantile(
            collapsed, PREDICTION_QUANTILES
        ).tolist()
        hodge_interval = np.quantile(hodge, PREDICTION_QUANTILES).tolist()
        summaries.append(
            {
                "N": N,
                "sector": sector,
                "panel_kind": panel_kind,
                "realizations": len(realizations),
                "observed_median": observed_median,
                "physical_bootstrap_interval": np.quantile(
                    physical_bootstrap, [0.025, 0.975]
                ).tolist(),
                "collapsed_prediction_interval": collapsed_interval,
                "hodge_prediction_interval": hodge_interval,
                "collapsed_covered": collapsed_interval[0]
                <= observed_median
                <= collapsed_interval[2],
                "hodge_covered": hodge_interval[0]
                <= observed_median
                <= hodge_interval[2],
                "median_hodge_balance": float(np.median(balances)),
                "null_banks": bank_records,
            }
        )
    _atomic_npz(output_npz, **output_arrays)
    checks = {
        "complete_requested_grid": sum(
            item["realizations"] for item in summaries
        )
        == len(cases),
        "finite_outputs": all(
            np.all(np.isfinite(values)) for values in output_arrays.values()
        ),
        "registered_null_replicates": all(
            values.shape == (null_count,)
            for key, values in output_arrays.items()
            if key.endswith("_null")
        ),
        "registered_bootstrap_replicates": all(
            values.shape == (bootstrap_count,)
            for key, values in output_arrays.items()
            if key.endswith("_physical_bootstrap")
        ),
        "safe_covariates_preexist": Path(safe_covariates_json).is_file(),
    }
    payload = {
        "version": VERSION,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "uncertainty_unit": "complete_disorder_realization",
        "null_replicates": null_count,
        "physical_bootstrap_replicates": bootstrap_count,
        "prediction_coverage": PREDICTION_COVERAGE,
        "groups": summaries,
        "safe_covariates_sha256": sha256(safe_covariates_json),
        "arrays_sha256": sha256(output_npz),
        "sources": _source_hashes(),
        "checks": checks,
        "passed": all(checks.values()),
    }
    if not payload["passed"]:
        raise RuntimeError(f"banked pilot aggregation failed: {checks}")
    _atomic_json(output_json, payload)
    return payload


def write_n14_prediction(
    cases: list[tuple[int, str, int, str]],
    *,
    checkpoint_root: Path = CHECKPOINT_ROOT,
    null_bank_root: Path = NULL_BANK_ROOT,
    safe_covariates_json: Path = N14_SAFE_JSON,
    output_json: Path = N14_PREDICTION_JSON,
    output_npz: Path = N14_PREDICTION_NPZ,
    seal_path: Path = N14_PREDICTION_SEAL,
    null_replicates: int = NULL_REPLICATES,
    seed: int = BASE_SEED,
) -> dict[str, Any]:
    """Predict group medians from safe two-point data and seal before unseal."""

    count = int(null_replicates)
    if count < 1:
        raise ValueError("prediction requires positive null replicates")
    groups = _group_cases(cases)
    sizes = {key[0] for key in groups}
    if len(sizes) != 1:
        raise ValueError("a prediction seal must contain exactly one system size")
    N = next(iter(sizes))
    required_primary = {(N, "central", "sparse"), (N, "adjacent", "sparse")}
    if not required_primary.issubset(groups):
        raise ValueError("prediction is missing the registered sparse primary pair")
    write_safe_covariates(
        cases,
        root=checkpoint_root,
        output_json=safe_covariates_json,
    )
    output_arrays: dict[str, np.ndarray] = {}
    summaries: list[dict[str, Any]] = []
    primary_pair: list[dict[str, Any]] = []
    for (group_N, sector, panel_kind), realizations in sorted(groups.items()):
        collapsed_banks, hodge_banks, bank_records = _load_group_banks(
            group_N,
            sector,
            panel_kind,
            realizations,
            null_bank_root=null_bank_root,
        )
        collapsed = _banked_complete_medians(
            collapsed_banks,
            count,
            _derived_seed(seed, group_N, sector, panel_kind, "sealed_collapsed"),
        )
        hodge = _banked_complete_medians(
            hodge_banks,
            count,
            _derived_seed(seed, group_N, sector, panel_kind, "sealed_hodge"),
        )
        prefix = f"N{group_N}_{sector}_{panel_kind}"
        output_arrays[f"{prefix}_collapsed"] = collapsed
        output_arrays[f"{prefix}_hodge"] = hodge
        record = {
            "N": group_N,
            "sector": sector,
            "panel_kind": panel_kind,
            "realizations": len(realizations),
            "realization_ids": realizations,
            "collapsed_interval": np.quantile(
                collapsed, PREDICTION_QUANTILES
            ).tolist(),
            "hodge_interval": np.quantile(hodge, PREDICTION_QUANTILES).tolist(),
            "collapsed_array_sha256": _array_hash(collapsed),
            "hodge_array_sha256": _array_hash(hodge),
            "null_banks": bank_records,
        }
        summaries.append(record)
        if panel_kind == "sparse" and sector in {"central", "adjacent"}:
            primary_pair.append(
                {
                    key: record[key]
                    for key in (
                        "N",
                        "sector",
                        "panel_kind",
                        "realizations",
                        "collapsed_interval",
                        "hodge_interval",
                    )
                }
            )
    _atomic_npz(output_npz, **output_arrays)
    checks = {
        "complete_requested_grid": sum(
            item["realizations"] for item in summaries
        )
        == len(cases),
        "registered_primary_pair": {
            (item["sector"], item["panel_kind"]) for item in primary_pair
        }
        == {("central", "sparse"), ("adjacent", "sparse")},
        "finite_prediction_arrays": all(
            np.all(np.isfinite(values)) for values in output_arrays.values()
        ),
        "complete_realization_unit": all(
            item["realizations"] == len(item["realization_ids"])
            for item in summaries
        ),
        "safe_covariates_preexist": Path(safe_covariates_json).is_file(),
    }
    payload = {
        "version": VERSION,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "system_size": N,
        "observable": "normalized_response_memory",
        "uncertainty_unit": "complete_disorder_realization",
        "prediction_coverage": PREDICTION_COVERAGE,
        "prediction_quantiles": list(PREDICTION_QUANTILES),
        "null_replicates": count,
        "safe_covariates_sha256": sha256(safe_covariates_json),
        "prediction_arrays_file": Path(output_npz).name,
        "prediction_arrays_sha256": sha256(output_npz),
        "sources": _source_hashes(),
        "groups": summaries,
        "primary_pair": primary_pair,
        "checks": checks,
    }
    serialized = json.dumps(payload, sort_keys=True).lower()
    payload["checks"]["no_outcome_leakage"] = not any(
        token in serialized for token in FORBIDDEN_PREDICTION_TOKENS
    )
    payload["passed"] = all(payload["checks"].values())
    if not payload["passed"]:
        raise RuntimeError(f"sealed prediction audit failed: {payload['checks']}")
    _atomic_json(output_json, payload)
    seal_file_hash(output_json, seal_path)
    return payload


def _bootstrap_median(
    values: np.ndarray,
    replicates: int,
    seed: int,
) -> np.ndarray:
    samples = np.asarray(values, dtype=float)
    count = int(replicates)
    if samples.ndim != 1 or samples.size < 1 or count < 1:
        raise ValueError("median bootstrap requires a nonempty realization vector")
    rng = np.random.default_rng(int(seed))
    indices = rng.integers(0, samples.size, size=(count, samples.size))
    return np.median(samples[indices], axis=1)


def select_frozen_branch(
    collapsed_pair_covered: bool,
    hodge_pair_covered: bool,
    structured_indistinguishable: bool,
    numerical_gates_passed: bool,
) -> str:
    """Map the registered pair outcome to exactly one frozen result branch."""

    if not numerical_gates_passed:
        return "feasibility_failure"
    if collapsed_pair_covered and hodge_pair_covered:
        return "strong_covariance_universality"
    if not collapsed_pair_covered and hodge_pair_covered:
        return "hodge_resolved_geometric_eth"
    if not collapsed_pair_covered and not hodge_pair_covered:
        if structured_indistinguishable:
            return "structured_cohomology"
        return "cohomological_non_gaussian_class"
    # A collapsed-only success is not one of the preregistered scientific
    # branches, so the analysis fails closed instead of inventing a claim.
    return "feasibility_failure"


def _outside_interval(confidence: list[float], interval: list[float]) -> bool:
    return confidence[1] < interval[0] or confidence[0] > interval[2]


def score_unsealed_n14(
    prediction_json: Path,
    prediction_seal: Path,
    unsealed_json: Path,
    *,
    output_json: Path = N14_INFERENCE_JSON,
    bootstrap_replicates: int = PHYSICAL_BOOTSTRAP_REPLICATES,
    seed: int = BASE_SEED,
    structured_indistinguishable: bool = False,
) -> dict[str, Any]:
    """Score the held-out sparse pair after validating the prediction seal."""

    prediction_hash = _validate_file_hash(prediction_json, prediction_seal)
    prediction = json.loads(Path(prediction_json).read_text(encoding="utf-8"))
    if not prediction.get("passed") or not all(prediction.get("checks", {}).values()):
        raise ValueError("sealed prediction contains a failed gate")
    unsealed = json.loads(Path(unsealed_json).read_text(encoding="utf-8"))
    if not unsealed.get("passed"):
        raise ValueError("unsealed outcome aggregate contains a failed gate")
    if unsealed.get("prediction_sha256") != prediction_hash:
        raise ValueError("unsealed aggregate references the wrong prediction")
    try:
        prediction_time = datetime.fromisoformat(prediction["generated_utc"])
        unsealed_time = datetime.fromisoformat(unsealed["unsealed_utc"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("prediction/unseal timestamp is invalid") from error
    if unsealed_time <= prediction_time:
        raise ValueError("prediction must precede the outcome unseal")
    records = unsealed.get("records", [])
    primary = {
        (int(item["N"]), str(item["sector"]), str(item["panel_kind"])): item
        for item in prediction["primary_pair"]
    }
    results: list[dict[str, Any]] = []
    for key, predicted in sorted(primary.items()):
        N, sector, panel_kind = key
        values = np.asarray(
            [
                float(record["R4"])
                for record in records
                if (
                    int(record["N"]),
                    str(record["sector"]),
                    str(record["panel_kind"]),
                )
                == key
            ],
            dtype=float,
        )
        if values.size != int(predicted["realizations"]):
            raise ValueError("unsealed primary realization count mismatch")
        bootstrap = _bootstrap_median(
            values,
            int(bootstrap_replicates),
            _derived_seed(seed, N, sector, panel_kind, "physical_bootstrap"),
        )
        observed = float(np.median(values))
        confidence = np.quantile(bootstrap, [0.025, 0.975]).tolist()
        collapsed_interval = [float(value) for value in predicted["collapsed_interval"]]
        hodge_interval = [float(value) for value in predicted["hodge_interval"]]
        results.append(
            {
                "N": N,
                "sector": sector,
                "panel_kind": panel_kind,
                "realizations": int(values.size),
                "observed_median": observed,
                "physical_bootstrap_interval": confidence,
                "collapsed_prediction_interval": collapsed_interval,
                "hodge_prediction_interval": hodge_interval,
                "collapsed_covered": collapsed_interval[0]
                <= observed
                <= collapsed_interval[2],
                "hodge_covered": hodge_interval[0]
                <= observed
                <= hodge_interval[2],
                "robust_outside_both": _outside_interval(
                    confidence, collapsed_interval
                )
                and _outside_interval(confidence, hodge_interval),
            }
        )
    collapsed_pair = all(item["collapsed_covered"] for item in results)
    hodge_pair = all(item["hodge_covered"] for item in results)
    robust_non_gaussian = all(item["robust_outside_both"] for item in results)
    inference_resolved = (
        collapsed_pair
        or hodge_pair
        or bool(structured_indistinguishable)
        or robust_non_gaussian
    )
    numerical_gates = (
        len(results) == 2
        and all(np.isfinite(item["observed_median"]) for item in results)
        and inference_resolved
    )
    branch = select_frozen_branch(
        collapsed_pair,
        hodge_pair,
        bool(structured_indistinguishable),
        numerical_gates,
    )
    payload = {
        "version": VERSION,
        "unsealed_utc": unsealed.get("unsealed_utc"),
        "scored_utc": datetime.now(timezone.utc).isoformat(),
        "prediction_sha256": prediction_hash,
        "selected_branch": branch,
        "primary_pair": results,
        "pair_coverage": {
            "collapsed": collapsed_pair,
            "hodge": hodge_pair,
        },
        "robust_non_gaussian_excess": robust_non_gaussian,
        "structured_indistinguishable": bool(structured_indistinguishable),
        "physical_bootstrap_replicates": int(bootstrap_replicates),
        "checks": {
            "valid_prediction_seal": True,
            "prediction_precedes_unseal": unsealed_time > prediction_time,
            "complete_primary_pair": len(results) == 2,
            "complete_realization_uncertainty": all(
                item["realizations"] > 0 for item in results
            ),
            "registered_branch_resolved": inference_resolved,
        },
    }
    payload["passed"] = all(payload["checks"].values())
    _atomic_json(output_json, payload)
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    predict = subparsers.add_parser("predict")
    predict.add_argument("--null-replicates", type=int, default=NULL_REPLICATES)
    unseal = subparsers.add_parser("unseal")
    unseal.add_argument(
        "--bootstrap-replicates",
        type=int,
        default=PHYSICAL_BOOTSTRAP_REPLICATES,
    )
    pilot = subparsers.add_parser("pilot")
    pilot.add_argument("--sizes", type=int, nargs="+", required=True)
    pilot.add_argument("--null-replicates", type=int, default=NULL_REPLICATES)
    pilot.add_argument(
        "--bootstrap-replicates",
        type=int,
        default=PHYSICAL_BOOTSTRAP_REPLICATES,
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "pilot":
        payload = aggregate_pilot_from_banks(
            registered_case_grid(tuple(args.sizes)),
            null_replicates=args.null_replicates,
            bootstrap_replicates=args.bootstrap_replicates,
        )
    elif args.command == "predict":
        cases = registered_case_grid((14,))
        payload = write_n14_prediction(
            cases,
            null_replicates=args.null_replicates,
        )
    else:
        cases = registered_case_grid((14,))
        unseal_outcomes(
            cases,
            prediction_json=N14_PREDICTION_JSON,
            prediction_seal=N14_PREDICTION_SEAL,
            output_json=N14_UNSEALED_JSON,
            output_npz=N14_UNSEALED_NPZ,
        )
        payload = score_unsealed_n14(
            N14_PREDICTION_JSON,
            N14_PREDICTION_SEAL,
            N14_UNSEALED_JSON,
            bootstrap_replicates=args.bootstrap_replicates,
        )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
