from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Audit completed v3 repeats, decompose fixed-point variability, "
            "and construct a calibration-only pooled anchor"
        )
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--repeats", type=int, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--anchor-output", type=Path, required=True)
    parser.add_argument("--candidate-linf", type=float, default=0.002)
    parser.add_argument("--candidate-relative-l2", type=float, default=0.01)
    return parser.parse_args()


def _intersection(intervals: list[tuple[float, float]]) -> dict[str, object]:
    low = max(item[0] for item in intervals)
    high = min(item[1] for item in intervals)
    return {
        "low": low,
        "high": high,
        "exists": low <= high,
        "gap": max(0.0, low - high),
    }


def main() -> None:
    args = parse_args()
    if len(args.repeats) < 2:
        raise ValueError("at least two completed repeats are required")
    root = args.root.resolve()
    output = args.output.resolve()
    anchor_output = args.anchor_output.resolve()
    for path in (output, anchor_output):
        if path.exists():
            raise FileExistsError(f"refusing to overwrite: {path}")

    records: list[dict[str, object]] = []
    inputs: list[np.ndarray] = []
    mapped: list[np.ndarray] = []
    jacobians: list[np.ndarray] = []
    candidates: list[np.ndarray] = []
    even_intervals: list[tuple[float, float]] = []
    odd_intervals: list[tuple[float, float]] = []
    operator_names: list[str] | None = None

    for repeat in args.repeats:
        repeat_root = root / f"repeat{repeat}"
        report = json.loads(
            (repeat_root / "repeat_report.json").read_text(encoding="utf-8")
        )
        rg1 = json.loads(
            (repeat_root / "base" / "rg1" / "summary.json").read_text(
                encoding="utf-8"
            )
        )
        rg2 = json.loads(
            (repeat_root / "base" / "rg2" / "summary.json").read_text(
                encoding="utf-8"
            )
        )
        with np.load(repeat_root / "jacobian.npz") as arrays:
            jacobian = np.asarray(arrays["t_even"], dtype=np.float64)
        current_names = list(rg2["operator_names"])
        if operator_names is None:
            operator_names = current_names
        elif current_names != operator_names:
            raise ValueError("operator bases differ between repeats")

        x = np.asarray(rg2["input_couplings"], dtype=np.float64)
        y = np.asarray(rg2["final_renormalized_couplings"], dtype=np.float64)
        candidate = np.asarray(report["fixed_point_candidate"], dtype=np.float64)
        inputs.append(x)
        mapped.append(y)
        jacobians.append(jacobian)
        candidates.append(candidate)
        even = report["lambda_even_bootstrap"]
        odd = report["lambda_odd_bootstrap"]
        even_intervals.append((float(even["ci95_low"]), float(even["ci95_high"])))
        odd_intervals.append((float(odd["ci95_low"]), float(odd["ci95_high"])))
        records.append(
            {
                "repeat": repeat,
                "lambda_even": report["lambda_even"],
                "lambda_odd": report["lambda_odd"],
                "lambda_even_ci95": list(even_intervals[-1]),
                "lambda_odd_ci95": list(odd_intervals[-1]),
                "rg1_couplings": rg1["final_renormalized_couplings"],
                "rg2_couplings": rg2["final_renormalized_couplings"],
                "fixed_point_candidate": candidate.tolist(),
            }
        )

    pairwise: list[dict[str, object]] = []
    candidate_gate_pass = True
    for left in range(len(candidates)):
        for right in range(left + 1, len(candidates)):
            difference = candidates[left] - candidates[right]
            linf = float(np.max(np.abs(difference)))
            relative_l2 = float(
                np.linalg.norm(difference)
                / max(np.linalg.norm(candidates[left]), np.linalg.norm(candidates[right]))
            )
            passed = (
                linf <= args.candidate_linf
                and relative_l2 <= args.candidate_relative_l2
            )
            candidate_gate_pass = candidate_gate_pass and passed
            pairwise.append(
                {
                    "left_repeat": args.repeats[left],
                    "right_repeat": args.repeats[right],
                    "candidate_linf": linf,
                    "candidate_relative_l2": relative_l2,
                    "maximum_component_index_one_based": int(
                        np.argmax(np.abs(difference)) + 1
                    ),
                    "status": "PASS" if passed else "FAIL",
                }
            )

    even_intersection = _intersection(even_intervals)
    odd_intersection = _intersection(odd_intervals)

    # Cross the two observed maps and Jacobians.  If changing the map while
    # holding T fixed moves the root much more than changing T while holding
    # the map fixed, the stochastic RG map is the dominant source.
    crossed: list[dict[str, object]] = []
    crossed_candidates: dict[tuple[int, int], np.ndarray] = {}
    for jacobian_index, jacobian in enumerate(jacobians):
        for map_index, (x, y) in enumerate(zip(inputs, mapped)):
            candidate = x + np.linalg.solve(np.eye(x.size) - jacobian, y - x)
            crossed_candidates[(jacobian_index, map_index)] = candidate
            crossed.append(
                {
                    "jacobian_repeat": args.repeats[jacobian_index],
                    "map_repeat": args.repeats[map_index],
                    "candidate_couplings": candidate.tolist(),
                }
            )
    map_effects: list[float] = []
    for jacobian_index in range(len(jacobians)):
        for left in range(len(inputs)):
            for right in range(left + 1, len(inputs)):
                map_effects.append(
                    float(
                        np.max(
                            np.abs(
                                crossed_candidates[(jacobian_index, left)]
                                - crossed_candidates[(jacobian_index, right)]
                            )
                        )
                    )
                )
    jacobian_effects: list[float] = []
    for map_index in range(len(inputs)):
        for left in range(len(jacobians)):
            for right in range(left + 1, len(jacobians)):
                jacobian_effects.append(
                    float(
                        np.max(
                            np.abs(
                                crossed_candidates[(left, map_index)]
                                - crossed_candidates[(right, map_index)]
                            )
                        )
                    )
                )

    mean_input = np.mean(inputs, axis=0)
    mean_mapped = np.mean(mapped, axis=0)
    mean_jacobian = np.mean(jacobians, axis=0)
    system = np.eye(mean_input.size) - mean_jacobian
    pooled_anchor = mean_input + np.linalg.solve(
        system, mean_mapped - mean_input
    )
    singular_values = np.linalg.svd(system, compute_uv=False)

    gates = {
        "candidate_pairwise": candidate_gate_pass,
        "even_ci_common_intersection": bool(even_intersection["exists"]),
        "odd_ci_common_intersection": bool(odd_intersection["exists"]),
    }
    all_pass = all(gates.values())
    result = {
        "status": "PASS" if all_pass else "EARLY_STOP_FAIL",
        "method": "preregistered_v3_cross_repeat_audit",
        "parameter_update_performed": False,
        "completed_repeats": args.repeats,
        "records": records,
        "pairwise_candidate_checks": pairwise,
        "even_ci_intersection": even_intersection,
        "odd_ci_intersection": odd_intersection,
        "gates": gates,
        "root_variability_decomposition": {
            "crossed_candidates": crossed,
            "maximum_map_effect_linf": max(map_effects),
            "maximum_jacobian_effect_linf": max(jacobian_effects),
            "dominant_source": (
                "stochastic_rg_map"
                if max(map_effects) > max(jacobian_effects)
                else "jacobian"
            ),
        },
        "decision": (
            "do_not_run_repeat3_v3_gates_already_impossible"
            if not all_pass
            else "continue_preregistered_v3"
        ),
    }
    anchor = {
        "status": "CALIBRATION_ONLY_NOT_FORMAL_RESULT",
        "method": "pooled_two_map_two_jacobian_newton_anchor",
        "source_repeats": args.repeats,
        "source_audit": str(output),
        "allowed_use": "v4_anchor_calibration_before_new_formal_seeds",
        "forbidden_use": "v3_result_or_independent_validation",
        "operator_names": operator_names,
        "mean_linearization_point": mean_input.tolist(),
        "mean_mapped_couplings": mean_mapped.tolist(),
        "condition_number_I_minus_mean_T": float(np.linalg.cond(system)),
        "singular_values_I_minus_mean_T": singular_values.tolist(),
        "candidate_couplings": pooled_anchor.tolist(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    anchor_output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    anchor_output.write_text(json.dumps(anchor, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(json.dumps(anchor, indent=2))


if __name__ == "__main__":
    main()
