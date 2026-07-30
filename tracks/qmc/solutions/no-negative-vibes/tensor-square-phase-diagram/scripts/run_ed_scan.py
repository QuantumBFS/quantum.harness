#!/usr/bin/env python3
"""Run the approved m=3 grand-canonical or m=4 half-filled ED pilot."""

from __future__ import annotations

import argparse
import csv
import json
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from tensor_square.ed import (
    build_sector_operators,
    charge_gap,
    sector_result,
)


T_GRID = (0.0, 0.25, 0.5, 1.0, 2.0)
G_GRID = (0.0, 0.25, 0.5, 1.0, 2.0)
MU_GRID = (-1.5, 0.0, 1.5)
M3_ASYMMETRY = 0.15
_CACHE: dict[str, object] = {}


def _initialize(mode: str) -> None:
    if mode == "m3":
        _CACHE["main"] = [
            build_sector_operators(3, n, "noncommuting") for n in range(10)
        ]
        _CACHE["commuting"] = [
            build_sector_operators(3, n, "commuting") for n in range(10)
        ]
    elif mode == "m4":
        _CACHE["main"] = [build_sector_operators(4, 8, "noncommuting")]
    else:
        raise ValueError(mode)


def _overlap(previous: np.ndarray | None, current: np.ndarray) -> float:
    if previous is None or previous.shape[0] != current.shape[0]:
        return float("nan")
    singular_values = np.linalg.svd(previous.conj().T @ current, compute_uv=False)
    return float(
        np.linalg.norm(singular_values)
        / np.sqrt(min(previous.shape[1], current.shape[1]))
    )


def _m3_line(t: float) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for variant in ("noncommuting", "commuting"):
        operators_by_sector = _CACHE[
            "main" if variant == "noncommuting" else "commuting"
        ]
        previous_by_mu: dict[float, tuple[int, np.ndarray] | None] = {
            mu: None for mu in MU_GRID
        }
        previous_fixed: dict[int, np.ndarray | None] = {4: None, 5: None}
        mu_values = MU_GRID if variant == "noncommuting" else (0.0,)
        for g_ratio in G_GRID:
            sector_rows = [
                sector_result(
                    operators,
                    t=t,
                    g_a=1.0,
                    g_b=g_ratio,
                    v_asymmetry=M3_ASYMMETRY,
                    seed=300_000 + int(1000 * t) + int(100 * g_ratio) + n,
                )
                for n, operators in enumerate(operators_by_sector)
            ]
            sector_energies = [float(row["energy"]) for row in sector_rows]
            for mu in mu_values:
                shifted = [
                    energy - mu * n for n, energy in enumerate(sector_energies)
                ]
                minimum = min(shifted)
                tied = [
                    n
                    for n, value in enumerate(shifted)
                    if value <= minimum + 2.0e-10
                ]
                selected_n = min(tied, key=lambda n: (abs(n - 4.5), n))
                selected = sector_rows[selected_n]
                previous_entry = previous_by_mu[mu]
                fidelity = (
                    _overlap(previous_entry[1], selected["subspace"])
                    if previous_entry is not None
                    and previous_entry[0] == selected_n
                    else float("nan")
                )
                previous_by_mu[mu] = (selected_n, selected["subspace"])
                row = {
                    key: value
                    for key, value in selected.items()
                    if key not in {"state", "subspace"}
                }
                row.update(
                    {
                        "mode": "m3",
                        "variant": variant,
                        "m": 3,
                        "t": t,
                        "g_a": 1.0,
                        "g_b_over_g_a": g_ratio,
                        "v_asymmetry": M3_ASYMMETRY,
                        "mu": mu,
                        "grand_energy": shifted[selected_n],
                        "density": selected_n / 9.0,
                        "charge_gap": charge_gap(
                            sector_energies, selected_n
                        ),
                        "fidelity_previous_g": fidelity,
                    }
                )
                rows.append(row)
            if variant == "noncommuting":
                for fixed_n in (4, 5):
                    selected = sector_rows[fixed_n]
                    fidelity = _overlap(
                        previous_fixed[fixed_n], selected["subspace"]
                    )
                    previous_fixed[fixed_n] = selected["subspace"]
                    row = {
                        key: value
                        for key, value in selected.items()
                        if key not in {"state", "subspace"}
                    }
                    row.update(
                        {
                            "mode": "m3",
                            "variant": f"noncommuting_n{fixed_n}",
                            "m": 3,
                            "t": t,
                            "g_a": 1.0,
                            "g_b_over_g_a": g_ratio,
                            "v_asymmetry": M3_ASYMMETRY,
                            "mu": 0.0,
                            "grand_energy": float(selected["energy"]),
                            "density": fixed_n / 9.0,
                            "charge_gap": charge_gap(
                                sector_energies, fixed_n
                            ),
                            "fidelity_previous_g": fidelity,
                        }
                    )
                    rows.append(row)
    free_operators = _CACHE["main"]
    free_rows = [
        sector_result(
            operators,
            t=t,
            g_a=0.0,
            g_b=0.0,
            v_asymmetry=M3_ASYMMETRY,
            seed=399_000 + int(1000 * t) + n,
        )
        for n, operators in enumerate(free_operators)
    ]
    free_energies = [float(row["energy"]) for row in free_rows]
    selected_n = int(np.argmin(free_energies))
    selected = free_rows[selected_n]
    free_row = {
        key: value
        for key, value in selected.items()
        if key not in {"state", "subspace"}
    }
    free_row.update(
        {
            "mode": "m3",
            "variant": "free",
            "m": 3,
            "t": t,
            "g_a": 0.0,
            "g_b_over_g_a": 0.0,
            "v_asymmetry": M3_ASYMMETRY,
            "mu": 0.0,
            "grand_energy": free_energies[selected_n],
            "density": selected_n / 9.0,
            "charge_gap": charge_gap(free_energies, selected_n),
            "fidelity_previous_g": float("nan"),
        }
    )
    rows.append(free_row)
    print(f"m3 t={t:g}: {len(rows)} rows complete", flush=True)
    return rows


