#!/usr/bin/env python3
"""Issue #28 N0 exact blocking oracle entry point."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vmcrg_ref.artifacts import atomic_write_json, atomic_write_npz, sha256_file
from vmcrg_ref.exact_oracle import (
    compare_small_neural_gradients,
    enumerate_rectangular_blocking,
    exact_handoff_energy,
    exact_local_energy_delta,
    exact_objective,
    exact_parameter_gradient,
    target_distribution_distances,
)
from vmcrg_ref.issue28_protocol import load_issue28_protocol


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="运行 Issue #28 N0 精确阻塞 oracle")
    parser.add_argument(
        "--protocol",
        type=Path,
        default=Path("config/issue28_n0_v1.json"),
        help="N0 oracle 配置",
    )
    parser.add_argument("--output", type=Path, required=True, help="全新输出目录")
    return parser


def validate_n0_config(config: dict[str, Any]) -> None:
    if config.get("protocol") != "issue28_n0_exact_oracle_v1":
        raise ValueError("unexpected N0 oracle protocol")
    if config.get("umbrella") != "config/issue28_easy_v1.json":
        raise ValueError("N0 umbrella protocol path changed")
    if config.get("blocking_oracle") != {
        "rows": 3,
        "cols": 6,
        "block_size": 3,
        "coupling": 0.436,
    }:
        raise ValueError("N0 blocking oracle geometry is not frozen")
    if config.get("identity_oracle") != {
        "length": 3,
        "radius": 1,
        "hidden": 3,
        "seed": 2026283001,
    }:
        raise ValueError("N0 identity oracle setup changed")
    if config.get("jax") != {
        "platform": "cpu",
        "enable_x64": True,
        "mc_sample_count": 100000,
        "install": "make install jax EXTRA=cpu",
    }:
        raise ValueError("N0 JAX platform or precision contract changed")
    if config.get("tolerances") != {
        "probability_sum": 1e-14,
        "objective_gradient": 1e-9,
        "jax_vs_analytic": 1e-9,
        "jax_vs_finite_difference": 1e-6,
        "local_delta": 1e-10,
        "monte_carlo_family_alpha": 0.05,
    }:
        raise ValueError("N0 deterministic/statistical tolerances changed")


def run_exact_oracle(config_path: str | Path, output: str | Path) -> dict[str, Any]:
    config_file = Path(config_path)
    config = json.loads(config_file.read_text(encoding="ascii"))
    validate_n0_config(config)
    umbrella = ROOT / config["umbrella"]
    umbrella_protocol = load_issue28_protocol(umbrella)
    blocking = config["blocking_oracle"]
    root = Path(output)
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"refusing to overwrite nonempty N0 output: {root}")
    root.mkdir(parents=True, exist_ok=True)

    result = enumerate_rectangular_blocking(
        int(blocking["rows"]),
        int(blocking["cols"]),
        int(blocking["block_size"]),
        float(blocking["coupling"]),
    )
    target = np.full(
        result.coarse_state_count,
        1.0 / result.coarse_state_count,
        dtype=np.float64,
    )
    zero_bias_objective = exact_objective(
        result,
        np.zeros(result.coarse_state_count, dtype=np.float64),
        target,
    )
    theta = np.asarray([0.1], dtype=np.float64)
    features = result.coarse_nn[:, None].astype(np.float64)
    bias = features @ theta
    objective = exact_objective(result, bias, target)
    gradient = exact_parameter_gradient(result, features, theta, target)
    blocking_report = {
        **result.to_dict(),
        "target_probability": target.tolist(),
        "zero_bias_objective": zero_bias_objective,
        "synthetic_bias": bias.tolist(),
        "synthetic_objective": objective,
        "target_distances_at_zero_bias": target_distribution_distances(
            result.coarse_probability,
            target,
        ),
        "handoff_sign_check": bool(
            np.array_equal(exact_handoff_energy(bias), -bias)
        ),
    }
    atomic_write_json(root / "exact_blocking.json", blocking_report)
    atomic_write_npz(
        root / "coarse_arrays.npz",
        {
            "coarse_states": result.coarse_states,
            "coarse_probability": result.coarse_probability,
            "coarse_nn": result.coarse_nn,
            "target_probability": target,
        },
    )
    local_spins = np.asarray(
        [[1, -1, 1, 1, -1, 1], [-1, 1, -1, 1, 1, -1], [1, 1, -1, -1, 1, -1]],
        dtype=np.int8,
    )
    local_before = exact_local_energy_delta(
        local_spins, 1, 2, float(blocking["coupling"]), direct_only=True
    )
    local_delta = exact_local_energy_delta(
        local_spins, 1, 2, float(blocking["coupling"])
    )
    trial = local_spins.copy()
    trial[1, 2] *= -1
    local_direct = exact_local_energy_delta(
        trial, 1, 2, float(blocking["coupling"]), direct_only=True
    ) - local_before
    gradient_report = {
        "features": features.tolist(),
        "parameters": theta.tolist(),
        "analytic_exact_gradient": gradient.tolist(),
        "local_delta": local_delta,
        "direct_local_delta": local_direct,
        "local_delta_absolute_error": abs(local_delta - local_direct),
        "status": "PASS" if abs(local_delta - local_direct) <= 1e-12 else "FAIL",
    }
    atomic_write_json(root / "gradient.json", gradient_report)
    identity = config["identity_oracle"]
    neural_gradient = compare_small_neural_gradients(
        int(identity["length"]),
        int(identity["radius"]),
        int(identity["hidden"]),
        int(identity["seed"]),
    )
    tolerances = config["tolerances"]
    neural_gradient["status"] = (
        "PASS"
        if neural_gradient["jax_vs_analytic_linf"]
        <= float(tolerances["jax_vs_analytic"])
        and neural_gradient["jax_vs_finite_difference_linf"]
        <= float(tolerances["jax_vs_finite_difference"])
        and neural_gradient["mc_family_alpha"]
        == float(tolerances["monte_carlo_family_alpha"])
        and neural_gradient["exact_vs_mc_all_z_below"]
        else "FAIL"
    )
    atomic_write_json(root / "neural_gradient.json", neural_gradient)
    artifact_names = (
        "exact_blocking.json",
        "coarse_arrays.npz",
        "gradient.json",
        "neural_gradient.json",
    )
    manifest = {
        "schema_version": 1,
        "stage": "N0",
        "scope": "EXACT_BLOCKING_ORACLE",
        "classification": (
            "CORRECTNESS_FAILURE"
            if gradient_report["status"] != "PASS"
            or neural_gradient["status"] != "PASS"
            else "EASY_GOAL_SUCCESS"
        ),
        "protocol_sha256": umbrella_protocol.protocol_sha256,
        "n0_config_sha256": sha256_file(config_file),
        "microstate_count": result.microstate_count,
        "coarse_state_count": result.coarse_state_count,
        "artifacts": {name: sha256_file(root / name) for name in artifact_names},
    }
    atomic_write_json(root / "manifest.json", manifest)
    print(
        "N0精确 oracle 完成 "
        f"微观态={result.microstate_count} 粗态={result.coarse_state_count} "
        f"分类={manifest['classification']}",
        flush=True,
    )
    return {
        **manifest,
        "blocking": blocking_report,
        "gradient": gradient_report,
        "neural_gradient": neural_gradient,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_exact_oracle(args.protocol, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
