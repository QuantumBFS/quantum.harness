from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from vmcrg_ref import covariance_matrices_from_sums, estimate_rg_jacobian


EVEN_SIZE = 13
ODD_SIZE = 5
TOTAL_SIZE = EVEN_SIZE + ODD_SIZE


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Hierarchical bootstrap across independent RG2 maps and MC runs"
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--bootstrap", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=202617901)
    return parser.parse_args()


def _distribution(values: np.ndarray) -> dict[str, float]:
    return {
        "mean": float(values.mean()),
        "standard_error": float(values.std(ddof=1)),
        "ci95_low": float(np.quantile(values, 0.025)),
        "ci95_high": float(np.quantile(values, 0.975)),
    }


def _load_repeat(root: Path, repeat: int) -> dict[str, object]:
    directory = root / f"repeat{repeat}"
    report_path = directory / "repeat_report.json"
    jacobian_path = directory / "jacobian.json"
    arrays_path = directory / "jacobian.npz"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    jacobian = json.loads(jacobian_path.read_text(encoding="utf-8"))
    if report.get("status") != "PASS":
        raise ValueError(f"repeat {repeat} did not pass its preregistered gate")
    if jacobian.get("status") != "NUMERICALLY_STABLE":
        raise ValueError(f"repeat {repeat} Jacobian is not numerically stable")
    arrays = np.load(arrays_path, allow_pickle=False)
    data = {
        "repeat": repeat,
        "measurements": int(jacobian["measurements_per_run"]),
        "micro": np.asarray(arrays["run_micro_sums"], dtype=np.float64),
        "block": np.asarray(arrays["run_block_sums"], dtype=np.float64),
        "cross": np.asarray(arrays["run_cross_sums"], dtype=np.float64),
        "outer": np.asarray(arrays["run_block_outer_sums"], dtype=np.float64),
        "lambda_even": float(jacobian["even"]["leading_eigenvalue"]),
        "lambda_odd": float(jacobian["odd"]["leading_eigenvalue"]),
    }
    arrays.close()
    run_count = data["micro"].shape[0]
    if run_count < 3:
        raise ValueError(f"repeat {repeat} has fewer than three runs")
    if data["micro"].shape != (run_count, TOTAL_SIZE):
        raise ValueError(f"repeat {repeat} has invalid first-moment dimensions")
    expected_second = (run_count, TOTAL_SIZE, TOTAL_SIZE)
    if data["cross"].shape != expected_second or data["outer"].shape != expected_second:
        raise ValueError(f"repeat {repeat} has invalid second-moment dimensions")
    if data["block"].shape != (run_count, TOTAL_SIZE):
        raise ValueError(f"repeat {repeat} has invalid block-moment dimensions")
    return data


def _estimate(selected: list[tuple[dict[str, object], np.ndarray]]) -> tuple[float, float]:
    measurements = {int(item["measurements"]) for item, _ in selected}
    if len(measurements) != 1:
        raise ValueError("all repeats must use the same measurements per run")
    micro = np.concatenate([item["micro"][indices] for item, indices in selected])
    block = np.concatenate([item["block"][indices] for item, indices in selected])
    cross = np.concatenate([item["cross"][indices] for item, indices in selected])
    outer = np.concatenate([item["outer"][indices] for item, indices in selected])
    sample_count = next(iter(measurements)) * micro.shape[0]
    a, b = covariance_matrices_from_sums(
        sample_count=sample_count,
        micro_sum=micro.sum(axis=0),
        block_sum=block.sum(axis=0),
        micro_block_sum=cross.sum(axis=0),
        block_outer_sum=outer.sum(axis=0),
    )
    even = estimate_rg_jacobian(a[:EVEN_SIZE, :EVEN_SIZE], b[:EVEN_SIZE, :EVEN_SIZE])
    odd = estimate_rg_jacobian(a[EVEN_SIZE:, EVEN_SIZE:], b[EVEN_SIZE:, EVEN_SIZE:])
    return even.leading_eigenvalue, odd.leading_eigenvalue


