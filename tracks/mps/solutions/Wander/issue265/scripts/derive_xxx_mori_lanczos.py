#!/usr/bin/env python3
"""Exact Pauli-string moments of the infinite-temperature XXX Mori kernel.

The calculation uses sparse Pauli strings on a periodic chain.  No many-body
state, transport trajectory, or fitted hydrodynamic coefficient is read.
For a momentum compatible with the ring, sufficiently large rings reproduce
the thermodynamic local commutator moments before operator support wraps.
"""

from __future__ import annotations

import argparse
import json
import math
from collections.abc import Iterable
from fractions import Fraction
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.heisenberg_burgers_bridge import (  # noqa: E402
    xxx_mori_even_moments,
    xxx_mori_long_wave_lanczos,
)


PauliString = tuple[tuple[int, int], ...]
Operator = dict[PauliString, complex]
GaussianInteger = tuple[int, int]
IntegerOperator = dict[PauliString, GaussianInteger]

_PRODUCT: dict[tuple[int, int], tuple[complex, int]] = {
    (0, 0): (1, 0), (0, 1): (1, 1), (0, 2): (1, 2), (0, 3): (1, 3),
    (1, 0): (1, 1), (1, 1): (1, 0), (1, 2): (1j, 3), (1, 3): (-1j, 2),
    (2, 0): (1, 2), (2, 1): (-1j, 3), (2, 2): (1, 0), (2, 3): (1j, 1),
    (3, 0): (1, 3), (3, 1): (1j, 2), (3, 2): (-1j, 1), (3, 3): (1, 0),
}


def _multiply(left: PauliString, right: PauliString) -> tuple[complex, PauliString]:
    lmap = dict(left)
    rmap = dict(right)
    phase = 1.0 + 0.0j
    result: list[tuple[int, int]] = []
    for site in sorted(set(lmap) | set(rmap)):
        local_phase, pauli = _PRODUCT[(lmap.get(site, 0), rmap.get(site, 0))]
        phase *= local_phase
        if pauli:
            result.append((site, pauli))
    return phase, tuple(result)


def _add(target: Operator, key: PauliString, value: complex, atol: float = 1e-13) -> None:
    updated = target.get(key, 0.0j) + value
    if abs(updated) <= atol:
        target.pop(key, None)
    else:
        target[key] = updated


def _liouvillian(operator: Operator, length: int, exchange: float = 1.0) -> Operator:
    result: Operator = {}
    for site in range(length):
        neighbour = (site + 1) % length
        for pauli in (1, 2, 3):
            h_string = tuple(sorted(((site, pauli), (neighbour, pauli))))
            for string, coefficient in operator.items():
                phase_lr, product_lr = _multiply(h_string, string)
                phase_rl, product_rl = _multiply(string, h_string)
                if product_lr != product_rl:
                    raise RuntimeError("Pauli products must have the same string")
                _add(
                    result,
                    product_lr,
                    0.25 * exchange * coefficient * (phase_lr - phase_rl),
                )
    return result


def _inner(left: Operator, right: Operator) -> complex:
    if len(left) > len(right):
        left, right = right, left
        return np.conjugate(_inner(left, right))
    # Millions of dyadic Pauli coefficients occur at the highest commutator
    # orders.  A naive left-to-right sum loses enough low bits to obscure the
    # exact rational moment even though every individual coefficient is still
    # exactly representable.  ``fsum`` makes the thermodynamic trace stable to
    # the final floating-point rounding.  Keep real and imaginary parts
    # separate because Python has no complex compensated sum.
    def products():
        for key, value in left.items():
            yield np.conjugate(value) * right.get(key, 0.0j)

    if left is right:
        return complex(
            math.fsum(
                value.real * value.real + value.imag * value.imag
                for value in left.values()
            ),
            0.0,
        )
    return complex(
        math.fsum(value.real for value in products()),
        math.fsum(value.imag for value in products()),
    )


def _subtract_projection(operator: Operator, density: Operator, susceptibility: float) -> Operator:
    coefficient = _inner(density, operator) / susceptibility
    result = dict(operator)
    for key, value in density.items():
        _add(result, key, -coefficient * value)
    return result


