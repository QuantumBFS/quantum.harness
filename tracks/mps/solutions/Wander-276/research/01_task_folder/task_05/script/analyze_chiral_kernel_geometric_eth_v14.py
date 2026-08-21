#!/usr/bin/env python3
"""Evaluate the sealed chiral-index prediction without refitting its band."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from run_chiral_kernel_geometric_eth_v14 import validate_prediction_seal


VERSION = "v14"
SCRIPT_ROOT = Path(__file__).resolve().parent
DEFAULT_REPO = SCRIPT_ROOT.parents[2]
OUTPUT_ROOT = SCRIPT_ROOT / "output/geometric_eth_theory_v14"
DEFAULT_PREDICTION = OUTPUT_ROOT / "chiral_prediction_v14.json"
DEFAULT_SIDECAR = OUTPUT_ROOT / "chiral_prediction_v14.sha256"
DEFAULT_OUTCOMES = OUTPUT_ROOT / "chiral_outcomes_v14.json"
DEFAULT_OUTPUT = OUTPUT_ROOT / "chiral_inference_v14.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"missing JSON input: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"JSON input is not an object: {path}")
    return payload


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
            os.fchmod(handle.fileno(), 0o644)
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _parse_timestamp(value: Any, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise RuntimeError(f"{label} timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise RuntimeError(f"{label} timestamp is not timezone aware")
    return parsed


def _bootstrap_interval(
    values: np.ndarray,
    *,
    generator: np.random.Generator,
    replicates: int,
    lower_quantile: float,
    upper_quantile: float,
) -> tuple[float, float]:
    if values.ndim != 1 or values.size < 2 or not np.all(np.isfinite(values)):
        raise RuntimeError("base-bootstrap input is invalid")
    indices = generator.integers(0, values.size, size=(replicates, values.size))
    means = np.mean(values[indices], axis=1)
    return (
        float(np.quantile(means, lower_quantile)),
        float(np.quantile(means, upper_quantile)),
    )


def evaluate_chiral_prediction(
    prediction: Mapping[str, Any],
    outcomes: Mapping[str, Any],
    *,
    prediction_file_sha256: str,
) -> dict[str, Any]:
    """Apply only the decision rules frozen in the prediction artifact."""

    if prediction.get("schema") != "chiral_kernel_prediction_v14":
        raise RuntimeError("prediction schema is invalid")
    if outcomes.get("schema") != "chiral_kernel_outcomes_v14":
        raise RuntimeError("outcomes schema is invalid")
    if outcomes.get("prediction_sha256") != prediction_file_sha256:
        raise RuntimeError("outcomes prediction hash does not match the sealed file")
    sealed = _parse_timestamp(prediction.get("sealed_utc"), "seal")
    generated = _parse_timestamp(outcomes.get("generated_utc"), "outcome")
    if generated <= sealed:
        raise RuntimeError("outcome timestamp must be later than the prediction seal")

    grid = prediction["registered_grid"]
    expected_sizes = grid["validation_sizes"]
    execution = outcomes.get("execution", {})
    if execution.get("sizes") != expected_sizes:
        raise RuntimeError("outcomes do not contain the frozen validation grid")
    if execution.get("bases_per_size") != grid["bases_per_size"]:
        raise RuntimeError("outcomes changed the frozen base count")
    if execution.get("tangents_per_base") != grid["tangents_per_base"]:
        raise RuntimeError("outcomes changed the frozen tangent count")
    if execution.get("tangent_classes") != grid["tangent_classes"]:
        raise RuntimeError("outcomes changed the frozen tangent classes")

    analysis = prediction["registered_analysis"]
    bootstrap = analysis["base_bootstrap"]
    class_order = bootstrap["class_order"]
    size_order = bootstrap["size_order"]
    if class_order != grid["tangent_classes"] or size_order != expected_sizes:
        raise RuntimeError("prediction analysis order is inconsistent with its grid")
    seed_sequences = np.random.SeedSequence(bootstrap["master_seed"]).spawn(
        len(class_order) * len(size_order)
    )
    band = prediction["primary_prediction"]["simultaneous_band"]
    band_lower = float(band["lower"])
    band_upper = float(band["upper"])

    class_inference: dict[str, Any] = {}
    seed_index = 0
    for class_name in class_order:
        cases = []
        for n_b, n_a in size_order:
            case_id = f"n_b{n_b}_n_a{n_a}"
            try:
                base_values = np.asarray(
                    outcomes["cases"][case_id]["classes"][class_name]
                    ["aggregate_after_safe_gates"]
                    ["base_mean_effective_scaled_complete_standardized_fourth_cumulant"],
                    dtype=float,
                )
            except KeyError as exc:
                raise RuntimeError(f"missing registered outcome tensor: {case_id}, {class_name}") from exc
            if base_values.size != grid["bases_per_size"]:
                raise RuntimeError("base-bootstrap unit count does not match the seal")
            interval_low, interval_high = _bootstrap_interval(
                base_values,
                generator=np.random.default_rng(seed_sequences[seed_index]),
                replicates=bootstrap["replicates"],
                lower_quantile=bootstrap["lower_quantile"],
                upper_quantile=bootstrap["upper_quantile"],
            )
            seed_index += 1
            point = float(np.mean(base_values))
            cases.append(
                {
                    "case_id": case_id,
                    "n_b": int(n_b),
                    "n_a": int(n_a),
                    "fiber_rank": int(n_a - n_b),
                    "base_count": int(base_values.size),
                    "tangents_averaged_per_base": int(grid["tangents_per_base"]),
                    "point_estimate": point,
                    "interval_low": interval_low,
                    "interval_high": interval_high,
                    "bootstrap_replicates": int(bootstrap["replicates"]),
                    "inside_frozen_band": bool(band_lower <= point <= band_upper),
                    "interval_disjoint_from_frozen_band": bool(
                        interval_high < band_lower or interval_low > band_upper
                    ),
                }
            )
        class_inference[class_name] = {"cases": cases}

    random_cases = class_inference["random"]["cases"]
    random_pass = all(case["inside_frozen_band"] for case in random_cases)
    control_rule = analysis["structured_control_separation"]
    required_size = tuple(control_rule["must_include_size"])
    control_records: dict[str, Any] = {}
    for class_name in control_rule["eligible_classes"]:
        disjoint = [
            case for case in class_inference[class_name]["cases"]
            if case["interval_disjoint_from_frozen_band"]
        ]
        required_present = any(
            (case["n_b"], case["n_a"]) == required_size for case in disjoint
        )
        passed = (
            len(disjoint) >= control_rule["minimum_disjoint_sizes"]
            and required_present
        )
        control_records[class_name] = {
            "disjoint_case_ids": [case["case_id"] for case in disjoint],
            "disjoint_size_count": len(disjoint),
            "required_largest_size_disjoint": required_present,
            "passes_registered_separation": passed,
        }
    control_pass = any(
        record["passes_registered_separation"]
        for record in control_records.values()
    )

    outcome_checks = outcomes.get("checks", {})
    exact_pass = bool(
        outcomes.get("all_checks_pass") is True
        and outcome_checks.get("prediction_seal_verified_before_outcomes") is True
        and outcome_checks.get("all_exact_index_gates_pass") is True
    )
    if not exact_pass:
        selected = "feasibility_failure"
    elif not random_pass:
        selected = "random_channel_failure"
    elif control_pass:
        selected = "deformed_locality_class"
    else:
        selected = "channel_law_validated"
    if selected not in prediction["branch_precedence"]:
        raise RuntimeError("selected branch is absent from frozen precedence")

    return {
        "version": VERSION,
        "schema": "chiral_kernel_inference_v14",
        "prediction_sha256": prediction_file_sha256,
        "sealed_utc": prediction["sealed_utc"],
        "outcomes_generated_utc": outcomes["generated_utc"],
        "checks": {
            "prediction_hash_matches_outcomes": True,
            "seal_precedes_outcomes": True,
            "all_exact_index_gates_pass": exact_pass,
            "frozen_grid_and_analysis_order": True,
        },
        "statistic": prediction["primary_prediction"]["statistic"],
        "random_primary": {
            "band": band,
            "cases": random_cases,
            "all_validation_points_inside_band": random_pass,
            "bootstrap_intervals_reporting_only": True,
        },
        "class_inference": class_inference,
        "structured_control": {
            "registered_rule": control_rule,
            "classes": control_records,
            "at_least_one_control_separates": control_pass,
        },
        "selected_branch": selected,
        "title_component_pass": bool(exact_pass and random_pass and control_pass),
        "quantitative_prediction_available": True,
        "quantitative_prediction": (
            "the complete standardized fourth cumulant is tested against the "
            "fixed inverse-effective-channel scaling variable without an exponent fit"
        ),
        "exponent_fit_performed": False,
        "claim_boundary": [
            "the frozen random-channel prediction failed if selected_branch is random_channel_failure",
            "bootstrap intervals report uncertainty and never widen the sealed band",
            "no archival model is used to refit the chiral prediction",
            "this finite-size test does not establish asymptotic or universal Geometric ETH",
        ],
    }


def analyze_chiral_files(
    *,
    repo_root: Path,
    prediction_path: Path,
    sidecar_path: Path,
    outcomes_path: Path,
    output_path: Path | None,
) -> dict[str, Any]:
    prediction = validate_prediction_seal(
        repo_root=repo_root,
        prediction_path=prediction_path,
        sidecar_path=sidecar_path,
    )
    outcomes = _json_object(outcomes_path)
    result = evaluate_chiral_prediction(
        prediction,
        outcomes,
        prediction_file_sha256=_sha256(prediction_path),
    )
    result["source_hashes"] = {
        str(prediction_path.relative_to(repo_root)): _sha256(prediction_path),
        str(outcomes_path.relative_to(repo_root)): _sha256(outcomes_path),
        str(Path(__file__).resolve().relative_to(repo_root.resolve())): _sha256(Path(__file__)),
    }
    if output_path is not None:
        _atomic_json(output_path, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO)
    parser.add_argument("--prediction", type=Path, default=DEFAULT_PREDICTION)
    parser.add_argument("--sidecar", type=Path, default=DEFAULT_SIDECAR)
    parser.add_argument("--outcomes", type=Path, default=DEFAULT_OUTCOMES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()
    result = analyze_chiral_files(
        repo_root=arguments.repo_root,
        prediction_path=arguments.prediction,
        sidecar_path=arguments.sidecar,
        outcomes_path=arguments.outcomes,
        output_path=arguments.output,
    )
    print(json.dumps({"output": str(arguments.output), "selected_branch": result["selected_branch"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
