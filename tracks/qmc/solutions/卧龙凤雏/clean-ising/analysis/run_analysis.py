#!/usr/bin/env python3
"""Validate raw data, fit c, create plots, and render the offline report."""

import argparse
import csv
import hashlib
import json
import platform
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

import numpy as np

SOLUTION_DIR = Path(__file__).resolve().parent.parent
if str(SOLUTION_DIR) not in sys.path:
    sys.path.insert(0, str(SOLUTION_DIR))

from analysis.bootstrap import FIT_WINDOWS, bootstrap_mc
from analysis.data_io import load_exact, load_manifest, load_mc_blocks
from analysis.fitting import fit_c
from analysis.plots import build_all_figures
from analysis.report_builder import build_report_document


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--renderer", type=Path, required=True)
    parser.add_argument("--draws", type=int)
    arguments = parser.parse_args()
    try:
        passed = analyze_run(arguments.run_dir, arguments.renderer, arguments.draws)
    except Exception as error:
        print(f"analysis failed: {error}", file=sys.stderr, flush=True)
        return 1
    return 0 if passed else 2


def analyze_run(run_dir: Path, renderer: Path, draws: int = None) -> bool:
    start = time.monotonic()
    run_path = Path(run_dir).resolve()
    manifest_path = run_path / "manifest.json"
    manifest = load_manifest(manifest_path)
    exact_records = load_exact(run_path / "raw" / "exact.jsonl", manifest)
    mc_blocks = load_mc_blocks(run_path / "raw" / "mc_blocks.jsonl", manifest)
    production = bool(manifest["config"]["production_gates"])
    bootstrap_draws = draws if draws is not None else (2000 if production else 200)
    bootstrap_seed = 20260729
    bootstrap = bootstrap_mc(
        mc_blocks,
        manifest,
        draws=bootstrap_draws,
        seed=bootstrap_seed,
    )

    widths = np.asarray([record["l"] for record in exact_records], dtype=float)
    exact_g = np.asarray([record["g_exact"] for record in exact_records], dtype=float)
    exact_fits = {
        l_min: asdict(fit_c(widths, exact_g, l_min)) for l_min in FIT_WINDOWS
    }
    mc_fits = {}
    for l_min in FIT_WINDOWS:
        values = bootstrap.c_draws_primary[l_min]
        low, high = np.percentile(values, [2.5, 97.5])
        mc_fits[l_min] = {
            "c": float(np.mean(values)),
            "se": float(np.std(values, ddof=1)),
            "low": float(low),
            "high": float(high),
        }

    primary_exact = exact_fits[6]["c"]
    primary_mc = mc_fits[6]
    diagnostics = bootstrap.diagnostics
    gates = {
        "exact_accuracy": abs(primary_exact - 0.5) <= 0.005,
        "mc_accuracy": abs(primary_mc["c"] - 0.5) <= 0.03,
        "mc_interval": primary_mc["low"] <= 0.5 <= primary_mc["high"],
        "integration": bool(diagnostics["integration_passes"]),
        "exact_window": all(
            abs(exact_fits[l_min]["c"] - primary_exact) <= 0.005
            for l_min in (4, 8)
        ),
        "mc_window": all(
            diagnostics["window_stability"][l_min]["passes"] for l_min in (4, 8)
        ),
        "thermalization": bool(diagnostics["thermalization_passes"]),
        "replicas": bool(diagnostics["replica_agreement_passes"]),
        "runtime": (
            manifest.get("total_elapsed_s") is None
            or float(manifest["total_elapsed_s"]) < 600.0
        ),
    }

    requirements = SOLUTION_DIR / "analysis" / "requirements.txt"
    manifest["python_version"] = platform.python_version()
    manifest["python_requirements_sha256"] = _sha256(requirements)
    manifest["analysis_elapsed_s"] = time.monotonic() - start
    _write_json_atomic(manifest_path, manifest)

    results = {
        "widths": widths,
        "aspect_ratio": manifest["config"]["aspect_ratio"],
        "k_values": bootstrap.k_values,
        "mean_energy": bootstrap.mean_energy,
        "exact_g": exact_g,
        "mc_g": bootstrap.g_mean_primary,
        "mc_g_se": np.std(bootstrap.g_draws_primary, axis=0, ddof=1),
        "exact_fits": exact_fits,
        "mc_fits": mc_fits,
        "mc_c_nested": float(np.mean(bootstrap.c_draws_nested[6])),
        "primary_grid_points": bootstrap.primary_grid_points,
        "nested_grid_points": bootstrap.nested_grid_points,
        "diagnostics": diagnostics,
        "gates": gates,
        "manifest": manifest,
        "bootstrap_seed": bootstrap_seed,
    }
    _write_processed(run_path, results, bootstrap)
    build_all_figures(results, run_path / "figures")
    document = build_report_document(results, run_path)
    _write_json_atomic(run_path / "report.json", document)
    subprocess.run(
        [sys.executable, str(Path(renderer).resolve()), str(run_path)],
        check=True,
    )
    print(f"analysis report: {run_path / 'report.html'}", flush=True)
    return all(gates.values()) if production else True


