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
