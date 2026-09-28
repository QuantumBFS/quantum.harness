#!/usr/bin/env python3
"""Exact first dynamical split of the XXX long-wave current subspace.

For each declared momentum cutoff this script constructs all ordered spin
bilinears whose two Fourier legs are slow, performs the exact infinite-
temperature Kubo projection of the microscopic bond current, and evaluates
``G0=(B,B)``, ``G1=(B,L B)``, and ``G2=(L B,L B)`` in sparse Pauli space.
The resulting ``P L P`` norm and positive ``Q L P`` leakage are microscopic
inputs to a no-double-counting Mori/F-GHD match.  No trajectory or target
Burgers coefficient is used.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.derive_xxx_mori_lanczos import (
    Operator,
    _add,
    _inner,
    _liouvillian,
    fourier_bond_current,
)
from scripts.derive_xxx_slow_current_projector import (
    _wrapped_mode,
    bond_current_bilinear_operator,
    bond_current_bilinear_gram,
    slow_bilinear_dynamical_matrices,
)


def _real_quadratic(left: np.ndarray, matrix: np.ndarray, right: np.ndarray) -> float:
    return float(np.real(np.vdot(left, matrix @ right)))


def _generalized_hermitian_eigenvalues(
    operator: np.ndarray, metric: np.ndarray
) -> np.ndarray:
    values, vectors = np.linalg.eigh(metric)
    retained = values > 1.0e-12
    root_inverse = vectors[:, retained] / np.sqrt(values[retained])[None, :]
    reduced = root_inverse.conj().T @ operator @ root_inverse
    return np.linalg.eigvalsh(0.5 * (reduced + reduced.conj().T))


def _operator_axpy(target: Operator, source: Operator, coefficient: complex) -> None:
    for string, value in source.items():
        _add(target, string, coefficient * value)


def _operator_scaled(operator: Operator, coefficient: complex) -> Operator:
    return {
        string: coefficient * value
        for string, value in operator.items()
        if abs(coefficient * value) > 1.0e-13
    }


def projected_qlq_lanczos(
    length: int,
    external_mode: int,
    cutoff_mode: int,
    steps: int,
) -> dict[str, object]:
    r"""Lanczos-expand the exact ``Q L Q`` spectrum seen by ``Q L Pj``."""

    if steps < 1:
        raise ValueError("steps must be positive")
    selected = tuple(
        p
        for p in range(length)
        if _wrapped_mode(p, length) <= cutoff_mode
        and _wrapped_mode(external_mode - p, length) <= cutoff_mode
    )
    basis = [
        bond_current_bilinear_operator(length, external_mode, mode)
        for mode in selected
    ]
    gram = bond_current_bilinear_gram(length, external_mode)
    g0 = gram[np.ix_(selected, selected)]
    inverse = np.linalg.pinv(g0, rcond=1.0e-12)
    overlap = (gram @ np.ones(length, dtype=complex))[list(selected)]
    coefficients = inverse @ overlap

    def project_q(operator: Operator) -> Operator:
        overlaps = np.asarray([_inner(item, operator) for item in basis])
        projected_coefficients = inverse @ overlaps
        result = dict(operator)
        for coefficient, item in zip(projected_coefficients, basis, strict=True):
            _operator_axpy(result, item, -coefficient)
        return result

    projected_current: Operator = {}
    for coefficient, item in zip(coefficients, basis, strict=True):
        _operator_axpy(projected_current, item, coefficient)
    force = project_q(_liouvillian(projected_current, length))
    force_norm = float(np.real(_inner(force, force)))
    if force_norm <= 0.0:
        raise RuntimeError("QLP force has zero norm")
    current = _operator_scaled(force, 1.0 / np.sqrt(force_norm))
    previous: Operator = {}
    previous_beta = 0.0
    alphas: list[float] = []
    betas: list[float] = []
    operator_counts: list[int] = [len(current)]
    q_orthogonality_residuals: list[float] = []
    for _ in range(steps):
        candidate = project_q(_liouvillian(current, length))
        alpha = float(np.real(_inner(current, candidate)))
        _operator_axpy(candidate, current, -alpha)
        if previous:
            _operator_axpy(candidate, previous, -previous_beta)
        beta_squared = float(np.real(_inner(candidate, candidate)))
        if beta_squared < -1.0e-11:
            raise RuntimeError("negative Lanczos norm")
        beta = float(np.sqrt(max(beta_squared, 0.0)))
        q_overlap = np.asarray([_inner(item, candidate) for item in basis])
        q_orthogonality_residuals.append(
            float(np.linalg.norm(q_overlap))
            / max(beta, np.finfo(float).tiny)
        )
        alphas.append(alpha)
        betas.append(beta)
        if beta <= 1.0e-13:
            break
        previous, current = current, _operator_scaled(candidate, 1.0 / beta)
        previous_beta = beta
        operator_counts.append(len(current))
    return {
        "length": int(length),
        "external_mode": int(external_mode),
        "cutoff_mode": int(cutoff_mode),
        "cutoff_wave_number": float(2.0 * np.pi * cutoff_mode / length),
        "selected_modes": list(selected),
        "qlp_force_norm": force_norm,
        "alphas": alphas,
        "betas": betas,
        "squared_betas": [value * value for value in betas],
        "operator_counts": operator_counts,
        "maximum_q_orthogonality_residual": max(
            q_orthogonality_residuals, default=0.0
        ),
        "trajectory_data_used": False,
        "target_coefficients_used": False,
    }


def derive(
    length: int,
    external_mode: int,
    cutoff_modes: tuple[int, ...],
) -> dict[str, object]:
    full_gram = bond_current_bilinear_gram(length, external_mode)
    full_overlap = full_gram @ np.ones(length, dtype=complex)
    _, current = fourier_bond_current(length, external_mode)
    evolved_current = _liouvillian(current, length)
    full_current_norm = float(np.real(_inner(current, current)))
    full_evolved_current_norm = float(
        np.real(_inner(evolved_current, evolved_current))
    )
    rows: list[dict[str, object]] = []
    for cutoff in sorted(set(cutoff_modes)):
        selected = tuple(
            p
            for p in range(length)
            if _wrapped_mode(p, length) <= cutoff
            and _wrapped_mode(external_mode - p, length) <= cutoff
        )
        dynamic = slow_bilinear_dynamical_matrices(
            length, external_mode, selected
        )
        g0 = np.asarray(dynamic["gram"])
        g1 = np.asarray(dynamic["liouvillian_gram"])
        g2 = np.asarray(dynamic["liouvillian_norm_gram"])
        overlap = full_overlap[list(selected)]
        inverse = np.linalg.pinv(g0, rcond=1.0e-12)
        coefficients = inverse @ overlap
        projected_norm = _real_quadratic(coefficients, g0, coefficients)
        projected_l_norm = _real_quadratic(coefficients, g2, coefficients)
        projected_l_overlap = g1 @ coefficients
        plp_coefficients = inverse @ projected_l_overlap
        plp_norm = _real_quadratic(plp_coefficients, g0, plp_coefficients)
        qlp_norm = projected_l_norm - plp_norm
        mean_frequency = (
            _real_quadratic(coefficients, g1, coefficients) / projected_norm
            if projected_norm > 0.0
            else 0.0
        )
        second_frequency_moment = (
            projected_l_norm / projected_norm if projected_norm > 0.0 else 0.0
        )
        generalized = _generalized_hermitian_eigenvalues(g1, g0)
        rows.append(
            {
                "cutoff_mode": int(cutoff),
                "cutoff_wave_number": float(2.0 * np.pi * cutoff / length),
                "selected_modes": list(selected),
                "selected_rank": int(np.linalg.matrix_rank(g0, tol=1.0e-12)),
                "projected_current_norm": projected_norm,
                "projected_fraction_of_full_current": projected_norm
                / full_current_norm,
                "projected_liouvillian_norm": projected_l_norm,
                "plp_liouvillian_norm": plp_norm,
                "qlp_leakage_norm": qlp_norm,
                "qlp_fraction_of_projected_liouvillian_norm": (
                    qlp_norm / projected_l_norm if projected_l_norm > 0.0 else 0.0
                ),
                "projected_mean_liouvillian_frequency": mean_frequency,
                "projected_second_frequency_moment": second_frequency_moment,
                "plp_generalized_frequency_minimum": float(np.min(generalized)),
                "plp_generalized_frequency_maximum": float(np.max(generalized)),
                "g0_analytic_residual": dynamic[
                    "maximum_g0_analytic_residual"
                ],
            }
        )
    minimum_leakage = min(row["qlp_leakage_norm"] for row in rows)
    return {
        "schema": 1,
        "method": "exact_sparse_pauli_slow_bilinear_plp_qlp_split",
        "inputs": {
            "length": int(length),
            "external_mode": int(external_mode),
            "cutoff_modes": sorted(set(cutoff_modes)),
            "temperature": "infinite",
            "trajectory_data_used": False,
            "target_coefficients_used": False,
        },
        "external_wave_number": float(2.0 * np.pi * external_mode / length),
        "full_current_norm": full_current_norm,
        "full_liouvillian_current_norm": full_evolved_current_norm,
        "rows": rows,
        "gates": {
            "exact_full_current_norm": bool(
                abs(full_current_norm - 0.125) <= 1.0e-12
            ),
            "all_static_projector_norms_bounded": bool(
                all(
                    0.0 <= row["projected_current_norm"]
                    <= full_current_norm + 1.0e-12
                    for row in rows
                )
            ),
            "all_qlp_leakage_norms_nonnegative": bool(
                minimum_leakage >= -1.0e-11
            ),
            "all_analytic_gram_residuals_small": bool(
                all(row["g0_analytic_residual"] <= 1.0e-11 for row in rows)
            ),
        },
        "interpretation": (
            "A nonzero QLP leakage proves that the selected long-wave bilinear "
            "sector is not dynamically closed.  Its eliminated spectrum is a "
            "Mori continuum unless an independently controlled rational "
            "approximation is introduced."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--length", type=int, default=24)
    parser.add_argument("--external-mode", type=int, default=1)
    parser.add_argument(
        "--cutoff-modes", type=int, nargs="+", default=[1, 2, 3, 4, 6, 8, 11]
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = derive(args.length, args.external_mode, tuple(args.cutoff_modes))
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(encoded, end="")
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
