#!/usr/bin/env python3
"""Thermodynamic QLQ Lanczos for a band-limited XXX current projector.

The slow two-spin subspace at zero external momentum is the sine-bandlimited
span of translation orbits

    O_r=L^-1/2 sum_x (Sx_x Sy_{x+r}-Sy_x Sx_{x+r}),  r>=1.

This representation removes the finite ring.  The only regulator is the
declared maximum separation used to represent the algebraic 1/r tail of the
band projector.  Sparse translation-orbit Pauli algebra then applies the
microscopic Liouvillian and re-projects after every Lanczos step.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
from scipy.integrate import quad

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.derive_xxx_mori_lanczos import (  # noqa: E402
    Operator,
    _add,
    _inner,
    _liouvillian_translation_reduced,
)


def _sine_projector(cutoff: float, maximum_separation: int) -> np.ndarray:
    r = np.arange(1, maximum_separation + 1, dtype=float)
    difference = r[:, None] - r[None, :]
    total = r[:, None] + r[None, :]
    first = np.empty_like(difference)
    zero = difference == 0.0
    first[zero] = cutoff
    first[~zero] = np.sin(cutoff * difference[~zero]) / difference[~zero]
    return (first - np.sin(cutoff * total) / total) / np.pi


def _projected_current_coefficients(
    cutoff: float, maximum_separation: int
) -> np.ndarray:
    r = np.arange(1, maximum_separation + 1, dtype=float)
    coefficients = np.empty_like(r)
    coefficients[0] = (cutoff - 0.5 * np.sin(2.0 * cutoff)) / np.pi
    tail = r[1:]
    coefficients[1:] = (
        np.sin((tail - 1.0) * cutoff) / (tail - 1.0)
        - np.sin((tail + 1.0) * cutoff) / (tail + 1.0)
    ) / np.pi
    return coefficients


def analytic_bandlimited_first_recurrent(cutoff: float) -> dict[str, float]:
    r"""Evaluate the infinite-tail current norm, force norm, and ``beta1^2``.

    Translation-orbit Pauli algebra makes both quadratic forms banded.  Their
    bulk pieces are diagonal in the half-line sine transform; only the first
    three separation coefficients enter the boundary correction.  This
    removes the maximum-separation regulator for the first recurrent.
    """

    f1 = (cutoff - 0.5 * np.sin(2.0 * cutoff)) / np.pi
    f2 = (np.sin(cutoff) - np.sin(3.0 * cutoff) / 3.0) / np.pi
    f3 = (
        np.sin(2.0 * cutoff) / 2.0
        - np.sin(4.0 * cutoff) / 4.0
    ) / np.pi
    current_norm = 0.125 * f1
    force_bulk = (2.0 / np.pi) * quad(
        lambda p: np.sin(p) ** 2 * 0.25 * (1.0 - np.cos(p)),
        0.0,
        cutoff,
        epsabs=1.0e-14,
        epsrel=1.0e-14,
    )[0]
    force_norm = (
        force_bulk
        - 3.0 / 16.0 * f1**2
        + 1.0 / 8.0 * f1 * f2
        - 1.0 / 16.0 * f2**2
    )
    l2_symbol = lambda p: (
        29.0 / 16.0
        - 19.0 / 8.0 * np.cos(p)
        + 9.0 / 16.0 * np.cos(2.0 * p)
    )
    l2_norm = (2.0 / np.pi) * quad(
        lambda p: np.sin(p) ** 2 * l2_symbol(p),
        0.0,
        cutoff,
        epsabs=1.0e-14,
        epsrel=1.0e-14,
    )[0]
    l2_norm += (
        -89.0 / 64.0 * f1**2
        + 58.0 / 32.0 * f1 * f2
        - 9.0 / 32.0 * f1 * f3
        - 51.0 / 64.0 * f2**2
        + 11.0 / 32.0 * f2 * f3
        - 1.0 / 32.0 * f3**2
    )
    delta1 = -1.5 * f1 + 0.5 * f2
    delta2 = 0.5 * f1 - 0.5 * f2
    projected_l2_norm = 0.125 * (2.0 / np.pi) * quad(
        lambda p: (
            (2.0 - 2.0 * np.cos(p)) * np.sin(p)
            + delta1 * np.sin(p)
            + delta2 * np.sin(2.0 * p)
        )
        ** 2,
        0.0,
        cutoff,
        epsabs=1.0e-14,
        epsrel=1.0e-14,
    )[0]
    ql2_norm = l2_norm - projected_l2_norm
    return {
        "projected_current_norm": float(current_norm),
        "qlp_force_norm": float(force_norm),
        "l2_projected_current_norm": float(l2_norm),
        "pl2_projected_current_norm": float(projected_l2_norm),
        "ql2_projected_current_norm": float(ql2_norm),
        "squared_first_qlq_recurrent": float(ql2_norm / force_norm),
    }


def _orbit_operator(coefficients: np.ndarray) -> Operator:
    operator: Operator = {}
    for separation, coefficient in enumerate(coefficients, start=1):
        _add(operator, ((0, 1), (separation, 2)), 0.25 * coefficient)
        _add(operator, ((0, 2), (separation, 1)), -0.25 * coefficient)
    return operator


def _two_spin_cross_coefficients(
    operator: Operator, maximum_separation: int
) -> np.ndarray:
    output = np.zeros(maximum_separation, dtype=complex)
    for separation in range(1, maximum_separation + 1):
        first = operator.get(((0, 1), (separation, 2)), 0.0j)
        second = operator.get(((0, 2), (separation, 1)), 0.0j)
        output[separation - 1] = 2.0 * (first - second)
    return output


def _project_q(
    operator: Operator,
    projector: np.ndarray,
) -> Operator:
    coefficients = _two_spin_cross_coefficients(operator, projector.shape[0])
    projected = projector @ coefficients
    result = dict(operator)
    for separation, coefficient in enumerate(projected, start=1):
        _add(result, ((0, 1), (separation, 2)), -0.25 * coefficient)
        _add(result, ((0, 2), (separation, 1)), 0.25 * coefficient)
    return result


def _axpy(target: Operator, source: Operator, coefficient: complex) -> None:
    for string, value in source.items():
        _add(target, string, coefficient * value)


def _scaled(operator: Operator, coefficient: complex) -> Operator:
    return {
        string: coefficient * value
        for string, value in operator.items()
        if abs(coefficient * value) > 1.0e-13
    }


def derive(
    cutoff: float,
    maximum_separation: int,
    steps: int,
) -> dict[str, object]:
    if not 0.0 < cutoff < np.pi:
        raise ValueError("cutoff must lie in (0,pi)")
    if maximum_separation < 8 or steps < 1:
        raise ValueError("insufficient separation or Lanczos depth")
    projector = _sine_projector(cutoff, maximum_separation)
    coefficients = _projected_current_coefficients(cutoff, maximum_separation)
    current = _orbit_operator(coefficients)
    current_norm = float(np.real(_inner(current, current)))
    exact_current_norm = float(
        0.125 * (cutoff - 0.5 * np.sin(2.0 * cutoff)) / np.pi
    )
    analytic = analytic_bandlimited_first_recurrent(cutoff)
    force = _project_q(_liouvillian_translation_reduced(current), projector)
    force_norm = float(np.real(_inner(force, force)))
    vector = _scaled(force, 1.0 / np.sqrt(force_norm))
    previous: Operator = {}
    previous_beta = 0.0
    alphas: list[float] = []
    betas: list[float] = []
    counts: list[int] = [len(vector)]
    projection_residuals: list[float] = []
    for _ in range(steps):
        candidate = _project_q(
            _liouvillian_translation_reduced(vector), projector
        )
        alpha = float(np.real(_inner(vector, candidate)))
        _axpy(candidate, vector, -alpha)
        if previous:
            _axpy(candidate, previous, -previous_beta)
        beta_squared = float(np.real(_inner(candidate, candidate)))
        beta = float(np.sqrt(max(beta_squared, 0.0)))
        remaining_p = projector @ _two_spin_cross_coefficients(
            candidate, maximum_separation
        )
        projection_residuals.append(
            float(np.linalg.norm(remaining_p))
            / max(beta, np.finfo(float).tiny)
        )
        alphas.append(alpha)
        betas.append(beta)
        if beta <= 1.0e-13:
            break
        previous, vector = vector, _scaled(candidate, 1.0 / beta)
        previous_beta = beta
        counts.append(len(vector))
    return {
        "schema": 1,
        "method": "thermodynamic_translation_orbit_bandlimited_qlq_lanczos",
        "inputs": {
            "cutoff_wave_number": float(cutoff),
            "maximum_separation": int(maximum_separation),
            "steps": int(steps),
            "trajectory_data_used": False,
            "target_coefficients_used": False,
        },
        "projected_current_norm": current_norm,
        "exact_infinite_tail_projected_current_norm": exact_current_norm,
        "analytic_infinite_tail_first_recurrent": analytic,
        "projected_current_tail_relative_error": float(
            abs(current_norm - exact_current_norm) / exact_current_norm
        ),
        "qlp_force_norm": force_norm,
        "alphas": alphas,
        "betas": betas,
        "squared_betas": [value * value for value in betas],
        "operator_counts": counts,
        "maximum_q_reprojection_residual": max(
            projection_residuals, default=0.0
        ),
        "gates": {
            "positive_force_norm": force_norm > 0.0,
            "positive_recurrents": all(value > 0.0 for value in betas),
            "zero_diagonal_within_tolerance": all(
                abs(value) <= 1.0e-11 for value in alphas
            ),
            "band_tail_resolved": bool(
                abs(current_norm - exact_current_norm) / exact_current_norm
                <= 5.0e-4
            ),
            "analytic_first_recurrent_positive": bool(
                analytic["qlp_force_norm"] > 0.0
                and analytic["ql2_projected_current_norm"] > 0.0
                and analytic["squared_first_qlq_recurrent"] > 0.0
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cutoff", type=float, default=float(np.pi / 4.0))
    parser.add_argument("--maximum-separation", type=int, default=128)
    parser.add_argument("--steps", type=int, default=3)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = derive(args.cutoff, args.maximum_separation, args.steps)
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(encoded, end="")
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
