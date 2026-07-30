"""Resumable sign-free Wolff QMC for the transverse-field Ising model."""

from __future__ import annotations

import argparse
import dataclasses
from dataclasses import dataclass
import hashlib
import json
import os
import platform
from pathlib import Path
import subprocess
import time

import numba
import numpy as np

from .qmc_mapping import couplings, energy_from_bond_sums


@dataclass(frozen=True, slots=True)
class QMCConfig:
    lx: int
    ly: int
    beta: float
    h: float
    j: float
    m: int
    thermal_sweeps: int
    measure_sweeps: int
    bins: int
    seed: int

    def __post_init__(self) -> None:
        positive = (
            self.lx,
            self.ly,
            self.beta,
            self.h,
            self.j,
            self.thermal_sweeps,
            self.measure_sweeps,
            self.seed,
        )
        if any(value <= 0 for value in positive):
            raise ValueError("QMC dimensions, couplings, sweeps, and seed must be positive")
        if self.m < 2:
            raise ValueError("m must be at least 2")
        if self.bins < 2 or self.measure_sweeps % self.bins:
            raise ValueError("measure_sweeps must be divisible into at least two bins")


@dataclass(frozen=True, slots=True)
class QMCResult:
    bin_energy: np.ndarray
    mean_energy: float
    stderr_energy: float
    mean_cluster_fraction: float


