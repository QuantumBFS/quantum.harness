#!/usr/bin/env python3
"""Adaptive independent-run production CPMC grid."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import math
from pathlib import Path

from cpmc_config import load_cpmc_contract
from matlab_runner import base_config, run_wave
from parse_cpmc_results import independent_run_estimate, load_cpmc_run


def _run_point(
    bridge: Path, contract, nwalkers: int, *,
    sigma_target: float, max_runs: int = 60,
) -> dict:
    point = f"Nw{nwalkers}_pc5"
    output = bridge / "runs/matlab_cp/production" / point
    count = 0
    estimate = None
    while count < max_runs:
        wave = min(6, max_runs - count)
        configs = [
            base_config(
                bridge, contract, mode="production",
                run_id=f"{point}_r{index:03d}",
                seed=8_000_000 + nwalkers * 1000 + index,
                nwalkers=nwalkers, pc_every=5, output_dir=output,
            )
            for index in range(count, count + wave)
        ]
        run_wave(bridge, configs)
        count += wave
        runs = [
            load_cpmc_run(output / f"{point}_r{index:03d}.mat", contract)
            for index in range(count)
        ]
        estimate = independent_run_estimate(runs)
        print(
            f"production {point}: E={estimate.mean:.8f} "
            f"sigma={estimate.sigma:.6f} runs={count}",
            flush=True,
        )
        if estimate.sigma <= sigma_target:
            break
    return {
        **asdict(estimate),
        "nwalkers": nwalkers,
        "pc_every": 5,
        "max_run_fallback": estimate.sigma > sigma_target,
    }


def main() -> int:
    root = Path(__file__).resolve().parents[3]
    bridge = root / "test/pqmc_cp_bridge"
    parser = argparse.ArgumentParser()
    parser.add_argument("--bridge-root", type=Path, default=bridge)
    parser.add_argument("--sigma-target", type=float, default=0.005)
    args = parser.parse_args()
    contract = load_cpmc_contract(args.bridge_root)
    results = {
        str(nwalkers): _run_point(
            args.bridge_root, contract, nwalkers,
            sigma_target=args.sigma_target,
        )
        for nwalkers in (100, 500, 1000)
    }
    left, right = results["500"], results["1000"]
    combined = math.hypot(left["sigma"], right["sigma"])
    if abs(left["mean"] - right["mean"]) > 2.0 * combined:
        results["2000"] = _run_point(
            args.bridge_root, contract, 2000,
            sigma_target=args.sigma_target,
        )
    path = args.bridge_root / "results/production_grid.json"
    path.write_text(json.dumps({
        "schema_version": 1,
        "sigma_target": args.sigma_target,
        "points": results,
        "nwalkers_2000_triggered": "2000" in results,
    }, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
