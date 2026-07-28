#!/usr/bin/env python3
"""Lyapunov-spectrum and central-charge analysis for the clean Ising transfer."""

import argparse
import csv
import json
import math
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.sparse.linalg import eigsh

try:
    from clean_ising_transfer import IsingTransferOperator, critical_coupling
except ImportError:  # imported from the repository root during tests
    from scripts.clean_ising_transfer import IsingTransferOperator, critical_coupling


def clean_lyapunov_spectrum(L, count=4, tol=1e-11):
    """Return the leading clean Lyapunov exponents ell_a = log(lambda_a)."""
    operator = IsingTransferOperator(L, critical_coupling(), critical_coupling())
    if count < 1 or count >= operator.dimension:
        raise ValueError("count must satisfy 1 <= count < 2**L")
    rng = np.random.default_rng(0)
    start_vector = rng.standard_normal(operator.dimension)
    start_vector /= np.linalg.norm(start_vector)
    ncv = min(max(2 * count + 1, 16), operator.dimension - 1)

    start = time.perf_counter()
    values, vectors = eigsh(
        operator,
        k=count,
        which="LA",
        v0=start_vector,
        ncv=ncv,
        tol=tol,
    )
    runtime_seconds = time.perf_counter() - start

    order = np.argsort(values)[::-1]
    values = np.asarray(values[order], dtype=float)
    vectors = np.asarray(vectors[:, order], dtype=float)
    if np.any(values <= 0.0) or not np.all(np.isfinite(values)):
        raise RuntimeError(f"non-positive or non-finite eigenvalue at L={L}")

    residuals = []
    for index, value in enumerate(values):
        vector = vectors[:, index]
        residual = np.linalg.norm(operator @ vector - value * vector) / abs(value)
        residuals.append(float(residual))
    if not np.all(np.isfinite(residuals)) or max(residuals) > 10.0 * tol:
        raise RuntimeError(f"unconverged clean spectrum at L={L}: {residuals}")

    return {
        "L": int(L),
        "dimension": operator.dimension,
        "lambda": values,
        "ell": np.log(values),
        "residuals": residuals,
        "runtime_seconds": runtime_seconds,
    }


def leading_lyapunov_iteration(L, steps=120, burn_in=40):
    """Estimate ell_1 from repeated transfer and scalar QR normalization."""
    if burn_in < 0 or steps <= burn_in:
        raise ValueError("require steps > burn_in >= 0")
    operator = IsingTransferOperator(L, critical_coupling(), critical_coupling())
    vector = np.ones(operator.dimension, dtype=float)
    vector /= np.linalg.norm(vector)
    increments = []
    start = time.perf_counter()

    for step in range(steps):
        vector = operator @ vector
        norm = float(np.linalg.norm(vector))
        if not math.isfinite(norm) or norm <= 0.0:
            raise RuntimeError(f"invalid transfer norm at L={L}, step={step}")
        vector /= norm
        if step >= burn_in:
            increments.append(math.log(norm))

    runtime_seconds = time.perf_counter() - start
    return {
        "L": int(L),
        "ell1": float(np.mean(increments)),
        "samples": len(increments),
        "increment_std": float(np.std(increments, ddof=1)) if len(increments) > 1 else 0.0,
        "runtime_seconds": runtime_seconds,
    }


def fit_transfer_energy(sizes, energies, powers=(1, 3), lmin=8):
    """Fit epsilon_0(L) = A L + sum_p b_p L^-p and extract c from b_1."""
    sizes = np.asarray(sizes, dtype=float)
    energies = np.asarray(energies, dtype=float)
    powers = tuple(int(power) for power in powers)
    if sizes.ndim != 1 or energies.shape != sizes.shape:
        raise ValueError("sizes and energies must be one-dimensional arrays of equal length")
    if 1 not in powers or len(set(powers)) != len(powers):
        raise ValueError("powers must be distinct and include 1")

    mask = sizes >= float(lmin)
    selected_sizes = sizes[mask]
    selected_energies = energies[mask]
    columns = [selected_sizes] + [selected_sizes ** (-power) for power in powers]
    design = np.column_stack(columns)
    if design.shape[0] < design.shape[1]:
        raise ValueError("not enough sizes for the requested finite-size fit")

    coefficients, _, rank, _ = np.linalg.lstsq(design, selected_energies, rcond=None)
    if rank != design.shape[1]:
        raise RuntimeError("rank-deficient central-charge fit")
    residual = selected_energies - design @ coefficients
    inverse_size_coefficient = coefficients[1 + powers.index(1)]

    return {
        "lmin": int(lmin),
        "powers": list(powers),
        "sizes": [int(size) for size in selected_sizes],
        "coefficients": [float(value) for value in coefficients],
        "central_charge": float(-6.0 * inverse_size_coefficient / math.pi),
        "residual_norm": float(np.linalg.norm(residual)),
    }