def _atomic_json(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def _atomic_npz(path: Path, **arrays) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        np.savez_compressed(handle, **arrays)
    os.replace(temporary, path)


@numba.njit
def _random_u64(state):
    x = state[0]
    x ^= x >> np.uint64(12)
    x ^= x << np.uint64(25)
    x ^= x >> np.uint64(27)
    state[0] = x
    return x * np.uint64(2685821657736338717)


@numba.njit
def _uniform(state):
    return (
        (_random_u64(state) >> np.uint64(11)) & np.uint64((1 << 53) - 1)
    ) / float(1 << 53)


@numba.njit
def _initialize_spins(spins, rng_state):
    flat = spins.reshape(spins.size)
    for index in range(flat.size):
        flat[index] = 1 if _uniform(rng_state) < 0.5 else -1


@numba.njit
def _wolff_cluster(spins, p_s, p_t, rng_state):
    m, lx, ly = spins.shape
    volume = spins.size
    seed = min(int(_uniform(rng_state) * volume), volume - 1)
    stack = np.empty(volume, np.int64)
    cluster = np.empty(volume, np.int64)
    marked = np.zeros(volume, np.uint8)
    stack[0] = seed
    marked[seed] = 1
    top = 1
    count = 0
    target = spins.reshape(volume)[seed]
    while top:
        top -= 1
        index = stack[top]
        cluster[count] = index
        count += 1
        t = index // (lx * ly)
        rem = index % (lx * ly)
        x = rem // ly
        y = rem % ly
        neighbors = (
            (t, x - 1, y, p_s),
            (t, x + 1, y, p_s),
            (t, x, y - 1, p_s),
            (t, x, y + 1, p_s),
            ((t - 1) % m, x, y, p_t),
            ((t + 1) % m, x, y, p_t),
        )
        for nt, nx, ny, probability in neighbors:
            if nx < 0 or nx >= lx or ny < 0 or ny >= ly:
                continue
            neighbor = nt * lx * ly + nx * ly + ny
            if (
                marked[neighbor] == 0
                and spins.reshape(volume)[neighbor] == target
                and _uniform(rng_state) < probability
            ):
                marked[neighbor] = 1
                stack[top] = neighbor
                top += 1
    flat = spins.reshape(volume)
    for index in range(count):
        flat[cluster[index]] = -flat[cluster[index]]
    return count


@numba.njit
def _sweep(spins, p_s, p_t, rng_state):
    return _wolff_cluster(spins, p_s, p_t, rng_state) / spins.size


@numba.njit
def _bond_sums(spins):
    m, lx, ly = spins.shape
    spatial = 0
    temporal = 0
    for t in range(m):
        for x in range(lx):
            for y in range(ly):
                if x + 1 < lx:
                    spatial += spins[t, x, y] * spins[t, x + 1, y]
                if y + 1 < ly:
                    spatial += spins[t, x, y] * spins[t, x, y + 1]
                temporal += spins[t, x, y] * spins[(t + 1) % m, x, y]
    return spatial, temporal


def _configuration_hash(cfg: QMCConfig) -> str:
    encoded = json.dumps(
        dataclasses.asdict(cfg), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _save_checkpoint(
    output: Path,
    *,
    config_hash: str,
    spins: np.ndarray,
    rng_state: np.ndarray,
    bin_energy: list[float],
    cluster_sum: float,
    cluster_count: int,
    thermal_sweeps: int,
    measurement_sweeps: int,
) -> None:
    _atomic_npz(
        output / "checkpoint.npz",
        spins=spins,
        rng_state=rng_state,
        bin_energy=np.asarray(bin_energy, dtype=float),
        cluster_sum=np.asarray([cluster_sum], dtype=float),
        cluster_count=np.asarray([cluster_count], dtype=np.int64),
        measurement_sweeps=np.asarray([measurement_sweeps], dtype=np.int64),
    )
    _atomic_json(
        output / "checkpoint.json",
        {
            "configuration_sha256": config_hash,
            "thermal_sweeps_completed": thermal_sweeps,
            "measurement_sweeps_completed": measurement_sweeps,
            "bins_completed": len(bin_energy),
        },
    )


def _result(
    bin_energy: list[float], cluster_sum: float, cluster_count: int
) -> QMCResult:
    values = np.asarray(bin_energy, dtype=float)
    mean = float(np.mean(values)) if values.size else float("nan")
    stderr = (
        float(np.std(values, ddof=1) / np.sqrt(values.size))
        if values.size >= 2
        else float("nan")
    )
    cluster_fraction = (
        float(cluster_sum / cluster_count) if cluster_count else float("nan")
    )
    return QMCResult(values, mean, stderr, cluster_fraction)


def run_chain(
    cfg: QMCConfig, output: Path | str, *, stop_after: int | None = None
) -> QMCResult:
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    bin_width = cfg.measure_sweeps // cfg.bins
    target_sweeps = cfg.measure_sweeps if stop_after is None else stop_after
    if target_sweeps < 0 or target_sweeps > cfg.measure_sweeps:
        raise ValueError("stop_after must lie within the measurement run")
    if target_sweeps % bin_width:
        raise ValueError("stop_after must end on a completed bin")

    config_hash = _configuration_hash(cfg)
    checkpoint_json = output / "checkpoint.json"
    checkpoint_npz = output / "checkpoint.npz"
    if checkpoint_json.exists() != checkpoint_npz.exists():
        raise RuntimeError("incomplete QMC checkpoint pair")

    if checkpoint_json.exists():
        metadata = json.loads(checkpoint_json.read_text(encoding="utf-8"))
        if metadata.get("configuration_sha256") != config_hash:
            raise ValueError("checkpoint configuration does not match this run")
        with np.load(checkpoint_npz, allow_pickle=False) as saved:
            spins = saved["spins"].copy()
            rng_state = saved["rng_state"].copy()
            bin_energy = saved["bin_energy"].astype(float).tolist()
            cluster_sum = float(saved["cluster_sum"][0])
            cluster_count = int(saved["cluster_count"][0])
            completed_sweeps = int(saved["measurement_sweeps"][0])
        if completed_sweeps != len(bin_energy) * bin_width:
            raise RuntimeError("QMC checkpoint counts are inconsistent")
    else:
        spins = np.empty((cfg.m, cfg.lx, cfg.ly), dtype=np.int8)
        rng_state = np.asarray([cfg.seed], dtype=np.uint64)
        _initialize_spins(spins, rng_state)
        coupling = couplings(cfg.beta, cfg.h, cfg.m, j=cfg.j)
        p_s = 1.0 - np.exp(-2.0 * coupling.ks)
        p_t = 1.0 - np.exp(-2.0 * coupling.kt)
        cluster_sum = 0.0
        cluster_count = 0
        for _ in range(cfg.thermal_sweeps):
            cluster_sum += _sweep(spins, p_s, p_t, rng_state)
            cluster_count += 1
        bin_energy = []
        completed_sweeps = 0

    coupling = couplings(cfg.beta, cfg.h, cfg.m, j=cfg.j)
    p_s = 1.0 - np.exp(-2.0 * coupling.ks)
    p_t = 1.0 - np.exp(-2.0 * coupling.kt)
    nsites = cfg.lx * cfg.ly
    while completed_sweeps < target_sweeps:
        energies = np.empty(bin_width, dtype=float)
        for index in range(bin_width):
            cluster_sum += _sweep(spins, p_s, p_t, rng_state)
            cluster_count += 1
            spatial, temporal = _bond_sums(spins)
            energies[index] = energy_from_bond_sums(
                coupling,
                spatial_sum=spatial,
                temporal_sum=temporal,
                nsites=nsites,
            )
        bin_energy.append(float(np.mean(energies)))
        completed_sweeps += bin_width
        _save_checkpoint(
            output,
            config_hash=config_hash,
            spins=spins,
            rng_state=rng_state,
            bin_energy=bin_energy,
            cluster_sum=cluster_sum,
            cluster_count=cluster_count,
            thermal_sweeps=cfg.thermal_sweeps,
            measurement_sweeps=completed_sweeps,
        )
        print(
            json.dumps(
                {
                    "event": "qmc_bin",
                    "bin": len(bin_energy),
                    "bins": cfg.bins,
                    "u": bin_energy[-1],
                },
                sort_keys=True,
            ),
            flush=True,
        )
    return _result(bin_energy, cluster_sum, cluster_count)


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main(argv=None) -> int:
    started = time.perf_counter()
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--field", type=float, required=True)
    parser.add_argument("--beta", type=float, required=True)
    parser.add_argument("--M", type=int, required=True)
    parser.add_argument("--chain", type=int, required=True)
    parser.add_argument("--thermal-sweeps", type=int)
    parser.add_argument("--measure-sweeps", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    raw = json.loads(Path(args.config).read_text(encoding="utf-8"))
    h_index = raw["model"]["fields"].index(args.field)
    beta_index = raw["betas"].index(args.beta)
    m_index = raw["trotter_slices"].index(args.M)
    if args.chain < 0 or args.chain >= raw["chains"]:
        raise ValueError("chain index is outside the configured range")
    seed = (
        raw["seed_base"]
        + 10000 * h_index
        + 100 * beta_index
        + 10 * m_index
        + args.chain
    )
    thermal_sweeps = (
        raw["thermal_sweeps"]
        if args.thermal_sweeps is None
        else args.thermal_sweeps
    )
    if thermal_sweeps <= 0:
        raise ValueError("thermal_sweeps must be positive")
    measure_sweeps = (
        raw["measure_sweeps"]
        if args.measure_sweeps is None
        else args.measure_sweeps
    )
    if measure_sweeps <= 0:
        raise ValueError("measure_sweeps must be positive")
    cfg = QMCConfig(
        raw["model"]["lx"],
        raw["model"]["ly"],
        args.beta,
        args.field,
        raw["model"]["j"],
        args.M,
        thermal_sweeps,
        measure_sweeps,
        raw["bins"],
        seed,
    )
    output = Path(args.run_dir)
    output.mkdir(parents=True, exist_ok=True)
    if args.dry_run:
        _atomic_json(
            output / "manifest.json",
            {"status": "rehearsed", "params": dataclasses.asdict(cfg)},
        )
        return 0
    result = run_chain(cfg, output)
    _atomic_npz(output / "bins.npz", energy=result.bin_energy)
    manifest = {
        "status": "success",
        "params": {
            "h": args.field,
            "beta": args.beta,
            "M": args.M,
            "chain": args.chain,
        },
        "settings": {
            "lx": cfg.lx,
            "ly": cfg.ly,
            "J": cfg.j,
            "boundary": raw["model"]["boundary"],
            "operator": raw["model"]["operator"],
            "thermal_sweeps": cfg.thermal_sweeps,
            "measure_sweeps": cfg.measure_sweeps,
            "bins": cfg.bins,
            "seed": seed,
        },
        "observables": {
            "u": result.mean_energy,
            "u_stderr": result.stderr_energy,
        },
        "diagnostics": {"mean_cluster_fraction": result.mean_cluster_fraction},
        "resources": {"wall_seconds": time.perf_counter() - started},
        "provenance": {
            "git_commit": _git_commit(),
            "python": platform.python_version(),
            "numba": numba.__version__,
        },
    }
    _atomic_json(output / "manifest.json", manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
