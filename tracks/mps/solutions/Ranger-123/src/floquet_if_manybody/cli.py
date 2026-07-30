"""Command line interface for baseline generation and audit."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Literal

import numpy as np

from .experiments import (
    backend_comparison,
    n2_bright_sweep,
    n2_markov_heat_spectrum,
    n3_sector_sweep,
)
from .io import read_result, write_result
from .plotting import (
    plot_backend_comparison,
    plot_dark_diagnostics,
    plot_error_maps,
    plot_heat_spectrum,
    plot_heat_valve_hero,
    plot_model_variants,
    plot_n2,
    plot_n3,
    plot_n3_pt_dynamics,
    plot_n3_sector_heat,
    plot_odd_sector_difference,
)

ExactBackend = Literal["uniform_tempo", "oqupy"]


def generate_baselines(output: Path, figures: Path, quick: bool = False) -> int:
    n2 = n2_bright_sweep(np.linspace(0, 2, 17 if quick else 81))
    n3_values = np.geomspace(0.125, 16, 15 if quick else 49)
    n3 = n3_sector_sweep(n3_values)
    comparison = backend_comparison(
        [0.005, 0.01] if quick else [0.005, 0.01, 0.025, 0.05],
        steps_per_period=24 if quick else 48,
        periods=4 if quick else 100,
    )
    heat = n2_markov_heat_spectrum(
        steps_per_period=32 if quick else 96,
        correlation_periods=3 if quick else 16,
    )
    paths = {
        "n2_exact.json": n2,
        "n3_exact.json": n3,
        "backend_comparison.json": comparison,
        "n2_markov_heat.json": heat,
    }
    for name, payload in paths.items():
        write_result(output / name, payload)
    plot_n2(read_result(output / "n2_exact.json"), figures / "n2_exact")
    plot_n3(read_result(output / "n3_exact.json"), figures / "n3_exact")
    plot_backend_comparison(
        read_result(output / "backend_comparison.json"), figures / "backend_comparison"
    )
    plot_heat_spectrum(
        read_result(output / "n2_markov_heat.json"), figures / "n2_markov_heat"
    )
    return 0


def audit_results(directory: Path, allow_unconverged: bool = False) -> int:
    failures: list[str] = []
    files = sorted(
        path
        for path in directory.glob("*.json")
        if path.name != "ARTIFACT_PROVENANCE.json"
    )
    if not files:
        failures.append("no result files")
    for path in files:
        try:
            result = read_result(path)
        except (ValueError, OSError) as exc:
            failures.append(str(exc))
            continue
        if not result["converged"] and not allow_unconverged:
            failures.append(f"{path.name}: unconverged")
        if "method" not in result:
            failures.append(f"{path.name}: missing method label")
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print(f"PASS: audited {len(files)} result files")
    return 0


def generate_pt_baselines(output: Path, figures: Path) -> int:
    from .pt_experiments import n2_pt_tempo_heat, n3_pt_tempo_dynamics

    n2 = n2_pt_tempo_heat()
    write_result(output / "n2_pt_tempo_heat.json", n2)
    plot_heat_spectrum(
        read_result(output / "n2_pt_tempo_heat.json"), figures / "n2_pt_tempo_heat"
    )
    n3 = n3_pt_tempo_dynamics()
    write_result(output / "n3_pt_tempo_dynamics.json", n3)
    plot_n3_pt_dynamics(
        read_result(output / "n3_pt_tempo_dynamics.json"),
        figures / "n3_pt_tempo_dynamics",
    )
    return 0


def generate_n3_paper_grid(
    output: Path,
    cache: Path,
    figures: Path,
    exact_backend: ExactBackend = "uniform_tempo",
) -> int:
    from .paper_extension import run_n3_heat_grid

    manifest = run_n3_heat_grid(output, cache, exact_backend=exact_backend)
    plot_n3_sector_heat(manifest, figures / "n3_sector_heat")
    plot_odd_sector_difference(manifest, figures / "n3_odd_difference")
    plot_dark_diagnostics(manifest, figures / "dark_diagnostics")
    return 0 if manifest["converged"] else 1


def generate_error_map(
    output: Path,
    cache: Path,
    figures: Path,
    exact_backend: ExactBackend = "uniform_tempo",
) -> int:
    from .paper_extension import run_error_grid

    manifest = run_error_grid(output, cache, exact_backend=exact_backend)
    plot_error_maps(manifest, figures / "error_maps")
    return 0


def generate_model_comparison(
    output: Path,
    cache: Path,
    figures: Path,
    exact_backend: ExactBackend = "uniform_tempo",
    full_kac: bool = False,
) -> int:
    from .paper_extension import run_model_comparison

    manifest = run_model_comparison(
        output,
        cache,
        exact_backend=exact_backend,
        full_kac=full_kac,
    )
    plot_model_variants(manifest, figures / "model_variants")
    return 0 if manifest.get("locally_complete", manifest["converged"]) else 1


def paper_audit(directory: Path) -> int:
    from .paper_extension import audit_paper_results

    passed, failures = audit_paper_results(directory)
    if not passed:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print("PASS: paper extension manifests and convergence evidence are complete")
    return 0


def generate_heat_valve(
    output: Path,
    cache: Path,
    figures: Path,
    *,
    full: bool,
) -> int:
    from .convergence import ConvergenceCache, atomic_write_result
    from .heat_valve import (
        HeatValvePoint,
        ValveNumerics,
        build_heat_valve_manifest,
        isolated_valve_scan,
        run_uniform_valve_point,
    )
    from .heat_valve_audit import audit_heat_valve_manifest

    floquet_steps = 360 if full else 240
    xi_values = np.linspace(1.8, 4.0, 45)
    isolated = isolated_valve_scan(
        HeatValvePoint(
            n=n,
            xi=float(xi),
            drive_frequency=3.0,
            floquet_steps=floquet_steps,
        )
        for n in (1, 2, 3)
        for xi in xi_values
    )
    atomic_write_result(output / "isolated_scan.json", isolated)
    selection = build_heat_valve_manifest(isolated)
    selected = [
        HeatValvePoint(
            n=int(item["n"]),  # type: ignore[arg-type]
            xi=float(item["xi"]),
            j=float(item["j"]),
            omega=float(item["omega"]),
            drive_frequency=float(item["drive_frequency"]),
            alpha=float(item["alpha"]),
            cutoff=float(item["cutoff"]),
            temperature=float(item["temperature"]),
            floquet_steps=int(item["floquet_steps"]),
        )
        for item in selection["selected_points"]
        if full or int(item["n"]) == 3
    ]
    numerical_controls = ValveNumerics()
    result_cache = ConvergenceCache(cache)
    results = []
    for point in selected:
        result = run_uniform_valve_point(
            point,
            numerical_controls,
            result_cache,
        )
        results.append(result)
        atomic_write_result(
            output / f"n{point.n}_xi{point.xi:.2f}.json",
            result,
        )
    manifest = build_heat_valve_manifest(isolated, results)
    audit = audit_heat_valve_manifest(manifest)
    manifest["audit"] = asdict(audit)
    atomic_write_result(output / "heat_valve_manifest.json", manifest)
    plot_heat_valve_hero(manifest, figures / "heat_valve_hero")
    requested = 9 if full else 3
    return 0 if len(results) == requested and all(
        bool(item.get("converged", False)) for item in results
    ) else 1


def heat_valve_audit(directory: Path) -> int:
    from .heat_valve_audit import audit_heat_valve_manifest

    path = directory / "heat_valve_manifest.json"
    if not path.is_file():
        print(f"FAIL: missing {path}")
        return 1
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        audit = audit_heat_valve_manifest(manifest)
    except (OSError, json.JSONDecodeError, ValueError, KeyError, TypeError) as exc:
        print(f"FAIL: malformed heat-valve manifest: {exc}")
        return 1
    if not audit.dark_channel_passed:
        for failure in audit.failures:
            print(f"FAIL: {failure}")
        return 1
    print("PASS: pole-resolved Floquet dark-channel gates are complete")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="floquet-if")
    subparsers = parser.add_subparsers(dest="command", required=True)
    baseline = subparsers.add_parser("baselines")
    baseline.add_argument("--output", type=Path, default=Path("results"))
    baseline.add_argument("--figures", type=Path, default=Path("figures"))
    baseline.add_argument("--quick", action="store_true")
    pt_baseline = subparsers.add_parser("pt-baselines")
    pt_baseline.add_argument("--output", type=Path, default=Path("results"))
    pt_baseline.add_argument("--figures", type=Path, default=Path("figures"))
    audit = subparsers.add_parser("audit")
    audit.add_argument("directory", type=Path)
    audit.add_argument("--allow-unconverged", action="store_true")
    for command in ("n3-heat-grid", "error-map", "model-comparison"):
        paper = subparsers.add_parser(command)
        paper.add_argument("--output", type=Path, default=Path("results/paper"))
        paper.add_argument("--cache", type=Path, default=Path("results/cache"))
        paper.add_argument("--figures", type=Path, default=Path("figures/paper"))
        paper.add_argument(
            "--exact-backend",
            choices=("uniform_tempo", "oqupy"),
            default="uniform_tempo",
        )
        if command == "model-comparison":
            paper.add_argument(
                "--full-kac",
                action="store_true",
                help="run cluster-scale timestep and phase refinement for Kac variants",
            )
    paper_check = subparsers.add_parser("paper-audit")
    paper_check.add_argument("directory", type=Path, default=Path("results/paper"))
    heat_valve = subparsers.add_parser("heat-valve")
    heat_valve.add_argument(
        "--output",
        type=Path,
        default=Path("results/heat-valve"),
    )
    heat_valve.add_argument(
        "--cache",
        type=Path,
        default=Path("results/cache/uniform_tempo"),
    )
    heat_valve.add_argument(
        "--figures",
        type=Path,
        default=Path("figures/heat-valve"),
    )
    mode = heat_valve.add_mutually_exclusive_group()
    mode.add_argument("--pilot", action="store_true")
    mode.add_argument("--full", action="store_true")
    heat_check = subparsers.add_parser("heat-valve-audit")
    heat_check.add_argument("directory", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    if arguments.command == "baselines":
        return generate_baselines(arguments.output, arguments.figures, arguments.quick)
    if arguments.command == "audit":
        return audit_results(arguments.directory, arguments.allow_unconverged)
    if arguments.command == "pt-baselines":
        return generate_pt_baselines(arguments.output, arguments.figures)
    if arguments.command == "n3-heat-grid":
        return generate_n3_paper_grid(
            arguments.output,
            arguments.cache,
            arguments.figures,
            arguments.exact_backend,
        )
    if arguments.command == "error-map":
        return generate_error_map(
            arguments.output,
            arguments.cache,
            arguments.figures,
            arguments.exact_backend,
        )
    if arguments.command == "model-comparison":
        return generate_model_comparison(
            arguments.output,
            arguments.cache,
            arguments.figures,
            arguments.exact_backend,
            arguments.full_kac,
        )
    if arguments.command == "paper-audit":
        return paper_audit(arguments.directory)
    if arguments.command == "heat-valve":
        return generate_heat_valve(
            arguments.output,
            arguments.cache,
            arguments.figures,
            full=arguments.full,
        )
    if arguments.command == "heat-valve-audit":
        return heat_valve_audit(arguments.directory)
    return 2


if __name__ == "__main__":
    sys.exit(main())
