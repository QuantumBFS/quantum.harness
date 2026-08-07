from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from vmcrg_ref import covariance_matrices_from_sums, estimate_rg_jacobian


RUN_KEYS = (
    "run_micro_sums",
    "run_block_sums",
    "run_cross_sums",
    "run_block_outer_sums",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interim audit of two v5 Table-I repeats")
    parser.add_argument("--inputs", type=Path, nargs=2, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bootstrap", type=int, default=2000)
    parser.add_argument("--bootstrap-seed", type=int, default=202611301)
    parser.add_argument("--permutations", type=int, default=10000)
    parser.add_argument("--permutation-seed", type=int, default=202611302)
    return parser.parse_args()


def distribution(values: np.ndarray) -> dict[str, float]:
    return {
        "mean": float(values.mean()),
        "standard_error": float(values.std(ddof=1)),
        "ci95_low": float(np.quantile(values, 0.025)),
        "ci95_high": float(np.quantile(values, 0.975)),
    }


def main() -> None:
    args = parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite: {output}")

    reports = [json.loads(path.resolve().read_text(encoding="utf-8")) for path in args.inputs]
    if any(report.get("status") != "NUMERICALLY_STABLE" for report in reports):
        raise ValueError("both Jacobian reports must be NUMERICALLY_STABLE")
    if reports[0]["input"] != reports[1]["input"]:
        raise ValueError("the repeats must use the same frozen input")
    runs = int(reports[0]["independent_runs"])
    measurements = int(reports[0]["measurements_per_run"])
    if any(int(report["independent_runs"]) != runs for report in reports):
        raise ValueError("the repeats must have equal run counts")
    if any(int(report["measurements_per_run"]) != measurements for report in reports):
        raise ValueError("the repeats must have equal measurement counts")

    loaded = [np.load(path.resolve().with_suffix(".npz")) for path in args.inputs]
    try:
        data = {key: np.concatenate([arrays[key] for arrays in loaded], axis=0) for key in RUN_KEYS}
    finally:
        for arrays in loaded:
            arrays.close()

    def eigenvalues(selection: np.ndarray) -> np.ndarray:
        a, b = covariance_matrices_from_sums(
            measurements * selection.size,
            data["run_micro_sums"][selection].sum(axis=0),
            data["run_block_sums"][selection].sum(axis=0),
            data["run_cross_sums"][selection].sum(axis=0),
            data["run_block_outer_sums"][selection].sum(axis=0),
        )
        return np.asarray(
            [
                estimate_rg_jacobian(a[:13, :13], b[:13, :13]).leading_eigenvalue,
                estimate_rg_jacobian(a[13:, 13:], b[13:, 13:]).leading_eigenvalue,
            ]
        )

    total_runs = 2 * runs
    all_indices = np.arange(total_runs)
    groups = (np.arange(runs), np.arange(runs, total_runs))
    batch_values = np.asarray([eigenvalues(group) for group in groups])
    pooled = eigenvalues(all_indices)

    bootstrap_rng = np.random.default_rng(args.bootstrap_seed)
    bootstrap_values = np.asarray(
        [
            eigenvalues(bootstrap_rng.integers(0, total_runs, size=total_runs))
            for _ in range(args.bootstrap)
        ]
    )

    observed_difference = np.abs(batch_values[0] - batch_values[1])
    permutation_rng = np.random.default_rng(args.permutation_seed)
    null_differences = np.empty((args.permutations, 2), dtype=np.float64)
    for sample in range(args.permutations):
        shuffled = permutation_rng.permutation(all_indices)
        null_differences[sample] = np.abs(
            eigenvalues(shuffled[:runs]) - eigenvalues(shuffled[runs:])
        )

    paper = np.asarray([3.045, 7.858])
    blocks: dict[str, object] = {}
    systematic = False
    for index, parity in enumerate(("even", "odd")):
        summary = distribution(bootstrap_values[:, index])
        p_value = float(
            (np.count_nonzero(null_differences[:, index] >= observed_difference[index]) + 1)
            / (args.permutations + 1)
        )
        paper_in_ci = bool(
            summary["ci95_low"] <= paper[index] <= summary["ci95_high"]
        )
        same_direction = bool(np.all(batch_values[:, index] > paper[index]))
        upward_discrepancy = bool(
            same_direction and summary["ci95_low"] > paper[index]
        )
        systematic = systematic or upward_discrepancy
        blocks[parity] = {
            "batch_eigenvalues": batch_values[:, index].tolist(),
            "pooled_eigenvalue": float(pooled[index]),
            "pooled_bootstrap": summary,
            "paper_L45_biased_value": float(paper[index]),
            "paper_value_in_pooled_ci": paper_in_ci,
            "observed_batch_difference": float(observed_difference[index]),
            "batch_permutation_p_value": p_value,
            "batch_effect_detected_at_0.05": p_value <= 0.05,
            "same_direction_upward": same_direction,
            "systematic_upward_discrepancy_indicated": upward_discrepancy,
        }

    result = {
        "status": (
            "SYSTEMATIC_UPWARD_DISCREPANCY_INDICATED"
            if systematic
            else "NO_SYSTEMATIC_DISCREPANCY_DETECTED"
        ),
        "scope": "interim_two_repeat_diagnostic_not_final_Table_I_result",
        "input": reports[0]["input"],
        "reports": [str(path.resolve()) for path in args.inputs],
        "runs_per_repeat": runs,
        "measurements_per_run": measurements,
        "pooled_runs": total_runs,
        "bootstrap_replicates": args.bootstrap,
        "bootstrap_seed": args.bootstrap_seed,
        "permutations": args.permutations,
        "permutation_seed": args.permutation_seed,
        "blocks": blocks,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