def fourier_density(length: int, momentum_index: int) -> tuple[float, Operator]:
    k = 2.0 * np.pi * momentum_index / length
    normalization = 0.5 / np.sqrt(length)
    density: Operator = {
        ((site, 3),): normalization * np.exp(-1j * k * site)
        for site in range(length)
    }
    return k, density


def fourier_bond_current(
    length: int,
    momentum_index: int,
    *,
    exchange: float = 1.0,
) -> tuple[float, Operator]:
    r"""Return the exactly normalized microscopic spin current on bonds.

    For ``H=J sum_x S_x.S_{x+1}``, the current flowing from ``x`` to
    ``x+1`` is

    ``j[x]=J(Sx[x] Sy[x+1]-Sy[x] Sx[x+1])``.

    Its Fourier phase is attached to the bond centre ``x+1/2``.  This phase,
    rather than an arbitrary lattice replacement of every internal GHD
    momentum, is what the microscopic continuity equation fixes exactly.
    """

    if momentum_index < 0 or momentum_index >= length:
        raise ValueError("momentum index is outside the periodic ring")
    k = 2.0 * np.pi * momentum_index / length
    normalization = float(exchange) / (4.0 * np.sqrt(length))
    current: Operator = {}
    for site in range(length):
        neighbour = (site + 1) % length
        phase = np.exp(-1j * k * (site + 0.5))
        _add(
            current,
            tuple(sorted(((site, 1), (neighbour, 2)))),
            normalization * phase,
        )
        _add(
            current,
            tuple(sorted(((site, 2), (neighbour, 1)))),
            -normalization * phase,
        )
    return k, current


def microscopic_bond_current_continuity_certificate(
    length: int,
    momentum_index: int,
    *,
    exchange: float = 1.0,
) -> dict[str, object]:
    r"""Certify ``[H,Sz_k]=-khat*j_k`` directly in Pauli operator space."""

    k, density = fourier_density(length, momentum_index)
    _, current = fourier_bond_current(
        length, momentum_index, exchange=exchange
    )
    khat = 2.0 * np.sin(0.5 * k)
    commutator = _liouvillian(density, length, exchange)
    residual = dict(commutator)
    # i[H,Sz_k]=-i*khat*j_k, hence [H,Sz_k]=-khat*j_k.
    for string, coefficient in current.items():
        _add(residual, string, khat * coefficient)
    commutator_norm = float(np.real(_inner(commutator, commutator)))
    residual_norm = float(np.real(_inner(residual, residual)))
    current_norm = float(np.real(_inner(current, current)))
    susceptibility = float(np.real(_inner(density, density)))
    return {
        "length": int(length),
        "momentum_index": int(momentum_index),
        "k": float(k),
        "khat": float(khat),
        "density_susceptibility": susceptibility,
        "bond_current_norm": current_norm,
        "density_commutator_norm": commutator_norm,
        "relative_operator_residual": float(
            np.sqrt(residual_norm)
            / max(np.sqrt(commutator_norm), np.finfo(float).tiny)
        ),
        "exact_fourier_identity": "[H,Sz_k]=-2*sin(k/2)*j_bond,k",
        "bond_center_phase_retained": True,
        "internal_ghd_momentum_replacement_implied": False,
        "uses_transport_trajectory": False,
        "uses_target_coefficients": False,
    }


def uniform_current_kernel_moments(
    length: int,
    max_order: int = 18,
    *,
    exchange: float = 1.0,
) -> dict[str, object]:
    r"""Return exact long-wave kernel moments from the total spin current.

    The lattice continuity equation implies
    ``lim[k->0] L S_k^z/khat = J_spin``.  Consequently the long-wave Mori
    moments are the infinite-temperature norms of successive commutators of
    the normalized uniform current.  This avoids any finite-momentum fit.
    """

    if length < max_order + 4:
        raise ValueError("length is too short for the requested local moment order")
    if max_order < 0 or max_order % 2:
        raise ValueError("max_order must be a non-negative even integer")
    normalization = float(exchange) / (4.0 * np.sqrt(length))
    current: Operator = {}
    for site in range(length):
        neighbour = (site + 1) % length
        _add(
            current,
            tuple(sorted(((site, 1), (neighbour, 2)))),
            normalization,
        )
        _add(
            current,
            tuple(sorted(((site, 2), (neighbour, 1)))),
            -normalization,
        )
    susceptibility = 0.25
    moments: list[float] = []
    counts: list[int] = []
    for order in range(0, max_order + 1, 2):
        moments.append(float(np.real(_inner(current, current))) / susceptibility)
        counts.append(len(current))
        if order != max_order:
            current = _liouvillian(current, length, exchange)
    return {
        "length": length,
        "orders": list(range(0, max_order + 1, 2)),
        "moments": moments,
        "operator_counts": counts,
        "method": "uniform_spin_current_commutator_chain",
        "finite_momentum_extrapolation_used": False,
    }