def _write_processed(run_dir: Path, results: Mapping[str, Any], bootstrap) -> None:
    processed = run_dir / "processed"
    processed.mkdir(parents=True, exist_ok=True)
    widths = np.asarray(results["widths"])
    primary = results["primary_grid_points"]
    nested = results["nested_grid_points"]
    _write_csv(
        processed / "free_energies.csv",
        [
            "L",
            "g_exact",
            f"g_mc_{primary}",
            f"g_mc_{primary}_se",
            f"g_mc_{nested}",
        ],
        [
            [
                int(width),
                results["exact_g"][index],
                results["mc_g"][index],
                results["mc_g_se"][index],
                bootstrap.g_mean_nested[index],
            ]
            for index, width in enumerate(widths)
        ],
    )
    _write_csv(
        processed / "central_charge_fits.csv",
        ["L_min", "method", "c", "standard_error", "ci_low", "ci_high", "role"],
        [
            row
            for l_min in FIT_WINDOWS
            for row in (
                [
                    l_min,
                    "transfer_matrix",
                    results["exact_fits"][l_min]["c"],
                    "",
                    "",
                    "",
                    "primary" if l_min == 6 else "diagnostic",
                ],
                [
                    l_min,
                    "monte_carlo",
                    results["mc_fits"][l_min]["c"],
                    results["mc_fits"][l_min]["se"],
                    results["mc_fits"][l_min]["low"],
                    results["mc_fits"][l_min]["high"],
                    "primary" if l_min == 6 else "diagnostic",
                ],
            )
        ],
    )
    energy_rows = []
    for width_index, width in enumerate(widths):
        sites = int(width * width * results["aspect_ratio"])
        for k_index, k_value in enumerate(results["k_values"]):
            energy = results["mean_energy"][width_index, k_index]
            energy_rows.append(
                [int(width), k_index, k_value, energy, energy / sites]
            )
    _write_csv(
        processed / "energy_vs_k.csv",
        ["L", "K_index", "K", "mean_H", "mean_H_per_site"],
        energy_rows,
    )
    diagnostics = results["diagnostics"]
    _write_csv(
        processed / "diagnostics.csv",
        ["metric", "value"],
        [
            ["max_half_z", diagnostics["max_half_z"]],
            ["max_replica_z", diagnostics["max_replica_z"]],
            ["integration_shift", diagnostics["integration_shift"]],
            ["primary_standard_error", diagnostics["primary_standard_error"]],
        ],
    )
    _write_json_atomic(
        processed / "analysis_metadata.json",
        {
            "bootstrap_seed": results["bootstrap_seed"],
            "bootstrap_draws": int(bootstrap.g_draws_primary.shape[0]),
            "primary_grid_points": bootstrap.primary_grid_points,
            "nested_grid_points": bootstrap.nested_grid_points,
            "fit_windows": list(FIT_WINDOWS),
            "primary_fit_window": 6,
            "gates": results["gates"],
        },
    )


def _write_csv(path: Path, columns: Iterable[str], rows: Iterable[Iterable[Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        writer.writerows(rows)


def _write_json_atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    temporary.replace(path)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
