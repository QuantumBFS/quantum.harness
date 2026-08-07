#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import resource
import statistics
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vmcrg_ref.ising import IsingLattice
from vmcrg_ref.mps_patch import PatchMPS
from vmcrg_ref.mps_sampler import MPSBiasedMetropolis
from vmcrg_ref.mps_vmcrg import MPSVMCRGOptimizer
from vmcrg_ref.operators import EVEN_SHAPES, OperatorBasis
from vmcrg_ref.patch_table import PatchEnergyCache, PatchLookupTable, enumerate_patches


def median_seconds(function, repeats: int) -> float:
    timings = []
    for _ in range(repeats):
        started = time.perf_counter()
        function()
        timings.append(time.perf_counter() - started)
    return float(statistics.median(timings))


def benchmark_chi(chi: int, seed: int) -> dict[str, float | int]:
    rng = np.random.default_rng(seed)
    model = PatchMPS.random(chi=chi, seed=seed + 1)
    patches = enumerate_patches()
    pattern_ids = rng.integers(0, 512, size=10000)
    lookup = PatchLookupTable.from_model(model)
    coarse_spins = rng.choice(np.array([-1, 1], dtype=np.int8), size=(15, 15))
    cache = PatchEnergyCache(coarse_spins, lookup)
    proposal_sites = rng.integers(0, 15, size=(5000, 2))

    direct_seconds = median_seconds(lambda: model.symmetric_values(patches), 9)
    lookup_seconds = median_seconds(lambda: lookup.values[pattern_ids], 21)
    full_seconds = median_seconds(lambda: cache.full_energy(coarse_spins), 31)

    def proposals() -> None:
        total = 0.0
        for x, y in proposal_sites:
            total += cache.proposal(int(x), int(y)).delta_energy
        if not np.isfinite(total):
            raise FloatingPointError("non-finite proposal benchmark")

    incremental_seconds = median_seconds(proposals, 7)

    couplings = np.zeros(len(EVEN_SHAPES))
    couplings[0] = 0.436
    initial = IsingLattice.random(45, np.random.default_rng(seed + 2)).spins.copy()
    micro_basis = OperatorBasis(45, EVEN_SHAPES)
    block_basis = OperatorBasis(15, EVEN_SHAPES)
    sampler = MPSBiasedMetropolis(
        IsingLattice(initial),
        couplings,
        np.zeros(len(EVEN_SHAPES)),
        0.1,
        lookup,
        np.random.default_rng(seed + 3),
        EVEN_SHAPES,
        compiled=True,
        micro_basis=micro_basis,
        block_basis=block_basis,
    )
    sampler.run_sweeps(1)
    sweep_seconds = median_seconds(lambda: sampler.run_sweeps(1), 7)

    optimizer = MPSVMCRGOptimizer(
        length=15,
        couplings=couplings,
        linear_bias=np.zeros(len(EVEN_SHAPES)),
        model=model.copy(),
        shapes=EVEN_SHAPES,
        walkers=2,
        seed=seed + 4,
        compiled=True,
        parallel_walkers=False,
    )
    optimizer.run(
        steps=1,
        sweeps_per_step=1,
        alpha_learning_rate=0.001,
        core_learning_rate=0.0001,
        canonicalize_every=0,
        cache_check_every=0,
    )
    iteration_seconds = median_seconds(
        lambda: MPSVMCRGOptimizer(
            length=15,
            couplings=couplings,
            linear_bias=np.zeros(len(EVEN_SHAPES)),
            model=model.copy(),
            shapes=EVEN_SHAPES,
            walkers=2,
            seed=seed + 5,
            compiled=True,
            parallel_walkers=False,
        ).run(
            steps=1,
            sweeps_per_step=1,
            alpha_learning_rate=0.001,
            core_learning_rate=0.0001,
            canonicalize_every=0,
            cache_check_every=0,
        ),
        3,
    )
    return {
        "chi": chi,
        "parameter_count": model.parameter_count,
        "parameter_bytes": sum(core.nbytes for core in model.cores),
        "lookup_bytes": lookup.values.nbytes,
        "direct_512_seconds": direct_seconds,
        "direct_per_patch_seconds": direct_seconds / 512.0,
        "lookup_10000_seconds": lookup_seconds,
        "lookup_per_patch_seconds": lookup_seconds / 10000.0,
        "full_residual_seconds": full_seconds,
        "incremental_5000_seconds": incremental_seconds,
        "incremental_proposal_seconds": incremental_seconds / 5000.0,
        "sweep_45x45_seconds": sweep_seconds,
        "training_iteration_15x15_seconds": iteration_seconds,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark MPS direct, lookup, full, and incremental paths")
    parser.add_argument("--output", type=Path, default=ROOT / "results/mps_challenge/benchmarks")
    parser.add_argument("--seed", type=int, default=20260910)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    rows = []
    for chi in (2, 4, 8):
        print(f"benchmark chi={chi}", flush=True)
        rows.append(benchmark_chi(chi, args.seed + chi))
    payload = {
        "rows": rows,
        "peak_rss_kib": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
        "timing": "median wall time after warm-up",
    }
    (args.output / "benchmark.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    with (args.output / "benchmark.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"benchmark complete output={args.output}", flush=True)


if __name__ == "__main__":
    main()