def _canonical_translation(string: PauliString) -> PauliString:
    """Anchor a finite Pauli string at its leftmost occupied site."""

    if not string:
        return string
    shift = min(site for site, _ in string)
    return tuple((site - shift, pauli) for site, pauli in string)


def _liouvillian_translation_reduced(
    operator: Operator,
    exchange: float = 1.0,
) -> Operator:
    r"""Apply the infinite-chain XXX Liouvillian to translation orbits.

    Each key represents ``sum_x tau_x(key)`` with the extensive normalization
    stripped off.  Only bonds intersecting the representative support can
    contribute.  Canonicalizing every output after the commutator exactly
    combines all translated copies without introducing a finite ring.
    """

    result: Operator = {}
    for string, coefficient in operator.items():
        if not string:
            continue
        right_edge = max(site for site, _ in string)
        for site in range(-1, right_edge + 1):
            neighbour = site + 1
            for pauli in (1, 2, 3):
                h_string = tuple(sorted(((site, pauli), (neighbour, pauli))))
                phase_lr, product_lr = _multiply(h_string, string)
                phase_rl, product_rl = _multiply(string, h_string)
                if product_lr != product_rl:
                    raise RuntimeError("Pauli products must have the same string")
                commutator = phase_lr - phase_rl
                if commutator:
                    _add(
                        result,
                        _canonical_translation(product_lr),
                        0.25 * exchange * coefficient * commutator,
                    )
    return result


def _liouvillian_translation_reduced_integer(
    operator: IntegerOperator,
) -> IntegerOperator:
    """Apply one XXX Liouvillian step to Gaussian-integer numerators.

    At depth ``r`` every coefficient has denominator ``2**(r+2)``.
    A nonzero Pauli commutator contributes ``+/- i/2``; the factor ``1/2``
    is absorbed into the next depth's denominator, leaving an exact Gaussian-
    integer rotation here.
    """

    result: IntegerOperator = {}
    for string, (real, imag) in operator.items():
        if not string:
            continue
        right_edge = max(site for site, _ in string)
        for site in range(-1, right_edge + 1):
            neighbour = site + 1
            for pauli in (1, 2, 3):
                h_string = tuple(sorted(((site, pauli), (neighbour, pauli))))
                phase_lr, product_lr = _multiply(h_string, string)
                phase_rl, product_rl = _multiply(string, h_string)
                if product_lr != product_rl:
                    raise RuntimeError("Pauli products must have the same string")
                commutator = phase_lr - phase_rl
                if not commutator:
                    continue
                sign = int(round(float(np.imag(commutator)) / 2.0))
                if sign not in (-1, 1) or abs(float(np.real(commutator))) > 1.0e-15:
                    raise RuntimeError("unexpected Pauli commutator coefficient")
                key = _canonical_translation(product_lr)
                previous_real, previous_imag = result.get(key, (0, 0))
                updated = (
                    previous_real - sign * imag,
                    previous_imag + sign * real,
                )
                if updated == (0, 0):
                    result.pop(key, None)
                else:
                    result[key] = updated
    return result


