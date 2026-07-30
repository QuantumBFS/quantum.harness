from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from vmcrg_ref.fixed_point import bias_newton_correction


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply one independently measured Newton correction to a frozen bias"
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument(
        "--covariance-source",
        type=Path,
        help="trajectory directory used for the late Hessian; defaults to INPUT",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--late-window", type=int, default=600)
    parser.add_argument("--maximum-condition-number", type=float, default=1.0e6)
    parser.add_argument("--maximum-correction", type=float, default=1.0e-3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_dir = args.input.resolve()
    covariance_source = (
        args.covariance_source.resolve() if args.covariance_source else input_dir
    )
    validation_path = args.validation.resolve()
    output_dir = args.output.resolve()
    if (output_dir / "summary.json").exists() or (output_dir / "correction.json").exists():
        raise FileExistsError(f"refusing to overwrite corrected bias output: {output_dir}")
    summary = json.loads((input_dir / "summary.json").read_text(encoding="utf-8"))
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    with np.load(covariance_source / "trajectory.npz") as trajectory:
        covariance_history = np.asarray(trajectory["covariance"], dtype=np.float64)
    if args.late_window <= 1 or args.late_window > len(covariance_history):
        raise ValueError("late window must fit inside the available trajectory")
    covariance = covariance_history[-args.late_window :].mean(axis=0)
    block_sites = (int(summary["length"]) // 3) ** 2
    measured_mean = (
        np.asarray(validation["mean_operators_per_block_site"], dtype=np.float64)
        * block_sites
    )
    estimate = bias_newton_correction(
        measured_mean,
        covariance,
        maximum_condition_number=args.maximum_condition_number,
        maximum_correction=args.maximum_correction,
    )
    old_couplings = np.asarray(
        summary["final_renormalized_couplings"], dtype=np.float64
    )
    corrected_couplings = old_couplings - estimate.correction
    corrected_summary = dict(summary)
    corrected_summary.update(
        {
            "final_renormalized_couplings": corrected_couplings.tolist(),
            "bias_correction_source": str(validation_path),
            "bias_correction_method": "J_new=J+Cov^-1_mean; Kprime_new=Kprime-Cov^-1_mean",
            "bias_correction": estimate.correction.tolist(),
            "uncorrected_final_renormalized_couplings": old_couplings.tolist(),
        }
    )
    report = {
        "method": corrected_summary["bias_correction_method"],
        "input": str(input_dir),
        "covariance_source": str(covariance_source),
        "validation": str(validation_path),
        "late_covariance_window": args.late_window,
        "covariance_condition_number": estimate.condition_number,
        "maximum_condition_number": args.maximum_condition_number,
        "maximum_correction": args.maximum_correction,
        "measured_mean_operators": measured_mean.tolist(),
        "bias_correction": estimate.correction.tolist(),
        "bias_correction_linf": float(np.max(np.abs(estimate.correction))),
        "predicted_mean_operators": estimate.predicted_mean.tolist(),
        "old_renormalized_couplings": old_couplings.tolist(),
        "corrected_renormalized_couplings": corrected_couplings.tolist(),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps(corrected_summary, indent=2), encoding="utf-8"
    )
    (output_dir / "correction.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
