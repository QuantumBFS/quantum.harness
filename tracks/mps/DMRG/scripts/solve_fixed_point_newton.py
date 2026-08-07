from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from vmcrg_ref.fixed_point import newton_fixed_point_candidate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Construct a 13-dimensional VMCRG fixed-point Newton candidate"
    )
    parser.add_argument("--map-input", type=Path, required=True)
    parser.add_argument("--jacobian", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--maximum-condition-number", type=float, default=1.0e6)
    parser.add_argument("--maximum-correction", type=float, default=0.05)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    map_dir = args.map_input.resolve()
    jacobian_path = args.jacobian.resolve()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite fixed-point candidate: {output}")
    summary = json.loads((map_dir / "summary.json").read_text(encoding="utf-8"))
    input_couplings = np.asarray(summary["input_couplings"], dtype=np.float64)
    mapped_couplings = np.asarray(
        summary["final_renormalized_couplings"], dtype=np.float64
    )
    with np.load(jacobian_path) as arrays:
        jacobian = np.asarray(arrays["t_even"], dtype=np.float64)
    estimate = newton_fixed_point_candidate(
        input_couplings,
        mapped_couplings,
        jacobian,
        maximum_condition_number=args.maximum_condition_number,
        maximum_correction=args.maximum_correction,
    )
    result = {
        "method": "unregularized_newton_for_R_of_K_minus_K",
        "equation": "(I-T) delta = R(K)-K; K_candidate = K+delta",
        "map_input": str(map_dir),
        "jacobian": str(jacobian_path),
        "operator_names": summary["operator_names"],
        "linearization_point": input_couplings.tolist(),
        "mapped_couplings": mapped_couplings.tolist(),
        "map_residual": estimate.map_residual.tolist(),
        "map_residual_l2": float(np.linalg.norm(estimate.map_residual)),
        "map_residual_linf": float(np.max(np.abs(estimate.map_residual))),
        "newton_correction": estimate.correction.tolist(),
        "newton_correction_l2": float(np.linalg.norm(estimate.correction)),
        "newton_correction_linf": float(np.max(np.abs(estimate.correction))),
        "candidate_couplings": estimate.candidate.tolist(),
        "condition_number_I_minus_T": estimate.condition_number,
        "singular_values_I_minus_T": estimate.singular_values.tolist(),
        "predicted_residual": estimate.predicted_residual.tolist(),
        "predicted_residual_l2": float(np.linalg.norm(estimate.predicted_residual)),
        "maximum_condition_number": args.maximum_condition_number,
        "maximum_correction": args.maximum_correction,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
