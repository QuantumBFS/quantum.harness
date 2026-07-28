"""Parity-resolved traces inside one Majorana reflection-positive cone.

The ordinary Majorana reflection-positivity theorem controls the full Fock
trace.  This module resolves the same trace into its even- and odd-fermion
parity sectors so that a possible dimension-dependent sector refinement can be
tested without losing the Spin-representation sign.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math

import numpy as np
from scipy.linalg import expm

from .majorana import (
    majorana_operators,
    quadratic_operator,
    random_reflection_generator,
)


_CLASSIFICATIONS = ("positive", "negative", "complex", "uncertain")


@dataclass(frozen=True)
class ParityTraceResult:
    """Normalized even, odd, and total Fock traces for one time history."""

    even: complex
    odd: complex
    total: complex
    even_classification: str
    odd_classification: str
    total_classification: str
    log_scale: float


def protected_sector(modes: int) -> str:
    """Return the parity sector suggested by the first numerical survey.

    In the canonical reflection structures and Jordan--Wigner Majorana
    orientation used by :mod:`oracle.majorana`, the conjectured protected
    parity is

        (-1) ** (modes * (modes + 1) / 2).

    An orientation-reversing Majorana relabeling can exchange the sector
    labels.  This function records a convention-dependent conjecture; it does
    not assert a proof.
    """
    if modes < 1:
        raise ValueError("modes must be positive")
    exponent = modes * (modes + 1) // 2
    return "even" if exponent % 2 == 0 else "odd"


def fermion_parity_operator(modes: int) -> np.ndarray:
    """Return ``P=(-i)^m gamma_0...gamma_(2m-1)`` in the canonical ordering."""
    gamma = majorana_operators(modes)
    parity = ((-1j) ** modes) * np.eye(1 << modes, dtype=complex)
    for operator in gamma:
        parity = parity @ operator
    return parity


def _parity_masks(modes: int) -> tuple[np.ndarray, np.ndarray]:
    dimension = 1 << modes
    odd = np.fromiter(
        (bool(state.bit_count() % 2) for state in range(dimension)),
        dtype=bool,
        count=dimension,
    )
    return ~odd, odd


def _classify(
    value: complex,
    *,
    sector_dimension: int,
    phase_tolerance: float,
    zero_tolerance: float,
) -> str:
    cancellation_ratio = abs(value) / math.sqrt(sector_dimension)
    if cancellation_ratio <= zero_tolerance:
        return "uncertain"
    phase = value / abs(value)
    if abs(phase.imag) > phase_tolerance:
        return "complex"
    return "positive" if phase.real > 0.0 else "negative"


def parity_resolved_trace(
    generators: list[np.ndarray],
    *,
    phase_tolerance: float = 1e-10,
    zero_tolerance: float = 1e-12,
) -> ParityTraceResult:
    """Evaluate even and odd Spin traces with stable positive rescaling."""
    if not generators:
        raise ValueError("at least one generator is required")

    matrices = [np.asarray(generator, dtype=complex) for generator in generators]
    shape = matrices[0].shape
    if (
        len(shape) != 2
        or shape[0] != shape[1]
        or shape[0] % 2
        or any(matrix.shape != shape for matrix in matrices)
    ):
        raise ValueError("generators must have one common even square shape")

    modes = shape[0] // 2
    gamma = majorana_operators(modes)
    dimension = 1 << modes
    product = np.eye(dimension, dtype=complex)
    log_scale = 0.0
    for matrix in matrices:
        product = product @ expm(
            quadratic_operator(matrix, operators=gamma)
        )
        product_norm = float(np.linalg.norm(product))
        if not math.isfinite(product_norm) or product_norm == 0.0:
            raise FloatingPointError("non-finite Fock-space product")
        product /= product_norm
        log_scale += math.log(product_norm)

    even_mask, odd_mask = _parity_masks(modes)
    diagonal = np.diag(product)
    even = complex(np.sum(diagonal[even_mask]))
    odd = complex(np.sum(diagonal[odd_mask]))
    total = even + odd
    sector_dimension = dimension // 2
    return ParityTraceResult(
        even=even,
        odd=odd,
        total=total,
        even_classification=_classify(
            even,
            sector_dimension=sector_dimension,
            phase_tolerance=phase_tolerance,
            zero_tolerance=zero_tolerance,
        ),
        odd_classification=_classify(
            odd,
            sector_dimension=sector_dimension,
            phase_tolerance=phase_tolerance,
            zero_tolerance=zero_tolerance,
        ),
        total_classification=_classify(
            total,
            sector_dimension=dimension,
            phase_tolerance=phase_tolerance,
            zero_tolerance=zero_tolerance,
        ),
        log_scale=log_scale,
    )


def _empty_counts() -> dict[str, int]:
    return {classification: 0 for classification in _CLASSIFICATIONS}


def scan_case(
    modes: int,
    depth: int,
    scale: float,
    seed: int,
    samples: int,
) -> dict[str, object]:
    """Scan one fixed Majorana-positive cone and count parity-sector signs."""
    if modes < 1:
        raise ValueError("modes must be positive")
    if depth < 1:
        raise ValueError("depth must be positive")
    if samples < 1:
        raise ValueError("samples must be positive")
    if not math.isfinite(scale) or scale < 0.0:
        raise ValueError("scale must be finite and non-negative")

    rng = np.random.default_rng(seed)
    counts = {
        "even": _empty_counts(),
        "odd": _empty_counts(),
        "total": _empty_counts(),
    }
    min_real = {"even": math.inf, "odd": math.inf, "total": math.inf}
    max_abs_imag = {"even": 0.0, "odd": 0.0, "total": 0.0}

    for _ in range(samples):
        generators = [
            random_reflection_generator(
                rng,
                block_size=modes,
                scale=scale,
                cone="positive",
            )
            for _ in range(depth)
        ]
        result = parity_resolved_trace(generators)
        values = {
            "even": result.even,
            "odd": result.odd,
            "total": result.total,
        }
        classifications = {
            "even": result.even_classification,
            "odd": result.odd_classification,
            "total": result.total_classification,
        }
        for sector in ("even", "odd", "total"):
            counts[sector][classifications[sector]] += 1
            min_real[sector] = min(min_real[sector], values[sector].real)
            max_abs_imag[sector] = max(
                max_abs_imag[sector],
                abs(values[sector].imag),
            )

    return {
        "params": {
            "modes": modes,
            "depth": depth,
            "scale": scale,
            "seed": seed,
            "samples": samples,
        },
        "protected_sector": protected_sector(modes),
        "counts": counts,
        "min_real": min_real,
        "max_abs_imag": max_abs_imag,
    }


def run_survey(
    *,
    modes: list[int],
    depth: int,
    scale: float,
    seed: int,
    samples: int,
) -> dict[str, object]:
    """Run the same reproducible parity survey for several mode counts."""
    return {
        "schema_version": 1,
        "convention": {
            "reflection_structures": "canonical J1/J2",
            "majorana_order": (
                "gamma_(2j)=Z^j X_j and gamma_(2j+1)=Z^j Y_j"
            ),
            "fermion_parity": "P=(-i)^m product_j gamma_j",
            "orientation_warning": (
                "an orientation-reversing Majorana relabeling can exchange "
                "the even and odd labels"
            ),
        },
        "interpretation": (
            "zero failures in the conjectured sector are numerical evidence, "
            "not a proof of parity-resolved Majorana positivity"
        ),
        "cells": [
            scan_case(
                modes=mode_count,
                depth=depth,
                scale=scale,
                seed=seed,
                samples=samples,
            )
            for mode_count in modes
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--modes",
        type=int,
        nargs="+",
        default=[2, 3, 4, 5, 6],
    )
    parser.add_argument("--depth", type=int, default=4)
    parser.add_argument("--scale", type=float, default=3.0)
    parser.add_argument("--seed", type=int, default=20260728)
    parser.add_argument("--samples", type=int, default=128)
    args = parser.parse_args()
    print(
        json.dumps(
            run_survey(
                modes=args.modes,
                depth=args.depth,
                scale=args.scale,
                seed=args.seed,
                samples=args.samples,
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
