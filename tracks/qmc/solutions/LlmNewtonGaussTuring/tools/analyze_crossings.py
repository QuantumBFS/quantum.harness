# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy"]
# ///
"""Blocked-chain crossing analysis for the Stage 3 square-lattice scan."""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

H_REF = 3.04438
N_BOOT = 2000
RNG = np.random.default_rng(20260728)


def tau_int(series: np.ndarray) -> float:
    values = np.asarray(series, dtype=float)
    if len(values) < 4:
        return 0.5
    centered = values - values.mean()
    variance = np.dot(centered, centered) / len(centered)
    if variance <= 1e-30:
        return 0.5
    tau = 0.5
    for lag in range(1, len(centered) // 2 + 1):
        rho = np.dot(centered[:-lag], centered[lag:]) / (
            (len(centered) - lag) * variance
        )
        if rho <= 0.0:
            break
        tau += rho
        if lag >= 6.0 * tau:
            break
    return max(tau, 0.5)


def circular_block_resample(
    values: np.ndarray, block: int, rng: np.random.Generator
) -> np.ndarray:
    count = len(values)
    block = max(1, min(block, count))
    starts = rng.integers(0, count, int(np.ceil(count / block)))
    indices = np.concatenate(
        [(start + np.arange(block)) % count for start in starts]
    )[:count]
    return values[indices]


def load(path: Path):
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"missing or empty input: {path}")
    raw = np.genfromtxt(path, delimiter=",", names=True, dtype=None, encoding="utf-8")
    raw = np.atleast_1d(raw)
    required = {
        "L", "h", "seed", "bin", "config_checked", "consistency_failures",
        "m2", "m4", "S0", "Sq",
    }
    missing = required - set(raw.dtype.names or ())
    if missing:
        raise ValueError(f"missing columns: {', '.join(sorted(missing))}")

    rows_by_chain = defaultdict(list)
    seed_owner = {}
    for row in raw:
        L = int(row["L"])
        h = round(float(row["h"]), 8)
        seed = int(row["seed"])
        owner = seed_owner.setdefault(seed, (L, h))
        if owner != (L, h):
            raise ValueError(f"RNG seed {seed} is reused across cells {owner} and {(L, h)}")
        config_checked = int(row["config_checked"])
        consistency_failures = int(row["consistency_failures"])
        if config_checked not in (0, 1):
            raise ValueError(f"invalid configuration-check flag in chain {(L, h, seed)}")
        if ((config_checked == 1 and consistency_failures < 0)
                or (config_checked == 0 and consistency_failures != -1)):
            raise ValueError(f"invalid configuration-check result in chain {(L, h, seed)}")
        values = np.asarray([row["m2"], row["m4"], row["S0"], row["Sq"]], dtype=float)
        if not np.all(np.isfinite(values)):
            raise ValueError(f"non-finite observable in chain {(L, h, seed)}")
        rows_by_chain[(L, h, seed)].append((int(row["bin"]), *values))

    chains = {}
    for key, rows in rows_by_chain.items():
        rows.sort(key=lambda item: item[0])
        indices = [item[0] for item in rows]
        if indices != list(range(len(rows))):
            raise ValueError(f"chain {key} has duplicate or missing bins")
        chains[key] = np.asarray([item[1:] for item in rows], dtype=float)

    cells = defaultdict(dict)
    for (L, h, seed), values in chains.items():
        cells[(L, h)][seed] = values
    chain_lengths = {len(values) for values in chains.values()}
    if len(chain_lengths) != 1:
        raise ValueError("every chain must contain the same number of bins")
    chain_counts = {len(chain_map) for chain_map in cells.values()}
    if len(chain_counts) != 1 or min(chain_counts, default=0) < 2:
        raise ValueError("every cell must contain the same number of at least two chains")
    fields_by_size = defaultdict(set)
    for L, h in cells:
        fields_by_size[L].add(h)
    if len({tuple(sorted(fields)) for fields in fields_by_size.values()}) != 1:
        raise ValueError("input is not a complete rectangular (L,h) grid")
    return cells


def q_of(bins: np.ndarray) -> float:
    m2, m4 = bins[:, 0].mean(), bins[:, 1].mean()
    return m2 * m2 / m4 if m4 > 1e-30 else np.nan


