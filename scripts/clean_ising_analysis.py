#!/usr/bin/env python3
"""Lyapunov-spectrum and central-charge analysis for the clean Ising transfer."""

import math
import time

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
