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
    parser = argparse.ArgumentParser(
        description="Permutation diagnosis of three Jacobian master-seed batches"
    )
    parser.add_argument("--inputs", type=Path, nargs=3, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--permutations", type=int, default=10000)
    parser.add_argument("--permutation-seed", type=int, required=True)
    parser.add_argument("--alpha", type=float, default=0.05)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite: {output}")
    reports = [json.loads(path.resolve().read_text(encoding="utf-8")) for path in args.inputs]
    if any(report.get("status") != "NUMERICALLY_STABLE" for report in reports):
        raise ValueError("all Jacobian reports must be NUMERICALLY_STABLE")
    if len({report["input"] for report in reports}) != 1:
        raise ValueError("all batches must use the same frozen input")
    runs = int(reports[0]["independent_runs"])
    measurements = int(reports[0]["measurements_per_run"])
    if any(int(report["independent_runs"]) != runs for report in reports):
        raise ValueError("all batches must contain the same number of runs")
    if any(int(report["measurements_per_run"]) != measurements for report in reports):
        raise ValueError("all batches must use the same measurement count")

    loaded = [np.load(path.resolve().with_suffix(".npz")) for path in args.inputs]
    try:
        data = {key: np.concatenate([arrays[key] for arrays in loaded], axis=0) for key in RUN_KEYS}
    finally:
        for arrays in loaded:
            arrays.close()

    def eigenvalues(selection: np.ndarray) -> tuple[float, float]:
        a, b = covariance_matrices_from_sums(
            measurements * selection.size,
            data["run_micro_sums"][selection].sum(axis=0),
            data["run_block_sums"][selection].sum(axis=0),
            data["run_cross_sums"][selection].sum(axis=0),
            data["run_block_outer_sums"][selection].sum(axis=0),
        )
        even = estimate_rg_jacobian(a[:13, :13], b[:13, :13]).leading_eigenvalue
        odd = estimate_rg_jacobian(a[13:, 13:], b[13:, 13:]).leading_eigenvalue
        return even, odd

    groups = [np.arange(index * runs, (index + 1) * runs) for index in range(3)]
    observed_values = np.asarray([eigenvalues(group) for group in groups])
    observed_range = observed_values.max(axis=0) - observed_values.min(axis=0)
    rng = np.random.default_rng(args.permutation_seed)
    null_ranges = np.empty((args.permutations, 2), dtype=np.float64)
    all_indices = np.arange(3 * runs)
    for sample in range(args.permutations):
        shuffled = rng.permutation(all_indices)
        values = np.asarray(
            [eigenvalues(shuffled[index * runs : (index + 1) * runs]) for index in range(3)]
        )
        null_ranges[sample] = values.max(axis=0) - values.min(axis=0)

    blocks: dict[str, object] = {}
    any_effect = False
    for index, parity in enumerate(("even", "odd")):
        p_value = float(
            (np.count_nonzero(null_ranges[:, index] >= observed_range[index]) + 1)
            / (args.permutations + 1)
        )
        detected = p_value <= args.alpha
        any_effect = any_effect or detected
        blocks[parity] = {
            "batch_eigenvalues": observed_values[:, index].tolist(),
            "observed_range": float(observed_range[index]),
            "permutation_p_value": p_value,
            "alpha": args.alpha,
            "null_range_median": float(np.median(null_ranges[:, index])),
            "null_range_q95": float(np.quantile(null_ranges[:, index], 0.95)),
            "batch_effect_detected": detected,
        }
    result = {
        "status": "BATCH_EFFECT_DETECTED" if any_effect else "NO_BATCH_EFFECT_DETECTED",
        "scope": "diagnostic_only_not_formal_Table_I_result",
        "method": "three_equal_batch_run_label_permutation_test",
        "input": reports[0]["input"],
        "reports": [str(path.resolve()) for path in args.inputs],
        "runs_per_batch": runs,
        "measurements_per_run": measurements,
        "permutations": args.permutations,
        "permutation_seed": args.permutation_seed,
        "blocks": blocks,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