def translation_reduced_uniform_current_kernel_moments(
    max_order: int = 22,
    *,
    exchange: float = 1.0,
) -> dict[str, object]:
    r"""Return exact long-wave moments directly in the thermodynamic limit.

    The normalized total current is ``L^-1/2 sum_x j_x``.  Distinct finite
    translation orbits are orthogonal at infinite temperature, so its norm per
    site is the sum of squared orbit coefficients.  This representation is
    algebraically identical to a sufficiently long periodic ring but stores
    each translated Pauli string only once.
    """

    if max_order < 0 or max_order % 2:
        raise ValueError("max_order must be a non-negative even integer")
    if exchange != 1.0:
        raise ValueError("exact translation-reduced moments currently require exchange=1")
    current: IntegerOperator = {
        ((0, 1), (1, 2)): (1, 0),
        ((0, 2), (1, 1)): (-1, 0),
    }
    susceptibility = 0.25
    moments: list[float] = []
    exact_moments: list[str] = []
    counts: list[int] = []
    for order in range(0, max_order + 1, 2):
        liouvillian_depth = order // 2
        norm_numerator = sum(real**2 + imag**2 for real, imag in current.values())
        exact = Fraction(norm_numerator, 2 ** (2 * liouvillian_depth + 2))
        moments.append(float(exact))
        exact_moments.append(str(exact))
        counts.append(len(current))
        if order != max_order:
            current = _liouvillian_translation_reduced_integer(current)
    return {
        "orders": list(range(0, max_order + 1, 2)),
        "moments": moments,
        "exact_moments": exact_moments,
        "translation_orbit_counts": counts,
        "method": "thermodynamic_translation_orbit_sparse_pauli_commutator_chain",
        "translation_orbits_used": True,
        "finite_ring_used": False,
        "finite_momentum_extrapolation_used": False,
    }


def kernel_moments(
    length: int,
    momentum_index: int,
    max_order: int = 6,
    *,
    exchange: float = 1.0,
) -> dict[str, object]:
    """Return positive spectral moments ``mu_0,mu_2,...`` of ``K(k,t)``."""

    if length < max_order + 4:
        raise ValueError("length is too short for the requested local moment order")
    if momentum_index <= 0 or momentum_index >= length:
        raise ValueError("use a nonzero periodic momentum index")
    if max_order < 0 or max_order % 2:
        raise ValueError("max_order must be a non-negative even integer")
    k, density = fourier_density(length, momentum_index)
    susceptibility = float(np.real(_inner(density, density)))
    khat = 2.0 * np.sin(0.5 * k)
    force = _subtract_projection(
        _liouvillian(density, length, exchange), density, susceptibility
    )
    current = force
    moments: list[float] = []
    counts: list[int] = []
    for order in range(0, max_order + 1, 2):
        moment = float(np.real(_inner(current, current))) / (susceptibility * khat**2)
        moments.append(moment)
        counts.append(len(current))
        if order != max_order:
            current = _subtract_projection(
                _liouvillian(current, length, exchange), density, susceptibility
            )
    return {
        "length": length,
        "momentum_index": momentum_index,
        "k": k,
        "khat": khat,
        "susceptibility": susceptibility,
        "orders": list(range(0, max_order + 1, 2)),
        "moments": moments,
        "operator_counts": counts,
    }


def calculate_grid(length: int, indices: Iterable[int], max_order: int) -> dict[str, object]:
    rows = [kernel_moments(length, index, max_order) for index in indices]
    errors: list[float] = []
    for row in rows:
        closed = xxx_mori_even_moments(np.asarray(row["k"]))
        errors.extend(
            abs(float(value) - float(closed[order]))
            for order, value in zip(row["orders"], row["moments"], strict=True)
            if order in closed
        )
    return {
        "schema": 1,
        "method": "exact_sparse_pauli_string_commutators",
        "uses_transport_trajectory": False,
        "uses_target_coefficients": False,
        "closed_form_max_abs_error": max(errors, default=0.0),
        "closed_form_validated_through_order": max(
            xxx_mori_even_moments(np.asarray(0.0))
        ),
        "long_wave_closed_moments": {
            str(order): float(value)
            for order, value in xxx_mori_even_moments(np.asarray(0.0)).items()
        },
        "long_wave_lanczos": {
            key: np.asarray(value).tolist()
            for key, value in xxx_mori_long_wave_lanczos().items()
        },
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--length", type=int, default=16)
    parser.add_argument("--indices", type=int, nargs="+", default=[1, 2, 3, 4])
    parser.add_argument("--max-order", type=int, default=6)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    encoded = json.dumps(
        calculate_grid(args.length, args.indices, args.max_order), indent=2
    ) + "\n"
    print(encoded, end="")
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")


if __name__ == "__main__":
    main()