def _bootstrap(
    maps: list[dict[str, object]],
    *,
    replicates: int,
    rng: np.random.Generator,
    resample_maps: bool,
    resample_runs: bool,
) -> tuple[np.ndarray, np.ndarray, int]:
    even_values: list[float] = []
    odd_values: list[float] = []
    invalid = 0
    map_count = len(maps)
    for _ in range(replicates):
        map_indices = (
            rng.integers(0, map_count, size=map_count)
            if resample_maps
            else np.arange(map_count)
        )
        selected: list[tuple[dict[str, object], np.ndarray]] = []
        for map_index in map_indices:
            item = maps[int(map_index)]
            run_count = item["micro"].shape[0]
            run_indices = (
                rng.integers(0, run_count, size=run_count)
                if resample_runs
                else np.arange(run_count)
            )
            selected.append((item, run_indices))
        try:
            even, odd = _estimate(selected)
        except (ValueError, np.linalg.LinAlgError):
            invalid += 1
            continue
        even_values.append(even)
        odd_values.append(odd)
    return np.asarray(even_values), np.asarray(odd_values), invalid


def assess(root: Path, repeats: list[int], bootstrap: int, seed: int) -> dict[str, object]:
    if repeats != [1, 2, 3]:
        raise ValueError("formal protocol requires exactly repeats 1, 2, and 3")
    if bootstrap < 100:
        raise ValueError("at least 100 bootstrap replicates are required")
    maps = [_load_repeat(root, repeat) for repeat in repeats]
    point = _estimate(
        [(item, np.arange(item["micro"].shape[0])) for item in maps]
    )
    full_rng, run_rng, map_rng = [
        np.random.default_rng(sequence)
        for sequence in np.random.SeedSequence(seed).spawn(3)
    ]
    full_even, full_odd, full_invalid = _bootstrap(
        maps,
        replicates=bootstrap,
        rng=full_rng,
        resample_maps=True,
        resample_runs=True,
    )
    run_even, run_odd, run_invalid = _bootstrap(
        maps,
        replicates=bootstrap,
        rng=run_rng,
        resample_maps=False,
        resample_runs=True,
    )
    map_even, map_odd, map_invalid = _bootstrap(
        maps,
        replicates=bootstrap,
        rng=map_rng,
        resample_maps=True,
        resample_runs=False,
    )
    arrays = (full_even, full_odd, run_even, run_odd, map_even, map_odd)
    if any(values.size < 2 for values in arrays):
        raise RuntimeError("bootstrap produced fewer than two valid estimates")

    paper = {"even": 3.045, "odd": 7.858}
    full = {"even": _distribution(full_even), "odd": _distribution(full_odd)}
    inside = {
        parity: bool(
            full[parity]["ci95_low"] <= paper[parity] <= full[parity]["ci95_high"]
        )
        for parity in ("even", "odd")
    }
    invalid = {
        "hierarchical": full_invalid,
        "run_only": run_invalid,
        "map_only": map_invalid,
    }
    stable = all(value == 0 for value in invalid.values())
    status = (
        "PASS_PAPER_VALUES_INSIDE_POOLED_HIERARCHICAL_CI95"
        if stable and all(inside.values())
        else "FAIL_POOLED_HIERARCHICAL_ACCEPTANCE_GATE"
    )
    return {
        "material_passport": {
            "schema": 9,
            "artifact_type": "reproducibility_validation_report",
            "verification_status": "VERIFIED",
        },
        "status": status,
        "scope": "three_independent_direct_paper_RG2_maps",
        "root": str(root.resolve()),
        "repeats": repeats,
        "method": (
            "hierarchical bootstrap resampling RG2 maps then independent MC runs; "
            "run-only and map-only distributions are non-additive sensitivity components"
        ),
        "bootstrap_replicates": bootstrap,
        "bootstrap_seed": seed,
        "invalid_replicates": invalid,
        "point_estimate_from_all_maps_and_runs": {
            "lambda_even": point[0],
            "lambda_odd": point[1],
        },
        "per_map_point_estimates": [
            {
                "repeat": item["repeat"],
                "lambda_even": item["lambda_even"],
                "lambda_odd": item["lambda_odd"],
            }
            for item in maps
        ],
        "hierarchical_uncertainty": full,
        "run_only_uncertainty": {
            "even": _distribution(run_even),
            "odd": _distribution(run_odd),
        },
        "map_only_uncertainty": {
            "even": _distribution(map_even),
            "odd": _distribution(map_odd),
        },
        "paper_L45_biased_values": paper,
        "paper_values_inside_hierarchical_ci95": inside,
        "all_acceptance_gates_pass": bool(stable and all(inside.values())),
    }


def main() -> None:
    args = parse_args()
    root = args.root.resolve()
    output = (args.output or root / "pooled_assessment.json").resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite pooled assessment: {output}")
    report = assess(root, [1, 2, 3], args.bootstrap, args.seed)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
