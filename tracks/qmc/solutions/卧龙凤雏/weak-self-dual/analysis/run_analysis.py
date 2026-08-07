import argparse
import csv
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from analysis.bootstrap import bootstrap_fits
from analysis.data_io import load_run, sha256_file, write_json_atomic
from analysis.diagnostics import (
    fit_stability,
    self_duality_diagnostic,
    width_sampling_diagnostics,
)
from analysis.fitting import evaluate_fit, fit_gamma
from analysis.gates import evaluate_gates
from analysis.plots import make_all_plots
from analysis.report_builder import build_report_document


def analyze_run(run_dir: Path, bootstrap_samples: int, bootstrap_seed: int) -> dict:
    start = time.monotonic()
    loaded = load_run(run_dir)
    widths = loaded.widths.astype(float)
    gamma = np.asarray([loaded.gamma_blocks[int(width)].mean() for width in widths])
    gamma_se = np.asarray(
        [_standard_error(loaded.gamma_blocks[int(width)]) for width in widths]
    )
    gamma_se = np.maximum(gamma_se, np.finfo(float).eps)
    primary_fit = fit_gamma(widths, gamma, gamma_se, 6, "l3")
    fit_samples = bootstrap_fits(
        loaded.gamma_blocks,
        loaded.widths,
        gamma_se,
        samples=bootstrap_samples,
        seed=bootstrap_seed,
    )
    primary_samples = fit_samples["primary"]
    central_charge = float(np.mean(primary_samples))
    central_se = float(np.std(primary_samples, ddof=1))
    ci_low, ci_high = np.percentile(primary_samples, [2.5, 97.5])
    stability = fit_stability(fit_samples)
    sampling = width_sampling_diagnostics(loaded.gamma_blocks)
    sampling_json = {str(width): values for width, values in sampling.items()}
    duality = self_duality_diagnostic(
        loaded.electric_counts, loaded.magnetic_counts, loaded.face_counts
    )
    fitted = evaluate_fit(primary_fit, widths)
    residual = gamma - fitted
    studentized = residual / gamma_se
    residual_trend = (
        float(np.corrcoef(residual, 1.0 / widths)[0, 1])
        if np.std(residual) > 0.0
        else 0.0
    )
    oracle_pass = _oracle_pass(loaded.oracle)
    max_invariant = max(float(values.max()) for values in loaded.invariant_errors.values())
    gates = evaluate_gates(
        ci_low=float(ci_low),
        ci_high=float(ci_high),
        oracle_pass=oracle_pass,
        max_invariant_error=max_invariant,
        invariant_tolerance=float(loaded.config["sampling"]["invariant_tolerance"]),
        self_duality_z=duality["z_score"],
        minimum_ess=min(value["effective_sample_size"] for value in sampling.values()),
        maximum_fit_shift_z=stability["maximum_shift_z"],
        systematic_spread=stability["systematic_spread"],
        maximum_studentized_residual=float(np.max(np.abs(studentized))),
        residual_trend=residual_trend,
        required=bool(loaded.config["production_gates"]),
    )
    fit_variant_summary = {
        name: {
            "mean": float(np.mean(values)),
            "standard_error": float(np.std(values, ddof=1)),
            "ci95": [float(value) for value in np.percentile(values, [2.5, 97.5])],
        }
        for name, values in fit_samples.items()
    }
    analysis_elapsed = time.monotonic() - start
    summary = {
        "schema_version": 1,
        "model": "Born-correlated weak self-dual Majorana network",
        "target_central_charge": 0.447,
        "widths": [int(value) for value in widths],
        "gamma": [float(value) for value in gamma],
        "gamma_standard_error": [float(value) for value in gamma_se],
        "central_charge": central_charge,
        "central_charge_standard_error": central_se,
        "central_charge_ci95": [float(ci_low), float(ci_high)],
        "primary_fit": primary_fit.to_dict(),
        "fit_variants": fit_variant_summary,
        "fit_stability": stability,
        "sampling_diagnostics": sampling_json,
        "self_duality": duality,
        "oracle": loaded.oracle,
        "max_invariant_error": max_invariant,
        "residual_trend": residual_trend,
        "bootstrap_samples": bootstrap_samples,
        "bootstrap_seed": bootstrap_seed,
        "analysis_elapsed_s": analysis_elapsed,
        "gates": gates,
    }
    processed = run_dir / "processed"
    figures = run_dir / "figures"
    processed.mkdir(parents=True, exist_ok=True)
    write_json_atomic(processed / "summary.json", summary)
    write_json_atomic(processed / "gates.json", gates)
    _write_finite_size(processed / "finite_size.csv", widths, gamma, gamma_se, fitted)
    _write_variants(processed / "fit_variants.csv", fit_variant_summary)
    figure_paths = make_all_plots(
        figures_dir=figures,
        widths=widths,
        gamma=gamma,
        gamma_se=gamma_se,
        primary_fit=primary_fit,
        fit_samples=fit_samples,
        sampling=sampling_json,
        self_duality=duality,
    )
    manifest = loaded.manifest
    manifest["python_version"] = platform.python_version()
    manifest["python_requirements_sha256"] = sha256_file(Path(__file__).parent / "requirements.txt")
    manifest["analysis_elapsed_s"] = analysis_elapsed
    for path in [processed / "summary.json", processed / "gates.json", processed / "finite_size.csv", processed / "fit_variants.csv", *figure_paths]:
        manifest["artifact_sha256"][path.stem] = sha256_file(path)
    write_json_atomic(run_dir / "manifest.json", manifest)
    write_json_atomic(run_dir / "report.json", build_report_document(summary, manifest))
    return summary


