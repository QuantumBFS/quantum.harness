#!/usr/bin/env python3
"""Finite-size central-charge analysis for random-bond Ising transfer strips."""

import math

import numpy as np


def fit_central_charge(
    sizes,
    free_energies,
    errors,
    include_l4=True,
    lmin=8,
):
    """Fit f_L=f_inf-pi*c/(6 L^2)+a/L^4 with known standard errors."""
    sizes = np.asarray(sizes, dtype=float)
    values = np.asarray(free_energies, dtype=float)
    errors = np.asarray(errors, dtype=float)
    if sizes.ndim != 1 or values.shape != sizes.shape or errors.shape != sizes.shape:
        raise ValueError("sizes, free_energies, and errors must have equal 1D shapes")
    if not np.all(np.isfinite(sizes)) or not np.all(np.isfinite(values)):
        raise ValueError("sizes and free energies must be finite")
    if not np.all(np.isfinite(errors)) or np.any(errors <= 0.0):
        raise ValueError("errors must be finite and positive")

    mask = sizes >= float(lmin)
    selected = sizes[mask]
    columns = [np.ones_like(selected), selected**-2]
    if include_l4:
        columns.append(selected**-4)
    design = np.column_stack(columns)
    if design.shape[0] < design.shape[1]:
        raise ValueError("not enough sizes for the requested fit")

    weighted_design = design / errors[mask, None]
    weighted_values = values[mask] / errors[mask]
    coefficients, _, rank, _ = np.linalg.lstsq(
        weighted_design, weighted_values, rcond=None
    )
    if rank != design.shape[1]:
        raise RuntimeError("rank-deficient central-charge fit")
    covariance = np.linalg.inv(weighted_design.T @ weighted_design)
    residual = values[mask] - design @ coefficients
    charge = -6.0 * coefficients[1] / math.pi
    charge_se = 6.0 * math.sqrt(covariance[1, 1]) / math.pi
    return {
        "sizes": selected.astype(int).tolist(),
        "include_l4": bool(include_l4),
        "coefficients": [float(value) for value in coefficients],
        "central_charge": float(charge),
        "central_charge_linear_se": float(charge_se),
        "weighted_residual_norm": float(np.linalg.norm(residual / errors[mask])),
    }


def estimate_required_rows(strip_result, target_free_energy_se):
    """Project retained rows and wall time using standard-error squared scaling."""
    target_free_energy_se = float(target_free_energy_se)
    if not math.isfinite(target_free_energy_se) or target_free_energy_se <= 0.0:
        raise ValueError("target_free_energy_se must be finite and positive")
    measured_se = float(strip_result["free_energy_se"])
    if not math.isfinite(measured_se) or measured_se < 0.0:
        raise ValueError("strip free_energy_se must be finite and nonnegative")

    ratio = measured_se / target_free_energy_se
    raw_rows = int(strip_result["retained_rows"]) * max(1.0, ratio * ratio)
    block = int(strip_result["block_length"])
    required = int(math.ceil(raw_rows / block) * block)
    measured_rows = int(strip_result["burn_in"]) + int(strip_result["retained_rows"])
    projected_rows = int(strip_result["burn_in"]) + required
    return {
        "L": int(strip_result.get("L", 0)),
        "required_retained_rows": required,
        "projected_runtime_seconds": float(strip_result["runtime_seconds"])
        * projected_rows
        / measured_rows,
    }


def central_charge_summary(strip_results, bootstrap_samples, seed):
    """Return three fit forms and a block-bootstrap error for the primary fit."""
    if len(strip_results) < 5:
        raise ValueError("five widths are required for the central-charge summary")
    bootstrap_samples = int(bootstrap_samples)
    if bootstrap_samples < 2:
        raise ValueError("bootstrap_samples must be at least two")

    sizes = np.asarray([item["L"] for item in strip_results], dtype=float)
    values = np.asarray([item["free_energy"] for item in strip_results], dtype=float)
    errors = np.asarray([item["free_energy_se"] for item in strip_results], dtype=float)
    fits = {
        "primary_L8_l24": fit_central_charge(sizes, values, errors, True, 8),
        "all_L_l2": fit_central_charge(sizes, values, errors, False, 8),
        "drop_L8_l24": fit_central_charge(sizes, values, errors, True, 10),
    }

    rng = np.random.default_rng(seed)
    bootstrap_charges = []
    for _ in range(bootstrap_samples):
        sampled_values = []
        for item in strip_results:
            blocks = np.asarray(item["block_log_norm_means"], dtype=float)
            if blocks.ndim != 1 or len(blocks) < 2 or not np.all(np.isfinite(blocks)):
                raise ValueError("each width requires at least two finite block means")
            sampled = rng.choice(blocks, size=len(blocks), replace=True)
            sampled_values.append(-float(np.mean(sampled)) / item["L"])
        bootstrap_charges.append(
            fit_central_charge(sizes, sampled_values, errors, True, 8)[
                "central_charge"
            ]
        )

    deterministic = [fit["central_charge"] for fit in fits.values()]
    fits["reported"] = {
        "central_charge": fits["primary_L8_l24"]["central_charge"],
        "bootstrap_se": float(np.std(bootstrap_charges, ddof=1)),
        "fit_envelope_lower": float(min(deterministic)),
        "fit_envelope_upper": float(max(deterministic)),
        "bootstrap_samples": bootstrap_samples,
    }
    return fits