def _m4_line(t: float) -> list[dict[str, object]]:
    operators = _CACHE["main"][0]
    rows: list[dict[str, object]] = []
    previous: np.ndarray | None = None
    for g_ratio in G_GRID:
        selected = sector_result(
            operators,
            t=t,
            g_a=1.0,
            g_b=g_ratio,
            v_asymmetry=0.0,
            seed=400_000 + int(1000 * t) + int(100 * g_ratio),
        )
        fidelity = _overlap(previous, selected["subspace"])
        previous = selected["subspace"]
        row = {
            key: value
            for key, value in selected.items()
            if key not in {"state", "subspace"}
        }
        row.update(
            {
                "mode": "m4",
                "variant": "noncommuting",
                "m": 4,
                "t": t,
                "g_a": 1.0,
                "g_b_over_g_a": g_ratio,
                "v_asymmetry": 0.0,
                "mu": 0.0,
                "grand_energy": float(selected["energy"]),
                "density": 0.5,
                "charge_gap": float("nan"),
                "fidelity_previous_g": fidelity,
            }
        )
        rows.append(row)
    print(f"m4 t={t:g}: {len(rows)} rows complete", flush=True)
    return rows


def _survivors(rows: list[dict[str, object]], mode: str) -> list[dict[str, object]]:
    survivors = []
    for t in T_GRID:
        line = [
            row
            for row in rows
            if row["variant"]
            == ("noncommuting_n4" if mode == "m3" else "noncommuting")
            and row["t"] == t
            and (mode == "m4" or row["mu"] == 0.0)
        ]
        line.sort(key=lambda row: float(row["g_b_over_g_a"]))
        balances = np.asarray([float(row["channel_balance"]) for row in line])
        finite_fidelity = [
            float(row["fidelity_previous_g"])
            for row in line
            if np.isfinite(float(row["fidelity_previous_g"]))
        ]
        balance_span = float(np.max(balances) - np.min(balances))
        fidelity_min = min(finite_fidelity, default=1.0)
        commutator_max = max(float(row["commutator_sq"]) for row in line)
        gap_values = np.asarray([float(row["sector_gap"]) for row in line])
        interior_gap = float(np.min(gap_values[1:-1]))
        endpoint_gap = float(0.5 * (gap_values[0] + gap_values[-1]))
        gap_anomaly = interior_gap < 0.75 * endpoint_gap
        candidate = t > 0.0 and (
            (balance_span >= 0.25 and fidelity_min <= 0.995) or gap_anomaly
        )
        survivors.append(
            {
                "t": t,
                "classification": "SURVIVE" if candidate else "STOP",
                "balance_span": balance_span,
                "fidelity_min": fidelity_min,
                "commutator_sq_max": commutator_max,
                "interior_gap_min": interior_gap,
                "endpoint_gap_mean": endpoint_gap,
                "reason": (
                    "fixed-sector channel reordering or gap anomaly"
                    if candidate
                    else (
                        "t=0 accidental degeneracy / no kinetic competition"
                        if t == 0.0
                        else "no fixed-sector channel or gap anomaly"
                    )
                ),
            }
        )
    return survivors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("m3", "m4"), required=True)
    parser.add_argument("--workers", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.workers <= 14:
        raise ValueError("WSL ED worker count must be in [1, 14]")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    context = mp.get_context("spawn")
    worker = _m3_line if args.mode == "m3" else _m4_line
    rows: list[dict[str, object]] = []
    with ProcessPoolExecutor(
        max_workers=min(args.workers, len(T_GRID)),
        mp_context=context,
        initializer=_initialize,
        initargs=(args.mode,),
    ) as executor:
        for line in executor.map(worker, T_GRID):
            rows.extend(line)
    rows.sort(
        key=lambda row: (
            str(row["variant"]),
            float(row["mu"]),
            float(row["t"]),
            float(row["g_b_over_g_a"]),
        )
    )
    table_path = args.output_dir / "table.csv"
    fieldnames = list(rows[0].keys())
    with table_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    survivors = _survivors(rows, args.mode)
    summary = {
        "experiment_id": f"stage1-ed-{args.mode}-20260729",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "mode": args.mode,
        "workers": min(args.workers, len(T_GRID)),
        "blas_threads": 1,
        "t_grid": T_GRID,
        "g_grid": G_GRID,
        "mu_grid": MU_GRID if args.mode == "m3" else (0.0,),
        "m3_asymmetry": M3_ASYMMETRY if args.mode == "m3" else 0.0,
        "rows": len(rows),
        "max_eigen_residual": max(float(row["residual"]) for row in rows),
        "survivors": survivors,
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.output_dir / "survivors.json").write_text(
        json.dumps(survivors, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
