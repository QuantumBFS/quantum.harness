#!/usr/bin/env python3
"""Project the exact XXX bond current onto long-wave spin bilinears.

The calculation is a finite-volume infinite-temperature Kubo projection.  It
uses the exact four-spin trace, including the on-site quantum cumulant, rather
than a cell-scale Gaussian Wick approximation.  The selected slow subspace
contains bilinears whose two Fourier legs both lie inside a declared momentum
cutoff.  No dynamics, trajectory, or target Burgers coefficient enters.
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
    _multiply,
)


_PAULI = (
    np.eye(2, dtype=complex),
    np.asarray([[0.0, 1.0], [1.0, 0.0]], dtype=complex),
    np.asarray([[0.0, -1.0j], [1.0j, 0.0]], dtype=complex),
    np.asarray([[1.0, 0.0], [0.0, -1.0]], dtype=complex),
)
_PAIRINGS = (((0, 1), (2, 3)), ((0, 2), (1, 3)), ((0, 3), (1, 2)))


def _local_trace(labels: tuple[int, ...]) -> complex:
    matrix = np.eye(2, dtype=complex)
    for label in labels:
        matrix = matrix @ (0.5 * _PAULI[label])
    return complex(0.5 * np.trace(matrix))


def _fourier_four_spin_trace(
    length: int,
    momentum_indices: tuple[int, int, int, int],
    spin_labels: tuple[int, int, int, int],
) -> complex:
    r"""Exact normalized infinite-temperature four-spin trace.

    The three two-site pairings give the Gaussian part.  When all four
    operators occupy one site, the local Pauli trace differs from the sum of
    pairings; the final ``1/L`` term is that exact quantum cumulant.
    """

    value = 0.0j
    paired_local = 0.0j
    for (i, j), (k, l) in _PAIRINGS:
        local = _local_trace((spin_labels[i], spin_labels[j])) * _local_trace(
            (spin_labels[k], spin_labels[l])
        )
        paired_local += local
        if (
            (momentum_indices[i] + momentum_indices[j]) % length == 0
            and (momentum_indices[k] + momentum_indices[l]) % length == 0
        ):
            value += local
    if sum(momentum_indices) % length == 0:
        value += (_local_trace(spin_labels) - paired_local) / float(length)
    return complex(value)


def bond_current_bilinear_gram(length: int, external_mode: int) -> np.ndarray:
    r"""Return the exact Gram matrix of the momentum-resolved current sum.

    With ``q=k-p``, define

    ``B_p=e^{i(k/2-p)}/sqrt(L) [S_p^x S_q^y-S_p^y S_q^x]``.

    Direct Fourier transformation gives ``j_k=sum_p B_p``.  The matrix below
    is ``G[p,r]=(B_p,B_r)`` in the infinite-temperature Kubo product.
    """

    if length < 4 or not 0 < external_mode < length:
        raise ValueError("invalid length or external mode")
    k = 2.0 * np.pi * external_mode / length
    gram = np.zeros((length, length), dtype=complex)
    terms = (((1, 2), 1.0), ((2, 1), -1.0))
    for p in range(length):
        q = (external_mode - p) % length
        coefficient_p = np.exp(1.0j * (k / 2.0 - 2.0 * np.pi * p / length)) / np.sqrt(length)
        for r in range(length):
            s = (external_mode - r) % length
            coefficient_r = np.exp(1.0j * (k / 2.0 - 2.0 * np.pi * r / length)) / np.sqrt(length)
            for left, left_sign in terms:
                for right, right_sign in terms:
                    gram[p, r] += (
                        np.conjugate(coefficient_p)
                        * coefficient_r
                        * left_sign
                        * right_sign
                        * _fourier_four_spin_trace(
                            length,
                            ((-q) % length, (-p) % length, r, s),
                            (left[1], left[0], right[0], right[1]),
                        )
                    )
    gram = 0.5 * (gram + gram.conj().T)
    return gram


def bond_current_bilinear_operator(
    length: int,
    external_mode: int,
    internal_mode: int,
) -> Operator:
    r"""Return the exact Pauli expansion of one ordered bilinear ``B_p``.

    Fourier spins use ``S_p=L^-1/2 sum_x exp(-ipx) S_x``.  The extra
    ``exp[-ip]`` in the bond-centred prefactor is essential: summing over all
    internal modes produces a nearest-neighbour bond rather than an on-site
    product.
    """

    if length < 4 or not 0 < external_mode < length:
        raise ValueError("invalid length or external mode")
    p = 2.0 * np.pi * (internal_mode % length) / length
    k = 2.0 * np.pi * external_mode / length
    q = k - p
    prefactor = np.exp(1.0j * (0.5 * k - p)) / (
        length * np.sqrt(length)
    )
    result: Operator = {}
    for x in range(length):
        for y in range(length):
            fourier_phase = np.exp(-1.0j * (p * x + q * y))
            for left, right, sign in ((1, 2, 1.0), (2, 1, -1.0)):
                phase, string = _multiply(((x, left),), ((y, right),))
                _add(
                    result,
                    string,
                    0.25 * prefactor * fourier_phase * sign * phase,
                )
    return result


def slow_bilinear_dynamical_matrices(
    length: int,
    external_mode: int,
    selected_modes: tuple[int, ...],
) -> dict[str, object]:
    r"""Compute exact ``G0=(B,B)``, ``G1=(B,LB)``, ``G2=(LB,LB)``.

    These matrices are the first dynamical data required for a microscopic
    ``P L P`` / ``Q L P`` split.  They use no hydrodynamic closure.
    """

    modes = tuple(sorted({mode % length for mode in selected_modes}))
    operators = [
        bond_current_bilinear_operator(length, external_mode, mode)
        for mode in modes
    ]
    evolved = [_liouvillian(operator, length) for operator in operators]
    count = len(modes)
    g0 = np.empty((count, count), dtype=complex)
    g1 = np.empty((count, count), dtype=complex)
    g2 = np.empty((count, count), dtype=complex)
    for i in range(count):
        for j in range(count):
            g0[i, j] = _inner(operators[i], operators[j])
            g1[i, j] = _inner(operators[i], evolved[j])
            g2[i, j] = _inner(evolved[i], evolved[j])
    return {
        "modes": modes,
        "gram": 0.5 * (g0 + g0.conj().T),
        "liouvillian_gram": 0.5 * (g1 + g1.conj().T),
        "liouvillian_norm_gram": 0.5 * (g2 + g2.conj().T),
        "maximum_g0_analytic_residual": float(
            np.max(
                np.abs(
                    g0
                    - bond_current_bilinear_gram(length, external_mode)[
                        np.ix_(modes, modes)
                    ]
                )
            )
        ),
    }


def _wrapped_mode(index: int, length: int) -> int:
    index %= length
    return min(index, length - index)


def derive(
    length: int,
    external_mode: int,
    cutoff_modes: tuple[int, ...],
) -> dict[str, object]:
    gram = bond_current_bilinear_gram(length, external_mode)
    coefficients = np.ones(length, dtype=complex)
    current_overlap = gram @ coefficients
    full_norm = float(np.real(np.vdot(coefficients, current_overlap)))
    spin_susceptibility = 0.25
    exact_kernel_mu0 = full_norm / spin_susceptibility
    eigenvalues = np.linalg.eigvalsh(gram)
    rows = []
    previous_norm = -np.inf
    for cutoff in sorted(set(cutoff_modes)):
        if cutoff < 0 or cutoff >= length // 2:
            raise ValueError("cutoff modes must lie below the Nyquist mode")
        selected = [
            p
            for p in range(length)
            if _wrapped_mode(p, length) <= cutoff
            and _wrapped_mode(external_mode - p, length) <= cutoff
        ]
        if not selected:
            projected_norm = 0.0
            rank = 0
        else:
            subgram = gram[np.ix_(selected, selected)]
            overlap = current_overlap[selected]
            projected_norm = float(
                np.real(
                    np.vdot(
                        overlap,
                        np.linalg.pinv(subgram, rcond=1.0e-12) @ overlap,
                    )
                )
            )
            rank = int(np.linalg.matrix_rank(subgram, tol=1.0e-12))
        monotone = bool(projected_norm + 1.0e-14 >= previous_norm)
        previous_norm = projected_norm
        rows.append(
            {
                "cutoff_mode": int(cutoff),
                "cutoff_wave_number": float(2.0 * np.pi * cutoff / length),
                "selected_ordered_bilinears": len(selected),
                "selected_gram_rank": rank,
                "projected_current_norm": projected_norm,
                "projected_fraction_of_full_current": projected_norm / full_norm,
                "projected_slow_kernel_mu0": projected_norm / spin_susceptibility,
                "orthogonal_kernel_mu0": (full_norm - projected_norm)
                / spin_susceptibility,
                "kernel_mu0_sum_residual": abs(
                    projected_norm / spin_susceptibility
                    + (full_norm - projected_norm) / spin_susceptibility
                    - exact_kernel_mu0
                ),
                "monotone_with_cutoff": monotone,
            }
        )
    return {
        "schema": 1,
        "method": "exact_four_spin_kubo_projection_onto_long_wave_bilinears",
        "inputs": {
            "length": int(length),
            "external_mode": int(external_mode),
            "cutoff_modes": sorted(set(cutoff_modes)),
            "temperature": "infinite",
            "trajectory_data_used": False,
            "target_coefficients_used": False,
        },
        "external_wave_number": float(2.0 * np.pi * external_mode / length),
        "full_bond_current_norm": full_norm,
        "spin_susceptibility": spin_susceptibility,
        "exact_kernel_mu0": exact_kernel_mu0,
        "exact_expected_full_bond_current_norm": 0.125,
        "full_norm_absolute_residual": abs(full_norm - 0.125),
        "gram_minimum_eigenvalue": float(np.min(eigenvalues)),
        "gram_rank": int(np.linalg.matrix_rank(gram, tol=1.0e-12)),
        "rows": rows,
        "gates": {
            "full_current_identity_normalized": bool(abs(full_norm - 0.125) <= 1.0e-12),
            "gram_positive_semidefinite": bool(np.min(eigenvalues) >= -1.0e-12),
            "all_projector_norms_bounded": bool(
                all(0.0 <= row["projected_current_norm"] <= full_norm + 1.0e-12 for row in rows)
            ),
            "all_projector_norms_monotone": bool(
                all(row["monotone_with_cutoff"] for row in rows)
            ),
            "all_pq_kernel_splits_positive_and_exact": bool(
                all(
                    row["projected_slow_kernel_mu0"] >= -1.0e-12
                    and row["orthogonal_kernel_mu0"] >= -1.0e-12
                    and row["kernel_mu0_sum_residual"] <= 1.0e-12
                    for row in rows
                )
            ),
        },
        "interpretation": (
            "The long-wave sector has a small static Kubo weight.  Its large "
            "late-time effect must come from its divergent lifetime.  This "
            "bounded projector replaces the divergent cell-scale Gaussian "
            "loop normalization in a no-double-counting construction."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--length", type=int, default=400)
    parser.add_argument("--external-mode", type=int, default=1)
    parser.add_argument(
        "--cutoff-modes",
        type=int,
        nargs="+",
        default=[1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64, 100, 199],
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
