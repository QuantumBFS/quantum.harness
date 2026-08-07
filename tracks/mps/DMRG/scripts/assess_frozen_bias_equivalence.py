from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from vmcrg_ref.fixed_point import bias_newton_correction


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Assess a frozen bias in coupling space without changing the bias"
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="directory containing summary.json and frozen_validation.json",
    )
    parser.add_argument(
        "--covariance-source",
        type=Path,
        help="directory containing trajectory.npz; defaults to --input",
    )
    parser.add_argument(
        "--validation",
        type=Path,
        help="validation JSON; defaults to INPUT/frozen_validation.json",
    )
    parser.add_argument("--late-window", type=int, default=600)
    parser.add_argument(
        "--trajectory-end-step",
        type=int,
        help="exclusive trajectory endpoint; defaults to the full trajectory",
    )
    parser.add_argument("--maximum-condition-number", type=float, default=1.0e6)
    parser.add_argument("--maximum-correction", type=float, default=1.0e-3)
    parser.add_argument("--bootstrap", type=int, default=2000)
    parser.add_argument("--bootstrap-seed", type=int, default=20260716)
    parser.add_argument("--confidence", type=float, default=0.95)
    parser.add_argument(
        "--output",
        type=Path,
        help="output report; defaults to INPUT/frozen_bias_equivalence.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.late_window <= 1:
        raise ValueError("late-window must exceed one optimization step")
    if args.maximum_condition_number <= 1.0:
        raise ValueError("maximum-condition-number must exceed one")
    if args.maximum_correction <= 0.0:
        raise ValueError("maximum-correction must be positive")
    if args.bootstrap <= 0:
        raise ValueError("bootstrap must be positive")
    if not 0.0 < args.confidence < 1.0:
        raise ValueError("confidence must lie strictly between zero and one")

    covariance_source = args.covariance_source or args.input
    summary_path = args.input / "summary.json"
    validation_path = args.validation or args.input / "frozen_validation.json"
    trajectory_path = covariance_source / "trajectory.npz"

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    with np.load(trajectory_path) as trajectory:
        covariance_history = np.asarray(trajectory["covariance"], dtype=np.float64)
    end_step = args.trajectory_end_step or len(covariance_history)
    if end_step <= 0 or end_step > len(covariance_history):
        raise ValueError("trajectory-end-step must lie inside the trajectory")
    if args.late_window > end_step:
        raise ValueError("late-window exceeds the available optimization trajectory")

    length = int(summary["length"])
    block_sites = (length // 3) ** 2
    mean_operators = (
        np.asarray(validation["mean_operators_per_block_site"], dtype=np.float64)
        * block_sites
    )
    covariance = covariance_history[end_step - args.late_window : end_step].mean(axis=0)
    estimate = bias_newton_correction(
        mean_operators,
        covariance,
        maximum_condition_number=args.maximum_condition_number,
        maximum_correction=np.inf,
    )
    correction_linf = float(np.max(np.abs(estimate.correction)))
    run_means_data = validation.get("run_means_per_block_site")
    bootstrap_deviation_linf: np.ndarray | None = None
    bootstrap_deviation_quantile: float | None = None
    upper_confidence_bound: float | None = None
    if run_means_data is not None:
        run_means = np.asarray(run_means_data, dtype=np.float64)
        if run_means.ndim != 2 or run_means.shape[1] != mean_operators.size:
            raise ValueError("run-level validation means have incompatible dimensions")
        if run_means.shape[0] < 2 or not np.all(np.isfinite(run_means)):
            raise ValueError("at least two finite run-level validation means are required")
        rng = np.random.default_rng(args.bootstrap_seed)
        bootstrap_deviation_linf = np.empty(args.bootstrap, dtype=np.float64)
        for sample in range(args.bootstrap):
            indices = rng.integers(0, run_means.shape[0], size=run_means.shape[0])
            bootstrap_mean = run_means[indices].mean(axis=0) * block_sites
            bootstrap_correction = np.linalg.solve(covariance, bootstrap_mean)
            bootstrap_deviation_linf[sample] = np.max(
                np.abs(bootstrap_correction - estimate.correction)
            )
        bootstrap_deviation_quantile = float(
            np.quantile(
                bootstrap_deviation_linf, args.confidence, method="higher"
            )
        )
        upper_confidence_bound = correction_linf + bootstrap_deviation_quantile
        status = (
            "PASS"
            if upper_confidence_bound <= args.maximum_correction
            else "FAIL"
        )
    else:
        status = "DIAGNOSTIC_ONLY"
    report = {
        "method": "validation_only_delta_J=Cov(S,S)^-1_mean(S)",
        "parameter_update_performed": False,
        "input_summary": str(summary_path.resolve()),
        "validation_source": str(validation_path.resolve()),
        "covariance_source": str(trajectory_path.resolve()),
        "late_covariance_window": args.late_window,
        "trajectory_end_step": end_step,
        "block_sites": block_sites,
        "mean_operators": mean_operators.tolist(),
        "covariance_condition_number": estimate.condition_number,
        "maximum_condition_number": args.maximum_condition_number,
        "inferred_bias_correction": estimate.correction.tolist(),
        "inferred_bias_correction_l2": float(np.linalg.norm(estimate.correction)),
        "inferred_bias_correction_linf": correction_linf,
        "maximum_correction": args.maximum_correction,
        "point_estimate_status": (
            "PASS" if correction_linf <= args.maximum_correction else "FAIL"
        ),
        "run_level_means_available": run_means_data is not None,
        "bootstrap_method": (
            "simultaneous_max_abs_centered_deviation_band"
            if bootstrap_deviation_linf is not None
            else None
        ),
        "bootstrap_replicates": (
            args.bootstrap if bootstrap_deviation_linf is not None else 0
        ),
        "bootstrap_seed": (
            args.bootstrap_seed if bootstrap_deviation_linf is not None else None
        ),
        "confidence_level": (
            args.confidence if bootstrap_deviation_linf is not None else None
        ),
        "bootstrap_deviation_linf_quantile": bootstrap_deviation_quantile,
        "correction_linf_upper_confidence_bound": upper_confidence_bound,
        "status": status,
        "z_test_diagnostic_only": {
            "max_abs_z": validation.get("max_abs_z"),
            "familywise_status": validation.get("familywise_status"),
        },
        "criteria_source": (
            "predeclared_implementation_acceptance_gate_not_paper_published"
        ),
    }

    output = args.output or args.input / "frozen_bias_equivalence.json"
    if output.exists():
        raise FileExistsError(f"refusing to overwrite equivalence report: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
