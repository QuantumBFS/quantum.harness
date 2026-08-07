#!/usr/bin/env python3
"""Adaptive independent-system grid for fixed-horizon CPMC."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from cpmc_config import load_cpmc_contract
from matlab_runner import base_config, run_wave
from parse_cpmc_results import independent_run_estimate, load_cpmc_run


def main() -> int:
    root = Path(__file__).resolve().parents[3]
    bridge = root / "test/pqmc_cp_bridge"
    parser = argparse.ArgumentParser()
    parser.add_argument("--bridge-root", type=Path, default=bridge)
    parser.add_argument("--wave-size", type=int, default=20)
    parser.add_argument("--max-systems", type=int, default=100)
    parser.add_argument("--sigma-target", type=float, default=0.005)
    args = parser.parse_args()
    contract = load_cpmc_contract(args.bridge_root)
    points = [(100, 5), (500, 5), (1000, 5), (1000, 20), (1000, 40)]
    output_root = args.bridge_root / "runs/matlab_cp/fixed_horizon"
    results = {}
    for nwalkers, pc_every in points:
        point = f"Nw{nwalkers}_pc{pc_every}"
        output = output_root / point
        count = 0
        estimate = None
        while count < args.max_systems:
            wave = min(args.wave_size, args.max_systems - count)
            configs = [
                base_config(
                    args.bridge_root, contract,
                    mode="fixed_horizon",
                    run_id=f"{point}_r{index:03d}",
                    seed=4_000_000 + nwalkers * 1000 + pc_every * 100 + index,
                    nwalkers=nwalkers, pc_every=pc_every,
                    output_dir=output,
                )
                for index in range(count, count + wave)
            ]
            run_wave(args.bridge_root, configs)
            count += wave
            runs = [
                load_cpmc_run(
                    output / f"{point}_r{index:03d}.mat", contract
                )
                for index in range(count)
            ]
            estimate = independent_run_estimate(runs)
            print(
                f"fixed {point}: E={estimate.mean:.8f} "
                f"sigma={estimate.sigma:.6f} systems={count}",
                flush=True,
            )
            if estimate.sigma <= args.sigma_target:
                break
        results[point] = {
            **asdict(estimate),
            "nwalkers": nwalkers,
            "pc_every": pc_every,
            "max_system_fallback": estimate.sigma > args.sigma_target,
        }
    path = args.bridge_root / "results/fixed_horizon_grid.json"
    path.write_text(json.dumps({
        "schema_version": 1,
        "sigma_target": args.sigma_target,
        "points": results,
    }, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
