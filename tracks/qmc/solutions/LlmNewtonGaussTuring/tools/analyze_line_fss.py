#!/usr/bin/env python3
"""Analyze the independent line-update finite-size crossing pilot."""

from __future__ import annotations

import argparse
import csv
import hashlib
import shlex
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np


def tau_int(values: np.ndarray) -> float:
    centered = np.asarray(values, dtype=float) - np.mean(values)
    variance = np.dot(centered, centered) / len(centered)
    if len(centered) < 4 or variance <= 1e-30:
        return 0.5
    tau = 0.5
    for lag in range(1, len(centered) // 2 + 1):
        rho = np.dot(centered[:-lag], centered[lag:]) / ((len(centered) - lag) * variance)
        if rho <= 0.0:
            break
        tau += rho
        if lag >= 6 * tau:
            break
    return max(tau, 0.5)


def load(path: Path):
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    required = {
        "run_id", "lattice", "L", "N", "h", "seed", "start", "bin", "n_bins",
        "sweeps_per_bin", "E", "spacetime_m2", "spacetime_m4", "S0", "Sq",
        "beta", "epsilon", "q_norm", "q_count", "config_checked",
    }
    if not rows or not required.issubset(rows[0]):
        raise ValueError(f"missing columns: {sorted(required - set(rows[0] if rows else []))}")
    scaling_column = "c_tau" if "c_tau" in rows[0] else "beta_over_L"
    chains: dict[tuple[int, float, str, int], list[tuple[int, np.ndarray]]] = defaultdict(list)
    metadata: dict[tuple[int, float], tuple[float, int, int, float, float, float, int]] = {}
    identity = {(row["run_id"], row["lattice"]) for row in rows}
    if len(identity) != 1:
        raise ValueError("input mixes run IDs or lattices")
    for row in rows:
        key = (int(row["L"]), round(float(row["h"]), 8), row["start"], int(row["seed"]))
        cell = key[:2]
        values = np.array([
            float(row["spacetime_m2"]), float(row["spacetime_m4"]),
            float(row["S0"]), float(row["Sq"]), float(row["E"]),
        ])
        if not np.all(np.isfinite(values)) or int(row["config_checked"]) != 1:
            raise ValueError(f"invalid bin in chain {key}")
        lattice = row["lattice"]
        expected_sites = int(row["L"]) ** 2 * (2 if lattice == "honeycomb" else 1)
        if int(row["N"]) != expected_sites or int(row["q_count"]) != 6:
            raise ValueError(f"invalid geometry metadata in chain {key}")
        beta = float(row["beta"])
        scale = float(row[scaling_column])
        expected_beta = (scale * int(row["L"]) / float(row["h"])
                         if scaling_column == "c_tau" else scale * int(row["L"]))
        if not np.isclose(beta, expected_beta, rtol=1e-12):
            raise ValueError(f"inconsistent beta scaling in chain {key}")
        chains[key].append((int(row["bin"]), values))
        cell_metadata = (
            float(row["q_norm"]), int(row["q_count"]), int(row["sweeps_per_bin"]),
            beta, scale, float(row["epsilon"]), int(row["N"]),
        )
        if cell in metadata and metadata[cell] != cell_metadata:
            raise ValueError(f"inconsistent metadata in cell {cell}")
        metadata[cell] = cell_metadata
    ordered = {}
    for key, entries in chains.items():
        entries.sort(key=lambda item: item[0])
        expected = list(range(int(next(row["n_bins"] for row in rows if (
            int(row["L"]), round(float(row["h"]), 8), row["start"], int(row["seed"])) == key))))
        if [entry[0] for entry in entries] != expected:
            raise ValueError(f"missing or duplicate bins in chain {key}")
        ordered[key] = np.stack([entry[1] for entry in entries])
    sizes = sorted({key[0] for key in ordered})
    fields_by_size = {L: sorted({key[1] for key in ordered if key[0] == L}) for L in sizes}
    if len({tuple(fields) for fields in fields_by_size.values()}) != 1:
        raise ValueError("input is not a complete size-field grid")
    chain_shapes = defaultdict(set)
    chain_counts = defaultdict(lambda: defaultdict(int))
    for L, h, start, _ in ordered:
        chain_shapes[(L, h)].add(start)
        chain_counts[(L, h)][start] += 1
    if any(starts != {"random", "ordered"} for starts in chain_shapes.values()):
        raise ValueError("every cell must contain random and ordered starts")
    if any(counts["random"] != counts["ordered"] for counts in chain_counts.values()):
        raise ValueError("every cell must contain balanced random and ordered chains")
    scales = {cell_metadata[4] for cell_metadata in metadata.values()}
    epsilons = {cell_metadata[5] for cell_metadata in metadata.values()}
    if len(scales) != 1 or len(epsilons) != 1:
        raise ValueError("input mixes imaginary-time scales or bond shifts")
    return next(iter(identity)), ordered, metadata


def block_means(values: np.ndarray, block: int) -> np.ndarray:
    count = len(values) // block
    if count < 2:
        raise ValueError(f"only {count} blocks remain at block size {block}")
    return values[: count * block].reshape(count, block, values.shape[1]).mean(axis=1)


def derived(values: np.ndarray, q_norm: float, L: int) -> tuple[float, float]:
    means = values.mean(axis=0)
    if means[1] <= 0 or means[3] <= 0:
        return np.nan, np.nan
    q = means[0] ** 2 / means[1]
    xi2 = (means[2] / means[3] - 1) / (4 * np.sin(q_norm / 2) ** 2)
    return q, np.sqrt(xi2) / L if xi2 > 0 else np.nan


def difference_z(first: np.ndarray, second: np.ndarray) -> float:
    if len(first) < 2 or len(second) < 2:
        return np.nan
    variance = np.var(first, axis=0, ddof=1) / len(first)
    variance += np.var(second, axis=0, ddof=1) / len(second)
    scale = np.sqrt(np.maximum(variance, 0.0))
    difference = np.abs(np.mean(first, axis=0) - np.mean(second, axis=0))
    z = np.divide(difference, scale, out=np.zeros_like(difference), where=scale > 0.0)
    z[(scale == 0.0) & (difference > 0.0)] = np.inf
    return float(np.max(z))


def circular_block_resample(values: np.ndarray, block: int, rng: np.random.Generator) -> np.ndarray:
    count = len(values)
    block = max(1, min(block, count))
    starts = rng.integers(0, count, int(np.ceil(count / block)))
    indices = np.concatenate([(start + np.arange(block)) % count for start in starts])[:count]
    return values[indices]


def summarize(chains, metadata, bootstrap: int, seed: int):
    rng = np.random.default_rng(seed)
    raw_cells = defaultdict(list)
    diagnostics = []
    for key, values in sorted(chains.items()):
        taus = np.array([tau_int(values[:, column]) for column in range(values.shape[1])])
        raw_cells[key[:2]].append((key[2], key[3], values, taus))

    points = {}
    samples = {}
    sampling = []
    for cell, raw_chains in sorted(raw_cells.items()):
        L, _ = cell
        q_norm = metadata[cell][0]
        block = max(1, int(np.ceil(2 * max(np.max(entry[3]) for entry in raw_chains))))
        processed_chains = []
        for start, chain_seed, values, taus in raw_chains:
            blocked = block_means(values, block)
            processed_chains.append((start, chain_seed, values, blocked))
            diagnostics.append((L, cell[1], start, chain_seed, *taus, block, len(blocked)))
        blocked_by_start = {
            start: np.concatenate([entry[3] for entry in processed_chains if entry[0] == start])
            for start in ("random", "ordered")
        }
        start_z = difference_z(blocked_by_start["random"], blocked_by_start["ordered"])
        minimum_blocks = min(len(entry[3]) for entry in processed_chains)
        sampling.append((L, cell[1], block, minimum_blocks, start_z,
                         int(minimum_blocks >= 8 and np.isfinite(start_z) and start_z <= 5.0)))
        combined = np.concatenate([entry[2] for entry in processed_chains])
        estimate = derived(combined, q_norm, L)
        boot = np.empty((bootstrap, 2))
        for sample in range(bootstrap):
            selected = rng.integers(0, len(processed_chains), len(processed_chains))
            resampled = []
            for index in selected:
                values = processed_chains[index][2]
                resampled.append(circular_block_resample(values, block, rng))
            boot[sample] = derived(np.concatenate(resampled), q_norm, L)
        points[cell] = (*estimate, *np.nanstd(boot, axis=0, ddof=1), len(processed_chains))
        samples[cell] = boot
    return points, samples, diagnostics, sampling


def unique_crossing(fields: np.ndarray, first: np.ndarray, second: np.ndarray) -> float:
    difference = first - second
    roots = []
    for index in range(len(fields) - 1):
        if difference[index] == 0:
            roots.append(fields[index])
        elif difference[index] * difference[index + 1] < 0:
            fraction = difference[index] / (difference[index] - difference[index + 1])
            roots.append(fields[index] + fraction * (fields[index + 1] - fields[index]))
    return roots[0] if len(roots) == 1 else np.nan


def crossing_rows(points, samples, observable_index: int):
    sizes = sorted({key[0] for key in points})
    fields = np.array(sorted({key[1] for key in points}))
    rows = []
    for first, second in zip(sizes, sizes[1:]):
        first_curve = np.array([points[(first, h)][observable_index] for h in fields])
        second_curve = np.array([points[(second, h)][observable_index] for h in fields])
        estimate = unique_crossing(fields, first_curve, second_curve)
        bootstrap = min(samples[(first, fields[0])].shape[0], samples[(second, fields[0])].shape[0])
        roots = []
        for sample in range(bootstrap):
            first_sample = np.array([samples[(first, h)][sample, observable_index] for h in fields])
            second_sample = np.array([samples[(second, h)][sample, observable_index] for h in fields])
            root = unique_crossing(fields, first_sample, second_sample)
            if np.isfinite(root):
                roots.append(root)
        error = np.std(roots, ddof=1) if np.isfinite(estimate) and len(roots) > 1 else np.nan
        rows.append((first, second, estimate, error, len(roots), bootstrap - len(roots)))
    return rows


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_outputs(input_path: Path, identity, points, samples, diagnostics, sampling,
                  bootstrap: int, seed: int):
    run_id, lattice = identity
    output_dir = input_path.parent
    points_path = output_dir / f"{lattice}_points.csv"
    with points_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["run_id", "lattice", "L", "h", "Q", "Q_err", "xi_over_L", "xi_err", "chains"])
        for (L, h), (q, xi, qerr, xierr, chains) in sorted(points.items()):
            writer.writerow([run_id, lattice, L, h, q, qerr, xi, xierr, chains])

    diagnostics_path = output_dir / f"{lattice}_diagnostics.csv"
    with diagnostics_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["L", "h", "start", "seed", "tau_m2", "tau_m4", "tau_S0", "tau_Sq", "tau_E", "block_bins", "independent_blocks"])
        writer.writerows(diagnostics)

    sampling_path = output_dir / f"{lattice}_sampling.csv"
    with sampling_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["L", "h", "block_bins", "minimum_independent_blocks",
                         "random_ordered_max_z", "sampling_pass"])
        writer.writerows(sampling)

    all_crossings = {}
    crossing_path = output_dir / f"{lattice}_crossings.csv"
    with crossing_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["observable", "L_first", "L_second", "crossing", "bootstrap_error", "bootstrap_success", "bootstrap_failed"])
        for name, index in (("Q", 0), ("xi_over_L", 1)):
            rows = crossing_rows(points, samples, index)
            all_crossings[name] = rows
            writer.writerows((name, *row) for row in rows)

    sizes = sorted({key[0] for key in points})
    figure, axes = plt.subplots(1, 2, figsize=(10, 4), constrained_layout=True)
    for L in sizes:
        rows = sorted((h, points[(L, h)]) for size, h in points if size == L)
        fields = [row[0] for row in rows]
        axes[0].errorbar(fields, [row[1][0] for row in rows], yerr=[row[1][2] for row in rows], marker="o", capsize=2, label=f"L={L}")
        axes[1].errorbar(fields, [row[1][1] for row in rows], yerr=[row[1][3] for row in rows], marker="o", capsize=2, label=f"L={L}")
    axes[0].set(xlabel="Transverse field", ylabel=r"$Q=\langle \bar m^2\rangle^2/\langle \bar m^4\rangle$")
    axes[1].set(xlabel="Transverse field", ylabel=r"$\xi/L$")
    for axis in axes:
        axis.grid(alpha=0.25)
        axis.legend(frameon=False)
    figure_path = output_dir / f"{lattice}_crossings.png"
    figure.savefig(figure_path, dpi=180)
    plt.close(figure)

    report_path = output_dir / f"{lattice}_REPORT.md"
    minimum_blocks = min(row[3] for row in sampling)
    maximum_start_z = max(row[4] for row in sampling)
    sampling_gate = all(row[5] == 1 for row in sampling)
    with report_path.open("w", encoding="utf-8") as stream:
        stream.write(f"# {lattice.title()} line-update FSS pilot\n\n")
        stream.write(f"Run ID: `{run_id}`\n\n")
        stream.write(
            f"Sampling gate: **{'PASS' if sampling_gate else 'INCONCLUSIVE'}**; "
            f"minimum independent blocks per chain = {minimum_blocks} "
            f"(required: 8); maximum random/ordered drift = {maximum_start_z:.3g} sigma "
            "(required: <= 5).\n\n"
        )
        for observable, rows in all_crossings.items():
            stream.write(f"## {observable}\n\n")
            for first, second, crossing, error, success, failed in rows:
                status = "resolved" if np.isfinite(crossing) else "no unique central root"
                stream.write(f"- L={first}/{second}: `{crossing:.8g} +/- {error:.3g}`; {status}; bootstrap roots {success}, failed {failed}.\n")
            stream.write("\n")
        stream.write("This bounded pilot is not a precision critical-field fit. Failed sampling gates or missing central roots make its crossing estimate inconclusive.\n")
    artifacts = (points_path, diagnostics_path, sampling_path, crossing_path, figure_path, report_path)
    metadata_path = output_dir / f"analysis-metadata-{lattice}.txt"
    with metadata_path.open("w", encoding="utf-8") as stream:
        stream.write(f"run_id={run_id}\n")
        stream.write(f"timestamp={datetime.now().isoformat(timespec='seconds')}\n")
        source_commit = subprocess.run(
            ["git", "-C", str(Path(__file__).resolve().parents[1]), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        stream.write(f"source_commit={source_commit}\n")
        stream.write(f"command={shlex.join(sys.argv)}\n")
        stream.write(f"python_version={sys.version.split()[0]}\n")
        stream.write(f"numpy_version={np.__version__}\n")
        stream.write(f"matplotlib_version={matplotlib.__version__}\n")
        stream.write(f"bootstrap_samples={bootstrap}\n")
        stream.write(f"bootstrap_seed={seed}\n")
        stream.write(f"input_sha256={sha256(input_path)}\n")
        stream.write(f"script_sha256={sha256(Path(__file__))}\n")
        for artifact in artifacts:
            stream.write(f"output_sha256.{artifact.name}={sha256(artifact)}\n")
    return (*artifacts, metadata_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bins", type=Path)
    parser.add_argument("--bootstrap", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20260730)
    args = parser.parse_args()
    args.bootstrap > 1 or parser.error("--bootstrap must exceed one")
    identity, chains, metadata = load(args.bins)
    points, samples, diagnostics, sampling = summarize(chains, metadata, args.bootstrap, args.seed)
    artifacts = write_outputs(args.bins, identity, points, samples, diagnostics, sampling,
                              args.bootstrap, args.seed)
    print(f"lattice={identity[1]} cells={len(points)} chains={len(chains)}", flush=True)
    for path in artifacts:
        print(path, flush=True)


if __name__ == "__main__":
    main()
