#!/usr/bin/env python3
"""Generate the high-statistics physical Berry-curvature ensemble."""

from __future__ import annotations

import argparse
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from lgeth.channels import (
    build_physical_channel_cache,
    cached_channel,
    curvature_from_channels,
    normalized_potential,
)
from lgeth.jacobi import jacobi_parameters, normalized_curvature


VERSION = "v1"
REGISTERED_SAMPLES = 20_000
REGISTERED_SEED_BLOCKS = 8
REGISTERED_SEED = 20260728110


def _split_indices(count: int, seed: int) -> tuple[np.ndarray, ...]:
    if count == REGISTERED_SAMPLES:
        sizes = (12_000, 4_000, 4_000)
    else:
        train = int(round(0.625 * count))
        validation = (count - train) // 2
        sizes = (train, validation, count - train - validation)
    permutation = np.random.default_rng(seed).permutation(count)
    first = sizes[0]
    second = first + sizes[1]
    return (
        np.sort(permutation[:first]),
        np.sort(permutation[first:second]),
        np.sort(permutation[second:]),
    )


def run(
    output_json: Path,
    output_npz: Path,
    samples: int = REGISTERED_SAMPLES,
    seed_blocks: int = REGISTERED_SEED_BLOCKS,
    seed: int = REGISTERED_SEED,
) -> dict[str, Any]:
    """Generate physical spectra and fixed train/validation/test indices."""

    started = time.perf_counter()
    count = int(samples)
    blocks = int(seed_blocks)
    if count < 64 or blocks < 2 or count < blocks:
        raise ValueError("require samples>=64 and 2<=seed_blocks<=samples")
    cache = build_physical_channel_cache()
    D = cache.rank
    M = cache.external_dimension
    parameters = jacobi_parameters(D, M)
    if parameters.plus_atoms or parameters.minus_atoms:
        raise RuntimeError("the registered physical ensemble must be atom free")
    sites = cache.channel_basis.shape[0]
    raw_spectra = np.empty((count, D), dtype=np.float32)
    normalized_spectra = np.empty((count, D), dtype=np.float32)
    coefficients_v = np.empty((count, sites), dtype=np.float32)
    coefficients_w = np.empty_like(coefficients_v)
    active_ranks = np.empty(count, dtype=np.int16)
    curvature_ranks = np.empty(count, dtype=np.int16)
    seed_block = np.empty(count, dtype=np.int16)
    block_indices = np.array_split(np.arange(count), blocks)
    child_sequences = np.random.SeedSequence(seed).spawn(blocks)
    for block, indices in enumerate(block_indices):
        rng = np.random.default_rng(child_sequences[block])
        for sample in indices:
            potential_v = normalized_potential(rng, sites)
            potential_w = normalized_potential(rng, sites)
            channel_v = cached_channel(potential_v, cache)
            channel_w = cached_channel(potential_w, cache)
            raw = np.linalg.eigvalsh(
                curvature_from_channels(channel_v, channel_w)
            )
            normalized = normalized_curvature(
                channel_v,
                channel_w,
                rtol=1e-10,
            )
            normalized_values = np.linalg.eigvalsh(normalized.omega)
            raw_spectra[sample] = raw
            normalized_spectra[sample] = normalized_values
            coefficients_v[sample] = potential_v
            coefficients_w[sample] = potential_w
            active_ranks[sample] = normalized.rank
            cutoff = 1e-10 * float(np.max(np.abs(raw)))
            curvature_ranks[sample] = np.count_nonzero(np.abs(raw) > cutoff)
            seed_block[sample] = block
        print(
            f"physical block {block + 1}/{blocks}: "
            f"{indices[-1] + 1}/{count} samples",
            flush=True,
        )
    train_indices, validation_indices, test_indices = _split_indices(
        count,
        seed + 1,
    )
    observed_atoms = int(
        np.count_nonzero(
            np.isclose(
                np.abs(normalized_spectra),
                1.0,
                atol=2e-7,
                rtol=0.0,
            )
        )
    )
    checks = {
        "registered_rank_is_50": D == 50,
        "parent_kernel_exact": cache.kernel_bandwidth < 1e-10,
        "parent_gap_open": cache.external_gap > 1e-3,
        "all_active_ranks_are_full": bool(np.all(active_ranks == D)),
        "all_curvature_ranks_are_full": bool(np.all(curvature_ranks == D)),
        "normalized_spectra_bounded": bool(
            np.max(np.abs(normalized_spectra)) <= 1.0 + 2e-7
        ),
        "no_exact_atoms": observed_atoms == 0,
        "split_complete_and_disjoint": bool(
            np.array_equal(
                np.sort(
                    np.concatenate(
                        [train_indices, validation_indices, test_indices]
                    )
                ),
                np.arange(count),
            )
            and np.intersect1d(train_indices, validation_indices).size == 0
            and np.intersect1d(train_indices, test_indices).size == 0
            and np.intersect1d(validation_indices, test_indices).size == 0
        ),
        "all_seed_blocks_nonempty": bool(
            np.array_equal(np.unique(seed_block), np.arange(blocks))
        ),
    }
    result = {
        "schema_version": 1,
        "version": VERSION,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "physical_case": {"N": cache.N, "n": cache.n_flux, "D": D, "M": M},
        "sample_count": count,
        "seed": int(seed),
        "seed_blocks": blocks,
        "split": {
            "train": int(train_indices.size),
            "validation": int(validation_indices.size),
            "test": int(test_indices.size),
            "split_seed": int(seed + 1),
        },
        "parent": {
            "kernel_bandwidth": cache.kernel_bandwidth,
            "external_gap": cache.external_gap,
        },
        "jacobi_parameters": {
            "interior_dimension": parameters.interior_dimension,
            "exponent": parameters.exponent,
            "plus_atoms": parameters.plus_atoms,
            "minus_atoms": parameters.minus_atoms,
        },
        "observed_exact_atoms": observed_atoms,
        "checks": checks,
        "all_checks_pass": bool(all(checks.values())),
        "runtime_seconds": time.perf_counter() - started,
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
    }
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_npz.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(result, indent=2) + "\n",
        encoding="utf-8",
    )
    np.savez_compressed(
        output_npz,
        normalized_spectra=normalized_spectra,
        raw_spectra=raw_spectra,
        tangent_coefficients_v=coefficients_v,
        tangent_coefficients_w=coefficients_w,
        train_indices=train_indices.astype(np.int32),
        validation_indices=validation_indices.astype(np.int32),
        test_indices=test_indices.astype(np.int32),
        seed_block=seed_block,
        active_ranks=active_ranks,
        curvature_ranks=curvature_ranks,
        channel_basis=cache.channel_basis,
        tangent_gram=cache.tangent_gram,
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("output/physical_ensemble_v1.json"),
    )
    parser.add_argument(
        "--output-npz",
        type=Path,
        default=Path("output/physical_ensemble_v1.npz"),
    )
    parser.add_argument("--samples", type=int, default=REGISTERED_SAMPLES)
    parser.add_argument(
        "--seed-blocks", type=int, default=REGISTERED_SEED_BLOCKS
    )
    args = parser.parse_args()
    result = run(
        args.output_json,
        args.output_npz,
        samples=args.samples,
        seed_blocks=args.seed_blocks,
    )
    print(json.dumps(result, indent=2))
    if not result["all_checks_pass"]:
        raise SystemExit("physical-ensemble audit failed")


if __name__ == "__main__":
    main()