def central_charge_summary(sizes, energies):
    """Return the primary clean-Ising fit and a deterministic stability envelope."""
    fits = {
        "primary_L8_p13": fit_transfer_energy(sizes, energies, powers=(1, 3), lmin=8),
        "drop_L8_p13": fit_transfer_energy(sizes, energies, powers=(1, 3), lmin=10),
        "all_L_p135": fit_transfer_energy(sizes, energies, powers=(1, 3, 5), lmin=8),
    }
    charges = [fit["central_charge"] for fit in fits.values()]
    lower = min(charges)
    upper = max(charges)
    fits["reported"] = {
        "lower": float(lower),
        "upper": float(upper),
        "midpoint": float(0.5 * (lower + upper)),
        "half_width": float(0.5 * (upper - lower)),
        "interpretation": "finite-size fit envelope, not a statistical error bar",
    }
    return fits


def write_analysis_artifacts(rows, output_dir):
    """Write the spectrum table, central-charge fits, and finite-size plot."""
    if not rows:
        raise ValueError("rows must not be empty")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    csv_path = output_dir / "lyapunov_spectrum.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    sizes = np.asarray([row["L"] for row in rows], dtype=float)
    energies = -np.asarray([row["ell_1"] for row in rows], dtype=float)
    summary = central_charge_summary(sizes, energies)
    json_path = output_dir / "central_charge_fit.json"
    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, sort_keys=True)
        handle.write("\n")

    primary = summary["primary_L8_p13"]
    coefficients = primary["coefficients"]
    grid = np.linspace(float(np.min(sizes)), float(np.max(sizes)), 400)
    fitted_energy = sum(
        coefficient * column
        for coefficient, column in zip(
            coefficients,
            [grid] + [grid ** (-power) for power in primary["powers"]],
        )
    )
    reported = summary["reported"]

    figure, axis = plt.subplots(figsize=(6.4, 4.4))
    axis.scatter(1.0 / sizes**2, energies / sizes, color="tab:blue", zorder=3, label="matrix-free data")
    axis.plot(1.0 / grid**2, fitted_energy / grid, color="tab:orange", label=r"fit: $L^{-1}+L^{-3}$")
    axis.set_xlabel(r"$1/L^2$")
    axis.set_ylabel(r"$\epsilon_0(L)/L$")
    axis.set_title("Critical clean Ising central charge")
    axis.grid(alpha=0.25)
    axis.legend()
    axis.text(
        0.04,
        0.08,
        rf"$c={reported['midpoint']:.7f}\pm{reported['half_width']:.1e}$" + "\n(fit envelope)",
        transform=axis.transAxes,
    )
    figure.tight_layout()
    figure.savefig(output_dir / "central_charge_fit.png", dpi=180)
    plt.close(figure)
    return summary


def run_analysis(sizes, count=4, tol=1e-11, qr_steps=120, qr_burn_in=40, output_dir=None):
    """Compute clean spectra and write all analysis artifacts."""
    rows = []
    for L in sizes:
        print(f"L={L}: computing {count} leading eigenvalues", flush=True)
        spectrum = clean_lyapunov_spectrum(L, count=count, tol=tol)
        leading_check = leading_lyapunov_iteration(L, steps=qr_steps, burn_in=qr_burn_in)
        row = {
            "L": int(L),
            "dimension": int(spectrum["dimension"]),
        }
        for index in range(count):
            suffix = index + 1
            row[f"lambda_{suffix}"] = float(spectrum["lambda"][index])
            row[f"ell_{suffix}"] = float(spectrum["ell"][index])
            row[f"residual_{suffix}"] = float(spectrum["residuals"][index])
        row.update(
            {
                "qr_ell1": float(leading_check["ell1"]),
                "qr_abs_error": abs(float(leading_check["ell1"] - spectrum["ell"][0])),
                "spectrum_runtime_seconds": float(spectrum["runtime_seconds"]),
                "qr_runtime_seconds": float(leading_check["runtime_seconds"]),
            }
        )
        rows.append(row)
        print(
            f"L={L}: ell_1={row['ell_1']:.12f}, "
            f"QR error={row['qr_abs_error']:.3e}, "
            f"residual max={max(spectrum['residuals']):.3e}",
            flush=True,
        )

    if output_dir is None:
        output_dir = Path("results") / "clean_ising_transfer"
    summary = write_analysis_artifacts(rows, output_dir)
    reported = summary["reported"]
    print(
        f"central charge = {reported['midpoint']:.10f} +/- "
        f"{reported['half_width']:.3e} (finite-size fit envelope)",
        flush=True,
    )
    return rows, summary


def _parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", nargs="+", type=int, default=[8, 10, 12, 16, 20])
    parser.add_argument("--count", type=int, default=4)
    parser.add_argument("--tol", type=float, default=1e-11)
    parser.add_argument("--qr-steps", type=int, default=120)
    parser.add_argument("--qr-burn-in", type=int, default=40)
    parser.add_argument("--output-dir", type=Path, default=Path("results/clean_ising_transfer"))
    return parser.parse_args()


if __name__ == "__main__":
    arguments = _parse_args()
    run_analysis(
        arguments.sizes,
        count=arguments.count,
        tol=arguments.tol,
        qr_steps=arguments.qr_steps,
        qr_burn_in=arguments.qr_burn_in,
        output_dir=arguments.output_dir,
    )