def xi_of(bins: np.ndarray, L: int) -> float:
    s0, sq = bins[:, 2].mean(), bins[:, 3].mean()
    qmin = 2.0 * np.pi / L
    denom = 4.0 * np.sin(qmin / 2.0) ** 2
    xi2 = (s0 / sq - 1.0) / denom if sq > 1e-30 else np.nan
    return np.sqrt(xi2) / L if xi2 > 0.0 else np.nan


def block_size(chain_map) -> int:
    maximum = 0.5
    for values in chain_map.values():
        maximum = max(maximum, *(tau_int(values[:, column]) for column in range(4)))
    return max(1, int(np.ceil(2.0 * maximum)))


def resample_cell(chain_map, block: int, rng: np.random.Generator) -> np.ndarray:
    seeds = np.asarray(sorted(chain_map), dtype=np.int64)
    selected = rng.choice(seeds, size=len(seeds), replace=True)
    return np.concatenate(
        [circular_block_resample(chain_map[int(seed)], block, rng) for seed in selected]
    )


def cell_value(chain_map, estimator, L: int, block: int, sample: bool = False) -> float:
    if sample:
        values = resample_cell(chain_map, block, RNG)
    else:
        values = np.concatenate([chain_map[seed] for seed in sorted(chain_map)])
    return estimator(values, L) if estimator is xi_of else estimator(values)


def crossing(fields: np.ndarray, first: np.ndarray, second: np.ndarray) -> float:
    difference = first - second
    roots = []
    for index in range(len(fields) - 1):
        if difference[index] == 0.0:
            roots.append(fields[index])
        elif difference[index] * difference[index + 1] < 0.0:
            fraction = difference[index] / (difference[index] - difference[index + 1])
            roots.append(fields[index] + fraction * (fields[index + 1] - fields[index]))
    return roots[0] if len(roots) == 1 else np.nan


def curve(cells, blocks, L: int, fields, estimator, sample: bool = False) -> np.ndarray:
    return np.asarray(
        [cell_value(cells[(L, h)], estimator, L, blocks[(L, h)], sample)
         for h in fields]
    )


def main(path: Path):
    cells = load(path)
    blocks = {key: block_size(chain_map) for key, chain_map in cells.items()}
    sizes = sorted({L for L, _ in cells})
    all_fields = sorted({h for _, h in cells})
    window = [h for h in all_fields if abs(h - H_REF) <= 0.045]
    if len(window) < 2:
        raise ValueError("crossing window has fewer than two fields")

    maximum_tau = max(
        max(tau_int(values[:, column]) for column in range(4))
        for chain_map in cells.values()
        for values in chain_map.values()
    )
    print(f"sizes={sizes}")
    print(f"window={window}")
    print(f"max_tau_int_bins={maximum_tau:.3f}\n")

    for name, estimator in (("Q_L", q_of), ("xi_L/L", xi_of)):
        print(f"--- {name} crossings (chain + circular-block bootstrap, n={N_BOOT}) ---")
        for first_size, second_size in zip(sizes, sizes[1:]):
            common = np.asarray(
                [
                    h for h in window
                    if (first_size, h) in cells and (second_size, h) in cells
                ]
            )
            if len(common) < 2:
                continue
            first_curve = curve(cells, blocks, first_size, common, estimator)
            second_curve = curve(cells, blocks, second_size, common, estimator)
            estimate = crossing(common, first_curve, second_curve)

            samples = []
            for _ in range(N_BOOT):
                sample_first = curve(
                    cells, blocks, first_size, common, estimator, sample=True
                )
                sample_second = curve(
                    cells, blocks, second_size, common, estimator, sample=True
                )
                value = crossing(common, sample_first, sample_second)
                if np.isfinite(value):
                    samples.append(value)
            samples = np.asarray(samples)
            error = samples.std(ddof=1) if len(samples) > 1 else np.nan
            failed = N_BOOT - len(samples)
            deviation = (estimate - H_REF) / error if error > 0.0 else np.nan
            print(
                f"  L={first_size:2d} vs {second_size:2d}: h_x={estimate:.5f} "
                f"+/- {error:.5f}; delta={estimate - H_REF:+.5f} "
                f"({deviation:+.1f} sigma); failed={failed}/{N_BOOT}"
            )
        print()


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "square_bins.csv"))
