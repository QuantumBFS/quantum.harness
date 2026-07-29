import argparse
import csv
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from analysis.bootstrap import hierarchical_mean_bootstrap
from analysis.data_io import load_run, sha256_file, write_json_atomic
from analysis.fitting import evaluate_fit, fit_free_energy
from analysis.gates import evaluate_gates
from analysis.plots import make_all_plots
from analysis.report_builder import build_report_document


def analyze_run(run_dir: Path, bootstrap_samples: int, bootstrap_seed: int) -> dict:
    start = time.monotonic()
    loaded = load_run(run_dir)
    widths = loaded.widths
    tensor = loaded.block_tensor
    phi = tensor.mean(axis=(0, 1))
    phi_se = _phi_standard_error(tensor)

    primary_fit = fit_free_energy(widths, phi, minimum_width=4)
    diagnostic_fit = fit_free_energy(widths, phi, minimum_width=6)
    phi_bootstrap = hierarchical_mean_bootstrap(
        tensor, samples=bootstrap_samples, seed=bootstrap_seed
    )
    primary_bootstrap = _fit_samples(widths, phi_bootstrap, minimum_width=4)
    diagnostic_bootstrap = _fit_samples(widths, phi_bootstrap, minimum_width=6)
    primary_se = float(np.std(primary_bootstrap, ddof=1))
    ci_low, ci_high = np.percentile(primary_bootstrap, [2.5, 97.5])

    stability = _stability_diagnostics(
        tensor=tensor,
        widths=widths,
        samples=bootstrap_samples,
        seed=bootstrap_seed + 100,
        primary_c=primary_fit.central_charge,
        primary_se=primary_se,
    )
    identity = loaded.oracle["nishimori_energy_identity"]
    bond = _bond_diagnostic(loaded)
    runtime_before_analysis = sum(
        float(loaded.manifest.get(key) or 0.0)
        for key in ("oracle_elapsed_s", "simulation_elapsed_s")
    )

    processed_dir = run_dir / "processed"
    figures_dir = run_dir / "figures"
    processed_dir.mkdir(parents=True, exist_ok=True)
    figure_paths = make_all_plots(
        figures_dir=figures_dir,
        widths=widths,
        phi=phi,
        phi_se=phi_se,
        primary_fit=primary_fit,
        diagnostic_fit=diagnostic_fit,
        primary_bootstrap=primary_bootstrap,
        diagnostic_bootstrap=diagnostic_bootstrap,
        stability=stability,
        identity=identity,
        bond=bond,
    )

    analysis_elapsed = time.monotonic() - start
    runtime_s = runtime_before_analysis + analysis_elapsed
    gates = evaluate_gates(
        central_charge=primary_fit.central_charge,
        standard_error=primary_se,
        ci_low=float(ci_low),
        ci_high=float(ci_high),
        diagnostic_central_charge=diagnostic_fit.central_charge,
        half_stability_z=stability["half_stability_z"],
        replica_stability_z=stability["replica_stability_z"],
        identity_error=float(identity["absolute_error"]),
        negative_bond_z=bond["z_score"],
        runtime_s=runtime_s,
        required=bool(loaded.config["production_gates"]),
    )
    summary = {
        "schema_version": 1,
        "model": "two-dimensional +/-J random-bond Ising model",
        "line": "Nishimori",
        "target_central_charge": 0.464,
        "widths": [int(width) for width in widths],
        "replicas": int(tensor.shape[0]),
        "blocks_per_replica": int(tensor.shape[1]),
        "bootstrap_samples": bootstrap_samples,
        "bootstrap_seed": bootstrap_seed,
        "phi": [float(value) for value in phi],
        "phi_standard_error": [float(value) for value in phi_se],
        "primary_fit": primary_fit.to_dict(),
        "diagnostic_fit": diagnostic_fit.to_dict(),
        "central_charge_standard_error": primary_se,
        "central_charge_ci95": [float(ci_low), float(ci_high)],
        "stability": stability,
        "nishimori_energy_identity": identity,
        "bond_frequency": bond,
        "runtime_s": runtime_s,
        "gates": gates,
    }
    summary_path = processed_dir / "summary.json"
    gates_path = processed_dir / "gates.json"
    write_json_atomic(summary_path, summary)
    write_json_atomic(gates_path, gates)
    _write_free_energy_csv(
        processed_dir / "free_energy.csv",
        widths,
        phi,
        phi_se,
        primary_fit,
    )
    _write_bootstrap_csv(
        processed_dir / "central_charge_bootstrap.csv",
        primary_bootstrap,
        diagnostic_bootstrap,
    )

    manifest = loaded.manifest
    manifest["python_version"] = platform.python_version()
    manifest["python_requirements_sha256"] = sha256_file(
        Path(__file__).parent / "requirements.txt"
    )
    manifest["analysis_elapsed_s"] = analysis_elapsed
    manifest["total_elapsed_s"] = runtime_s
    for key, path in [
        ("summary", summary_path),
        ("gates", gates_path),
        ("free-energy-csv", processed_dir / "free_energy.csv"),
        ("bootstrap-csv", processed_dir / "central_charge_bootstrap.csv"),
    ]:
        manifest["artifact_sha256"][key] = sha256_file(path)
    for path in figure_paths:
        manifest["artifact_sha256"][f"figure-{path.stem}"] = sha256_file(path)
    write_json_atomic(run_dir / "manifest.json", manifest)
    return summary