def _standard_error(values: np.ndarray) -> float:
    stream_means = np.asarray(values).mean(axis=1)
    if len(stream_means) > 1:
        return float(stream_means.std(ddof=1) / np.sqrt(len(stream_means)))
    blocks = np.asarray(values)[0]
    return float(blocks.std(ddof=1) / np.sqrt(len(blocks)))


def _oracle_pass(oracle: dict) -> bool:
    born = oracle["born_enumeration"]
    gauge = oracle["gauge_equivalence"]
    clean = oracle["clean_positive"]
    return (
        born["max_probability_error"] < 1e-11
        and born["max_parity_error"] < 1e-10
        and born["max_covariance_error"] < 1e-10
        and gauge["max_probability_error"] < 1e-11
        and gauge["max_observable_error"] < 1e-10
        and clean["max_covariance_error"] < 1e-10
    )


def _write_finite_size(path, widths, gamma, error, fitted):
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["width", "gamma", "standard_error", "fitted_gamma", "residual"])
        for row in zip(widths, gamma, error, fitted):
            width, observed, standard_error, prediction = row
            writer.writerow([int(width), f"{observed:.17g}", f"{standard_error:.17g}", f"{prediction:.17g}", f"{observed-prediction:.17g}"])


def _write_variants(path, variants):
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["variant", "mean", "standard_error", "ci95_low", "ci95_high"])
        for name, values in variants.items():
            writer.writerow([name, values["mean"], values["standard_error"], *values["ci95"]])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--bootstrap-samples", type=int, default=4000)
    parser.add_argument("--bootstrap-seed", type=int, default=447122)
    parser.add_argument("--renderer", type=Path)
    args = parser.parse_args()
    summary = analyze_run(args.run_dir, args.bootstrap_samples, args.bootstrap_seed)
    if args.renderer:
        subprocess.run([sys.executable, str(args.renderer.resolve()), str(args.run_dir.resolve())], check=True)
    interval = summary["central_charge_ci95"]
    print(
        f"c_eff={summary['central_charge']:.6f} "
        f"SE={summary['central_charge_standard_error']:.6f} "
        f"CI95=[{interval[0]:.6f}, {interval[1]:.6f}] "
        f"required_gates_pass={summary['gates']['all_required_pass']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