def _fit_samples(
    widths: np.ndarray, phi_samples: np.ndarray, minimum_width: int
) -> np.ndarray:
    return np.asarray(
        [
            fit_free_energy(widths, sample, minimum_width).central_charge
            for sample in phi_samples
        ],
        dtype=float,
    )


def _phi_standard_error(tensor: np.ndarray) -> np.ndarray:
    replica_means = tensor.mean(axis=1)
    if tensor.shape[0] > 1:
        return replica_means.std(axis=0, ddof=1) / np.sqrt(tensor.shape[0])
    return tensor[0].std(axis=0, ddof=1) / np.sqrt(tensor.shape[1])


def _stability_diagnostics(
    *,
    tensor: np.ndarray,
    widths: np.ndarray,
    samples: int,
    seed: int,
    primary_c: float,
    primary_se: float,
) -> dict:
    block_count = tensor.shape[1]
    if block_count < 2:
        raise ValueError("stability diagnostics require at least two blocks")
    midpoint = block_count // 2
    halves = [tensor[:, :midpoint], tensor[:, midpoint:]]
    half_c = [
        fit_free_energy(widths, half.mean(axis=(0, 1)), 4).central_charge
        for half in halves
    ]
    half_bootstrap = [
        _fit_samples(
            widths,
            hierarchical_mean_bootstrap(
                half, samples=samples, seed=seed + half_index
            ),
            4,
        )
        for half_index, half in enumerate(halves)
    ]
    half_denominator = np.hypot(
        np.std(half_bootstrap[0], ddof=1),
        np.std(half_bootstrap[1], ddof=1),
    )
    half_z = abs(half_c[0] - half_c[1]) / max(float(half_denominator), 1.0e-15)

    if tensor.shape[0] < 2:
        raise ValueError("replica stability requires at least two replicas")
    leave_one_out = [
        fit_free_energy(widths, np.delete(tensor, replica, axis=0).mean(axis=(0, 1)), 4)
        .central_charge
        for replica in range(tensor.shape[0])
    ]
    replica_z = max(abs(value - primary_c) for value in leave_one_out) / max(
        primary_se, 1.0e-15
    )
    return {
        "half_central_charges": [float(value) for value in half_c],
        "half_stability_z": float(half_z),
        "leave_one_replica_out": [float(value) for value in leave_one_out],
        "replica_stability_z": float(replica_z),
    }


def _bond_diagnostic(loaded) -> dict:
    probability = float(loaded.config["antiferromagnetic_probability"])
    trials = loaded.total_bonds
    if trials <= 0:
        raise ValueError("bond-frequency diagnostic requires sampled bonds")
    observed = loaded.negative_bonds / trials
    standard_error = np.sqrt(probability * (1.0 - probability) / trials)
    return {
        "negative_bonds": loaded.negative_bonds,
        "total_bonds": trials,
        "observed_probability": float(observed),
        "expected_probability": probability,
        "standard_error": float(standard_error),
        "z_score": float((observed - probability) / standard_error),
    }


def _write_free_energy_csv(
    path: Path,
    widths: np.ndarray,
    phi: np.ndarray,
    phi_se: np.ndarray,
    fit,
) -> None:
    fitted = evaluate_fit(fit, widths)
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["width", "phi", "standard_error", "fitted_phi", "residual"])
        for values in zip(widths, phi, phi_se, fitted):
            width, observed, standard_error, predicted = values
            writer.writerow(
                [
                    int(width),
                    f"{observed:.17g}",
                    f"{standard_error:.17g}",
                    f"{predicted:.17g}",
                    f"{observed - predicted:.17g}",
                ]
            )


def _write_bootstrap_csv(
    path: Path, primary: np.ndarray, diagnostic: np.ndarray
) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["sample", "c_lmin4", "c_lmin6"])
        for index, (first, second) in enumerate(zip(primary, diagnostic)):
            writer.writerow([index, f"{first:.17g}", f"{second:.17g}"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--bootstrap-samples", type=int, default=4_000)
    parser.add_argument("--bootstrap-seed", type=int, default=464_122)
    parser.add_argument("--renderer", type=Path, required=True)
    arguments = parser.parse_args()
    summary = analyze_run(
        arguments.run_dir,
        bootstrap_samples=arguments.bootstrap_samples,
        bootstrap_seed=arguments.bootstrap_seed,
    )
    manifest = json.loads((arguments.run_dir / "manifest.json").read_text())
    document = build_report_document(summary, manifest)
    write_json_atomic(arguments.run_dir / "report.json", document)
    subprocess.run(
        [sys.executable, str(arguments.renderer.resolve()), str(arguments.run_dir.resolve())],
        check=True,
    )
    fit = summary["primary_fit"]
    interval = summary["central_charge_ci95"]
    print(
        f"c_eff={fit['central_charge']:.6f} "
        f"SE={summary['central_charge_standard_error']:.6f} "
        f"CI95=[{interval[0]:.6f}, {interval[1]:.6f}] "
        f"required_gates_pass={summary['gates']['all_required_pass']}"
    )


if __name__ == "__main__":
    main()
