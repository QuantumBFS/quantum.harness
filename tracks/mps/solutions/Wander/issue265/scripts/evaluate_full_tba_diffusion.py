#!/usr/bin/env python3
"""Evaluate the diagonal XXX GHD diffusion formula at finite field.

This is a first-principles quadrature of Eq. (16) in the supplemental
material of De Nardis et al., arXiv:2003.13708.  Unlike the simpler spectral
regulator, it explicitly dresses the two-body scattering kernel.  Equation
(16) of that supplement identifies the diagonal result with the physical spin
diffusion up to an ``O(h)`` off-diagonal remainder in the zero-field limit.

The program also evaluates the cross contraction obtained by expanding the
charge-difference quadratic form of De Nardis, Bernard and Doyon,
arXiv:1812.00767.  With the conventions used here this is exactly the
off-diagonal term in ``(mathfrak D C)_spin``: the full contraction is the
diagonal term minus the positive cross contraction.  At finite numerical
cutoff this identity does not, by itself, imply convergence to the physical
infinite-string result.  The supplement of arXiv:2003.13708 argues, but does
not prove, that the off-diagonal contribution vanishes in the half-filling limit after the
string sums are taken in the correct order.

The program does *not* presume that the finite-field sequence has an already
established constant term in

    D_spin(h) = 5*pi/(27*h) + D1 + O(h).

The rapidity-independent infinite-temperature fillings turn the dressing
operation into a tridiagonal recurrence in string space.  We solve that
recurrence at every Fourier momentum with either a finite zero boundary (the
``s_max`` prescription used in the published numerical check) or the formal
large-string Robin boundary.  Comparing the two exposes the non-commuting
limits instead of hiding them.  The remaining absolute velocity difference is
evaluated through the Fourier series of ``|v-v'|``; this reduces a
four-dimensional direct quadrature to FFT convolutions and string-space matrix
products.

No spin-chain trajectory is read by this program.
"""

from __future__ import annotations

import argparse
import json
from math import ceil
from pathlib import Path
import sys

import numpy as np
from scipy.fft import fft, fftshift, ifft, ifftshift, next_fast_len
from scipy.integrate import trapezoid
from scipy.linalg import solve_banded


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.heisenberg_burgers_bridge import (  # noqa: E402
    EXACT_D0_INFINITY_T,
    finite_field_spectral_regulator_diffusion,
    zero_field_edge_dressed_scattering_fourier,
    zero_field_edge_thermodynamic_fields,
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--field", type=float, required=True)
    parser.add_argument(
        "--string-xi-cutoff",
        type=float,
        default=10.0,
        help="Keep physical strings through s*h <= this value",
    )
    parser.add_argument(
        "--string-xi-buffer",
        type=float,
        default=4.0,
        help="Extra string interval used only inside the dressing solve",
    )
    parser.add_argument(
        "--string-boundary",
        choices=("zero", "robin"),
        default="zero",
        help=(
            "Boundary at the end of the string dressing solve. 'zero' "
            "reproduces a finite-s_max calculation; 'robin' imposes the "
            "formal large-string solution at each Fourier momentum."
        ),
    )
    parser.add_argument(
        "--rapidity-u-extent",
        type=float,
        default=20.0,
        help="Integrate rapidities through |h*theta| <= this value",
    )
    parser.add_argument("--rapidity-step", type=float, default=0.25)
    parser.add_argument(
        "--velocity-series-terms",
        type=int,
        default=2000,
        help="Odd Fourier modes retained in the exact |v-v'| series",
    )
    parser.add_argument(
        "--velocity-group-ratio",
        type=float,
        default=2.0,
        help=(
            "Geometric ratio used to group strings by their velocity scale. "
            "Each group pair gets its own |v-v'| Fourier interval; this "
            "avoids resolving giant-string velocities on the fastest-string "
            "scale. Must exceed one."
        ),
    )
    parser.add_argument(
        "--skip-cross-diagnostic",
        action="store_true",
        help="Skip the non-physical formal cross contraction to halve runtime",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON output path; stdout is always written",
    )
    return parser.parse_args()


def _fillings(field: float, count: int) -> np.ndarray:
    species = np.arange(1, count + 1, dtype=float)
    return (np.sinh(field) / np.sinh((species + 1.0) * field)) ** 2


def _dressed_kernel_fourier(
    field: float,
    momenta: np.ndarray,
    *,
    active_strings: int,
    solve_strings: int,
    boundary: str = "zero",
) -> tuple[np.ndarray, np.ndarray]:
    r"""Return ``T^dr(k)`` and the physical-source dressed momentum.

    If ``F_{s,r}=G^dr_{s,r}``, the infinite-temperature local recurrence is

    ``[2 cosh(|k|/2) delta - I*(1-n)] F = 1``.

    At large string index its formal homogeneous solution obeys
    ``F_{S+1}=exp(-|k|/2) F_S``.  The alternative ``zero`` boundary is the
    literal finite-``s_max`` prescription.  Their difference near ``k=0`` is
    retained as an order-of-limits diagnostic.  Finally

    ``T^dr_{s,s'}=F_{s,s'-1}+F_{s,s'+1}``.
    """

    if solve_strings < active_strings + 2:
        raise ValueError("solve_strings must exceed active_strings by two")
    if boundary not in {"zero", "robin"}:
        raise ValueError("boundary must be 'zero' or 'robin'")
    filling = _fillings(field, solve_strings + 1)
    holes = 1.0 - filling
    source_count = active_strings + 1
    rhs = np.zeros((solve_strings, source_count), dtype=float)
    rhs[:source_count, :] = np.eye(source_count)

    # Single precision is amply below the cutoff/quadrature error here and
    # halves the peak memory of the N_theta x N_string^2 kernel.  All
    # thermodynamic fields, contractions and reported scalars remain float64.
    kernel_hat = np.empty(
        (momenta.size, active_strings, active_strings), dtype=np.float32
    )
    physical_hat = np.empty((momenta.size, active_strings), dtype=float)

    # FFT momenta occur in +/- pairs.  Solving each |k| once halves the cost.
    absolute_to_indices: dict[float, list[int]] = {}
    for index, momentum in enumerate(momenta):
        key = float(np.round(abs(momentum), 14))
        absolute_to_indices.setdefault(key, []).append(index)

    for absolute_momentum, indices in absolute_to_indices.items():
        decay = np.exp(-absolute_momentum / 2.0)
        banded = np.zeros((3, solve_strings), dtype=float)
        banded[1, :] = 2.0 * np.cosh(absolute_momentum / 2.0)
        banded[0, 1:] = -holes[1:solve_strings]
        banded[2, :-1] = -holes[: solve_strings - 1]
        if boundary == "robin":
            banded[1, -1] -= holes[solve_strings] * decay
        dressed_momentum = solve_banded((1, 1), banded, rhs)

        active = dressed_momentum[:active_strings, :]
        dressed_kernel = np.zeros(
            (active_strings, active_strings), dtype=float
        )
        # s'=1 has only the upper neighbouring source r=2.
        dressed_kernel[:, 0] = active[:, 1]
        for source in range(1, active_strings):
            dressed_kernel[:, source] = (
                active[:, source - 1] + active[:, source + 1]
            )
        for index in indices:
            kernel_hat[index, :, :] = dressed_kernel
            physical_hat[index, :] = active[:, 0]
    return kernel_hat, physical_hat


def _dressed_kernel_rows_fourier(
    field: float,
    momenta: np.ndarray,
    *,
    left_strings: np.ndarray,
    active_strings: int,
    solve_strings: int,
    boundary: str = "robin",
) -> np.ndarray:
    r"""Return selected symmetric rows of ``T^dr(k)`` without an ``S^2`` cube.

    For source string ``s'`` the local-recurrence source is
    ``e_(s'-1)+e_(s'+1)`` (with the lower neighbour absent at ``s'=1``).
    Solving only these columns reduces storage from ``O(N_k S^2)`` to
    ``O(N_k S N_left)`` and is the appropriate route for fixed-string inner
    matching against the complete giant partner tail.
    """

    selected = np.asarray(left_strings, dtype=int)
    if selected.ndim != 1 or selected.size == 0:
        raise ValueError("left_strings must be a non-empty vector")
    if np.any(selected < 1) or np.any(selected > active_strings):
        raise ValueError("selected strings must lie in the active range")
    if solve_strings < active_strings + 2:
        raise ValueError("solve_strings must exceed active_strings by two")
    if boundary not in {"zero", "robin"}:
        raise ValueError("boundary must be zero or robin")
    filling = _fillings(field, solve_strings + 1)
    holes = 1.0 - filling
    rhs = np.zeros((solve_strings, selected.size), dtype=float)
    for column, string in enumerate(selected):
        if string > 1:
            rhs[string - 2, column] += 1.0
        rhs[string, column] += 1.0
    result = np.empty(
        (momenta.size, selected.size, active_strings), dtype=np.float32
    )
    absolute_to_indices: dict[float, list[int]] = {}
    for index, momentum in enumerate(momenta):
        key = float(np.round(abs(momentum), 14))
        absolute_to_indices.setdefault(key, []).append(index)
    for absolute_momentum, indices in absolute_to_indices.items():
        decay = np.exp(-absolute_momentum / 2.0)
        banded = np.zeros((3, solve_strings), dtype=float)
        banded[1, :] = 2.0 * np.cosh(absolute_momentum / 2.0)
        banded[0, 1:] = -holes[1:solve_strings]
        banded[2, :-1] = -holes[: solve_strings - 1]
        if boundary == "robin":
            banded[1, -1] -= holes[solve_strings] * decay
        solved = solve_banded((1, 1), banded, rhs)
        rows = solved[:active_strings].T
        for index in indices:
            result[index] = rows
    return result


def _thermodynamic_fields(
    field: float,
    strings: int,
    rapidities: np.ndarray,
) -> dict[str, np.ndarray]:
    """Closed infinite-temperature XXX TBA functions."""

    species = np.arange(1, strings + 1, dtype=float)
    filling = _fillings(field, strings)
    holes = 1.0 - filling
    theta = rapidities[None, :].astype(np.longdouble)
    s = species[:, None].astype(np.longdouble)
    h = np.longdouble(field)

    first = s / (
        (4.0 * theta**2 + s**2) * np.sinh(h * s)
    )
    second = (s + 2.0) / (
        (4.0 * theta**2 + (s + 2.0) ** 2)
        * np.sinh(h * (s + 2.0))
    )
    rho_total = (
        2.0
        * np.sinh(h)
        * np.sinh(h * (s + 1.0))
        / (np.pi * np.sinh(2.0 * h))
        * (first - second)
    )

    first_energy = s / (
        (4.0 * theta**2 + s**2) ** 2 * np.sinh(h * s)
    )
    second_energy = (s + 2.0) / (
        (4.0 * theta**2 + (s + 2.0) ** 2) ** 2
        * np.sinh(h * (s + 2.0))
    )
    energy_derivative = (
        16.0
        * theta
        * np.sinh(h)
        * np.sinh(h * (s + 1.0))
        / np.sinh(2.0 * h)
        * (first_energy - second_energy)
    )
    velocity = energy_derivative / (2.0 * np.pi * rho_total)

    sh = np.sinh(field * (species + 1.0))
    dressed_magnetization = sh * (
        (species + 1.0) * np.cosh(field * (species + 1.0))
        - np.cosh(field) / np.sinh(field) * sh
    ) / (sh**2 - np.sinh(field) ** 2)

    return {
        "species": species,
        "filling": filling,
        "holes": holes,
        "rho_total": np.asarray(rho_total, dtype=float),
        "velocity": np.asarray(velocity, dtype=float),
        "dressed_magnetization": dressed_magnetization,
    }


def diagonal_diffusion_width_field(
    field: float,
    *,
    string_xi_cutoff: float = 8.0,
    string_xi_buffer: float = 6.0,
    rapidity_u_extent: float = 40.0,
    rapidity_step: float = 0.4,
    velocity_series_terms: int = 100,
    velocity_group_ratio: float = 1.3,
    string_boundary: str = "robin",
) -> dict[str, np.ndarray | float | int]:
    r"""Return the node-resolved diagonal GHD broadening ``w_s(theta)``.

    It evaluates Eq. (14) of the supplement to arXiv:2003.13708 before the
    final spin-weight contraction.  The result can therefore be propagated
    as a microscopic Gaussian quasiparticle mixture instead of being reduced
    immediately to one scalar diffusion constant.
    """

    active_strings = int(ceil(string_xi_cutoff / field))
    solve_strings = max(
        active_strings + 2,
        int(ceil((string_xi_cutoff + string_xi_buffer) / field)),
    )
    theta_extent = rapidity_u_extent / field
    requested_points = int(ceil(2.0 * theta_extent / rapidity_step))
    points = int(next_fast_len(max(requested_points, 128)))
    if points % 2:
        points = int(next_fast_len(points + 1))
    actual_step = 2.0 * theta_extent / points
    rapidities = (np.arange(points) - points // 2) * actual_step
    momenta = 2.0 * np.pi * np.fft.fftfreq(points, d=actual_step)
    kernel_hat, _ = _dressed_kernel_fourier(
        field,
        momenta,
        active_strings=active_strings,
        solve_strings=solve_strings,
        boundary=string_boundary,
    )
    dressed_kernel = fftshift(ifft(kernel_hat, axis=0), axes=0).real / actual_step
    del kernel_hat
    fields = _thermodynamic_fields(field, active_strings, rapidities)
    filling = fields["filling"]
    holes = fields["holes"]
    rho_total = fields["rho_total"]
    velocity = np.nan_to_num(fields["velocity"], copy=False)
    right = filling[:, None] * holes[:, None] * rho_total
    kernel_squared_hat = fft(ifftshift(dressed_kernel**2, axes=0), axis=0)
    self_kernel_squared = np.diag(dressed_kernel[points // 2, :, :]) ** 2
    del dressed_kernel

    species_bound = np.max(np.abs(velocity), axis=1)
    total_bound = float(np.max(species_bound)) * (1.0 + 1.0e-12)
    positive = np.maximum(species_bound, total_bound * np.finfo(float).eps)
    labels = np.floor(
        np.log(total_bound / positive) / np.log(float(velocity_group_ratio))
    ).astype(int)
    groups = [np.flatnonzero(labels == label) for label in np.unique(labels)]
    node_contraction = np.zeros_like(rho_total)
    inverse_odd_square_sum = sum(
        1.0 / (2 * mode + 1) ** 2 for mode in range(velocity_series_terms)
    )
    species_interval = np.empty(active_strings, dtype=float)
    for indices in groups:
        species_interval[indices] = (
            2.0 * float(np.max(species_bound[indices])) * (1.0 + 1.0e-12)
        )
    for left_indices in groups:
        left_max = float(np.max(species_bound[left_indices]))
        for right_indices in groups:
            interval = (
                left_max
                + float(np.max(species_bound[right_indices]))
            ) * (1.0 + 1.0e-12)

            def convolution(momentum: float) -> np.ndarray:
                right_hat = fft(
                    ifftshift(
                        right[right_indices]
                        * np.exp(-1j * momentum * velocity[right_indices]),
                        axes=1,
                    ),
                    axis=1,
                ).T
                convolved_hat = np.einsum(
                    "kij,kj->ki",
                    kernel_squared_hat[:, left_indices][:, :, right_indices],
                    right_hat,
                    optimize=True,
                )
                convolved = fftshift(ifft(convolved_hat, axis=0), axes=0).T
                return (
                    actual_step
                    * np.exp(1j * momentum * velocity[left_indices])
                    * convolved
                ).real

            block = 0.5 * convolution(0.0)
            for mode in range(velocity_series_terms):
                odd = 2 * mode + 1
                block -= (
                    4.0
                    / np.pi**2
                    * convolution(odd * np.pi / interval)
                    / odd**2
                )
            node_contraction[left_indices] += interval * block

    approximate_zero = 0.5 * species_interval * (
        1.0 - 8.0 / np.pi**2 * inverse_odd_square_sum
    )
    node_contraction -= (
        actual_step
        * right
        * self_kernel_squared[:, None]
        * approximate_zero[:, None]
    )
    width = np.divide(
        node_contraction,
        rho_total**2,
        out=np.zeros_like(node_contraction),
        where=rho_total > 0.0,
    )
    return {
        "field": float(field),
        "active_strings": active_strings,
        "rapidity_step": float(actual_step),
        "rapidities": rapidities,
        "filling": filling,
        "holes": holes,
        "rho_total": rho_total,
        "velocity": velocity,
        "dressed_magnetization": fields["dressed_magnetization"],
        "width": width,
    }


def full_diffusion_operator_field(
    field: float,
    *,
    string_xi_cutoff: float = 3.0,
    string_xi_buffer: float = 3.0,
    rapidity_u_extent: float = 8.0,
    rapidity_points: int = 64,
    string_boundary: str = "robin",
) -> dict[str, np.ndarray | float | int]:
    r"""Discretize the complete non-diagonal occupation-space kernel.

    This implements Eqs. (4.27)--(4.30) of arXiv:1812.00767.  Every
    string/rapidity node and off-diagonal pair is retained; no two-mode or
    finite-pole closure is made.  ``noise_covariance`` is the symmetric FDT
    combination ``(D C + C D.T)/2`` for occupation fluctuations.
    """

    if not 0.0 < field <= 0.35:
        raise ValueError("field must lie in (0,0.35]")
    if rapidity_points < 16 or rapidity_points % 2:
        raise ValueError("rapidity_points must be an even integer >=16")
    if string_boundary not in {"zero", "robin"}:
        raise ValueError("string_boundary must be 'zero' or 'robin'")
    active_strings = int(ceil(string_xi_cutoff / field))
    solve_strings = max(
        active_strings + 2,
        int(ceil((string_xi_cutoff + string_xi_buffer) / field)),
    )
    theta_extent = rapidity_u_extent / field
    step = 2.0 * theta_extent / rapidity_points
    rapidities = (
        np.arange(rapidity_points, dtype=float) - rapidity_points // 2
    ) * step
    momenta = 2.0 * np.pi * np.fft.fftfreq(rapidity_points, d=step)
    kernel_hat, _ = _dressed_kernel_fourier(
        field,
        momenta,
        active_strings=active_strings,
        solve_strings=solve_strings,
        boundary=string_boundary,
    )
    dressed = fftshift(ifft(kernel_hat, axis=0), axes=0).real / step
    fields = _thermodynamic_fields(field, active_strings, rapidities)
    filling = fields["filling"]
    holes = fields["holes"]
    rho_s = fields["rho_total"]
    velocity = np.nan_to_num(fields["velocity"], copy=False)

    species_i = np.repeat(np.arange(active_strings), rapidity_points)
    rapidity_i = np.tile(np.arange(rapidity_points), active_strings)
    delta_index = (
        rapidity_i[:, None] - rapidity_i[None, :] + rapidity_points // 2
    ) % rapidity_points
    reverse_index = (
        rapidity_i[None, :] - rapidity_i[:, None] + rapidity_points // 2
    ) % rapidity_points
    left_species = species_i[:, None]
    right_species = species_i[None, :]
    t_ij = dressed[delta_index, left_species, right_species]
    t_ji = dressed[reverse_index, right_species, left_species]

    n_flat = filling[species_i]
    f_flat = holes[species_i]
    rho_flat = rho_s[species_i, rapidity_i]
    v_flat = velocity[species_i, rapidity_i]
    assembled = _assemble_nodal_diffusion_noise(
        n_flat, rho_flat, v_flat, t_ij, t_ji, step
    )
    diffusion = assembled["diffusion_operator"]
    static_covariance = assembled["static_covariance"]
    noise_covariance = assembled["noise_covariance"]
    collision_rate = assembled["collision_rate"]
    # Frechet derivative of v_eff=e'^dr/p'^dr with respect to a nodal
    # occupation.  It follows directly by differentiating
    # h^dr=(1-Tn)^(-1)h; no finite-difference fit is involved.
    velocity_vertex = (
        step
        * t_ij
        * rho_flat[None, :]
        / rho_flat[:, None]
        * (v_flat[None, :] - v_flat[:, None])
    )
    dressed_spin_flat = fields["dressed_magnetization"][species_i]
    spin_projection = step * rho_flat * dressed_spin_flat
    # Hessian of the physical spin density q[n].  Since
    # dq = integral rho_s q^dr dn, differentiating both dressed factors gives
    # the two terms below.  This is the quadratic observable correction needed
    # when occupation fields, rather than conserved densities, are propagated.
    spin_hessian = step**2 * t_ij * (
        rho_flat[None, :] * dressed_spin_flat[:, None]
        + rho_flat[:, None] * dressed_spin_flat[None, :]
    )
    return {
        "field": float(field),
        "active_strings": active_strings,
        "solve_strings": solve_strings,
        "rapidity_points": rapidity_points,
        "rapidity_step": float(step),
        "rapidities": rapidities,
        "species_index": species_i,
        "filling": n_flat,
        "holes": f_flat,
        "rho_total": rho_flat,
        "dressed_scattering": t_ij,
        "reverse_dressed_scattering": t_ji,
        "velocity": v_flat,
        "diffusion_operator": diffusion,
        "static_covariance": static_covariance,
        "noise_covariance": noise_covariance,
        "velocity_vertex": velocity_vertex,
        "spin_projection": spin_projection,
        "spin_hessian": spin_hessian,
        "collision_rate": collision_rate,
    }


def _thermodynamic_fields_nodes(
    field: float,
    species: np.ndarray,
    rapidities: np.ndarray,
) -> dict[str, np.ndarray]:
    """Closed infinite-temperature TBA functions on arbitrary nodal pairs."""

    species = np.asarray(species, dtype=float)
    theta = np.asarray(rapidities, dtype=np.longdouble)
    s = species.astype(np.longdouble)
    h = np.longdouble(field)
    first = s / ((4.0 * theta**2 + s**2) * np.sinh(h * s))
    second = (s + 2.0) / (
        (4.0 * theta**2 + (s + 2.0) ** 2) * np.sinh(h * (s + 2.0))
    )
    rho_total = (
        2.0
        * np.sinh(h)
        * np.sinh(h * (s + 1.0))
        / (np.pi * np.sinh(2.0 * h))
        * (first - second)
    )
    first_energy = s / (
        (4.0 * theta**2 + s**2) ** 2 * np.sinh(h * s)
    )
    second_energy = (s + 2.0) / (
        (4.0 * theta**2 + (s + 2.0) ** 2) ** 2
        * np.sinh(h * (s + 2.0))
    )
    energy_derivative = (
        16.0
        * theta
        * np.sinh(h)
        * np.sinh(h * (s + 1.0))
        / np.sinh(2.0 * h)
        * (first_energy - second_energy)
    )
    velocity = energy_derivative / (2.0 * np.pi * rho_total)
    sh = np.sinh(field * (species + 1.0))
    dressed_magnetization = sh * (
        (species + 1.0) * np.cosh(field * (species + 1.0))
        - np.cosh(field) / np.sinh(field) * sh
    ) / (sh**2 - np.sinh(field) ** 2)
    filling = (
        np.sinh(field) / np.sinh((species + 1.0) * field)
    ) ** 2
    return {
        "filling": filling,
        "holes": 1.0 - filling,
        "rho_total": np.asarray(rho_total, dtype=float),
        "velocity": np.asarray(velocity, dtype=float),
        "dressed_magnetization": dressed_magnetization,
    }


def fixed_string_inner_weights_field(
    field: float,
    left_strings: np.ndarray,
    *,
    partner_xi_cutoff: float = 8.0,
    partner_xi_buffer: float = 6.0,
    rapidity_ratio_extent: float = 12.0,
    rapidity_ratio_map_alpha: float = 3.0,
    nodes_per_string: int = 20,
    kernel_theta_step: float = 0.25,
    string_boundary: str = "robin",
    susceptibility: float = 0.25,
) -> dict[str, object]:
    r"""Resolve selected inner strings against the complete finite-h tail.

    This evaluates their separate contributions to Eq. (16) and to the cross
    contraction while retaining every partner string through
    ``partner_xi_cutoff/h``.  Only selected rows of the dressed kernel are
    generated, so this remains usable when the partner cutoff is much larger
    than the fixed-string set.
    """

    h = float(field)
    selected = np.asarray(left_strings, dtype=int)
    if not 0.0 < h <= 0.35:
        raise ValueError("field must lie in (0,0.35]")
    if susceptibility <= 0.0 or nodes_per_string < 8:
        raise ValueError("susceptibility and node count must be positive")
    active_strings = int(ceil(partner_xi_cutoff / h))
    if np.any(selected < 1) or np.any(selected > active_strings):
        raise ValueError("left strings must lie below the partner cutoff")
    solve_strings = max(
        active_strings + 2,
        int(ceil((partner_xi_cutoff + partner_xi_buffer) / h)),
    )
    base_nodes, base_weights = np.polynomial.legendre.leggauss(nodes_per_string)
    alpha = float(rapidity_ratio_map_alpha)
    if alpha == 0.0:
        mapped_nodes = rapidity_ratio_extent * base_nodes
        mapped_weights = rapidity_ratio_extent * base_weights
    else:
        mapped_nodes = (
            rapidity_ratio_extent * np.sinh(alpha * base_nodes) / np.sinh(alpha)
        )
        mapped_weights = (
            rapidity_ratio_extent
            * alpha
            * np.cosh(alpha * base_nodes)
            / np.sinh(alpha)
            * base_weights
        )
    partner_species_values = np.arange(1, active_strings + 1, dtype=float)
    partner_species = np.repeat(partner_species_values, nodes_per_string)
    partner_rapidities = partner_species * np.tile(mapped_nodes, active_strings)
    partner_weights = partner_species * np.tile(mapped_weights, active_strings)
    partner_fields = _thermodynamic_fields_nodes(
        h, partner_species, partner_rapidities
    )
    maximum_difference = float(
        np.max(np.abs(partner_rapidities))
        + np.max(selected) * np.max(np.abs(mapped_nodes))
    )
    requested_points = int(ceil(2.0 * maximum_difference / kernel_theta_step))
    points = int(next_fast_len(max(requested_points, 256)))
    if points % 2:
        points = int(next_fast_len(points + 1))
    theta_extent = 0.5 * points * kernel_theta_step
    actual_step = 2.0 * theta_extent / points
    momenta = 2.0 * np.pi * np.fft.fftfreq(points, d=actual_step)
    kernel_hat = _dressed_kernel_rows_fourier(
        h,
        momenta,
        left_strings=selected,
        active_strings=active_strings,
        solve_strings=solve_strings,
        boundary=string_boundary,
    )
    kernel_grid = (
        fftshift(ifft(kernel_hat, axis=0), axes=0).real / actual_step
    )
    del kernel_hat

    partner_active = (
        partner_fields["filling"]
        * partner_fields["holes"]
        * partner_fields["rho_total"]
    )
    rows = []
    for row_index, string in enumerate(selected):
        left_species = np.full(nodes_per_string, float(string))
        left_rapidities = float(string) * mapped_nodes
        left_weights = float(string) * mapped_weights
        left_fields = _thermodynamic_fields_nodes(
            h, left_species, left_rapidities
        )
        differences = left_rapidities[:, None] - partner_rapidities[None, :]
        fractional = differences / actual_step + points // 2
        lower = np.floor(fractional).astype(int)
        interpolation = fractional - lower
        lower %= points
        upper = (lower + 1) % points
        partner_string_index = partner_species.astype(int) - 1
        kernel = (
            (1.0 - interpolation)
            * kernel_grid[lower, row_index, partner_string_index[None, :]]
            + interpolation
            * kernel_grid[upper, row_index, partner_string_index[None, :]]
        )
        pair_speed = np.abs(
            left_fields["velocity"][:, None]
            - partner_fields["velocity"][None, :]
        )
        collision = 0.5 * np.sum(
            partner_weights[None, :]
            * partner_active[None, :]
            * (kernel / left_fields["rho_total"][:, None]) ** 2
            * pair_speed,
            axis=1,
        )
        left_prefactor = (
            left_fields["filling"]
            * left_fields["holes"]
            * left_fields["rho_total"]
        )
        magnetization = left_fields["dressed_magnetization"]
        diagonal = np.sum(
            left_weights * left_prefactor * magnetization**2 * (2.0 * collision)
        ) / susceptibility
        cross_partner = (
            partner_fields["filling"]
            * partner_fields["holes"]
            * partner_fields["dressed_magnetization"]
        )
        cross = np.sum(
            left_weights[:, None]
            * partner_weights[None, :]
            * (
                left_fields["filling"]
                * left_fields["holes"]
                * magnetization
            )[:, None]
            * cross_partner[None, :]
            * pair_speed
            * kernel**2
        ) / susceptibility
        rows.append(
            {
                "string": int(string),
                "diagonal_weight": float(diagonal),
                "cross_weight": float(cross),
                "full_weight": float(diagonal - cross),
                "max_collision_rate": float(np.max(collision)),
            }
        )
    return {
        "field": h,
        "active_partner_strings": active_strings,
        "solve_strings": solve_strings,
        "left_strings": selected.tolist(),
        "nodes_per_string": int(nodes_per_string),
        "kernel_theta_step": float(actual_step),
        "rows": rows,
    }


def _zero_field_edge_kernel_rows_fourier(
    momenta: np.ndarray,
    *,
    left_strings: np.ndarray,
    partner_strings: int | None = None,
    right_strings: np.ndarray | None = None,
) -> np.ndarray:
    """Return exact zero-field edge kernel rows on a Fourier grid."""

    selected = np.asarray(left_strings, dtype=int)
    if selected.ndim != 1 or selected.size == 0:
        raise ValueError("left_strings must be a non-empty vector")
    if np.any(selected < 1):
        raise ValueError("left strings must be positive")
    if (partner_strings is None) == (right_strings is None):
        raise ValueError("supply exactly one partner cutoff or right-string vector")
    if right_strings is None:
        if int(partner_strings) < int(np.max(selected)):
            raise ValueError("partner cutoff must contain every selected string")
        right = np.arange(1, int(partner_strings) + 1, dtype=int)
    else:
        right = np.asarray(right_strings, dtype=int)
        if right.ndim != 1 or right.size == 0 or np.any(right < 1):
            raise ValueError("right_strings must be a non-empty positive vector")
    result = np.empty(
        (momenta.size, selected.size, right.size), dtype=np.float32
    )
    absolute_to_indices: dict[float, list[int]] = {}
    for index, momentum in enumerate(np.asarray(momenta, dtype=float)):
        key = float(np.round(abs(momentum), 14))
        absolute_to_indices.setdefault(key, []).append(index)
    for absolute_momentum, indices in absolute_to_indices.items():
        rows = zero_field_edge_dressed_scattering_fourier(
            selected[:, None], right[None, :], absolute_momentum
        )
        for index in indices:
            result[index] = rows
    return result


def zero_field_edge_weights(
    left_strings: np.ndarray,
    *,
    partner_string_cutoff: int = 128,
    partner_batch_size: int = 128,
    rapidity_ratio_extent: float = 12.0,
    rapidity_ratio_map_alpha: float = 3.0,
    nodes_per_string: int = 24,
    kernel_theta_step: float = 0.25,
    susceptibility: float = 0.25,
) -> dict[str, object]:
    r"""Compute the strict-zero-field edge coefficients ``q_s/h^2``.

    The function combines the exact discrete Green function of the edge
    dressing recurrence with the fixed-string ``h->0`` thermodynamics.  Both
    diagonal and cross contractions are retained.  Increasing
    ``partner_string_cutoff`` exposes the large-string overlap with the giant
    outer solution without taking a small but finite magnetic field.
    """

    selected = np.asarray(left_strings, dtype=int)
    cutoff = int(partner_string_cutoff)
    if selected.ndim != 1 or selected.size == 0 or np.any(selected < 1):
        raise ValueError("left_strings must be positive")
    if cutoff < int(np.max(selected)):
        raise ValueError("partner cutoff must contain selected strings")
    if nodes_per_string < 8 or kernel_theta_step <= 0.0:
        raise ValueError("node count and kernel step must be positive")
    if susceptibility <= 0.0 or rapidity_ratio_extent <= 0.0:
        raise ValueError("susceptibility and rapidity extent must be positive")

    base_nodes, base_weights = np.polynomial.legendre.leggauss(nodes_per_string)
    alpha = float(rapidity_ratio_map_alpha)
    if alpha == 0.0:
        mapped_nodes = rapidity_ratio_extent * base_nodes
        mapped_weights = rapidity_ratio_extent * base_weights
    else:
        mapped_nodes = (
            rapidity_ratio_extent * np.sinh(alpha * base_nodes) / np.sinh(alpha)
        )
        mapped_weights = (
            rapidity_ratio_extent
            * alpha
            * np.cosh(alpha * base_nodes)
            / np.sinh(alpha)
            * base_weights
        )
    batch_size = int(partner_batch_size)
    if batch_size < 1:
        raise ValueError("partner batch size must be positive")
    maximum_difference = float(
        (cutoff + np.max(selected)) * np.max(np.abs(mapped_nodes))
    )
    requested_points = int(np.ceil(2.0 * maximum_difference / kernel_theta_step))
    points = int(next_fast_len(max(requested_points, 256)))
    if points % 2:
        points = int(next_fast_len(points + 1))
    actual_step = float(kernel_theta_step)
    momenta = 2.0 * np.pi * np.fft.fftfreq(points, d=actual_step)
    left_cache = []
    collisions = []
    cross_sums = np.zeros(selected.size, dtype=float)
    for string in selected:
        left_species = np.full(nodes_per_string, float(string))
        left_rapidities = float(string) * mapped_nodes
        left_weights = float(string) * mapped_weights
        left_fields = zero_field_edge_thermodynamic_fields(
            left_species, left_rapidities
        )
        left_cache.append((left_rapidities, left_weights, left_fields))
        collisions.append(np.zeros(nodes_per_string, dtype=float))

    for first in range(1, cutoff + 1, batch_size):
        right_values = np.arange(
            first, min(cutoff + 1, first + batch_size), dtype=int
        )
        right_float = right_values.astype(float)
        partner_species = np.repeat(right_float, nodes_per_string)
        partner_rapidities = partner_species * np.tile(
            mapped_nodes, right_values.size
        )
        partner_weights = partner_species * np.tile(
            mapped_weights, right_values.size
        )
        partner_fields = zero_field_edge_thermodynamic_fields(
            partner_species, partner_rapidities
        )
        partner_active = (
            partner_fields["filling"]
            * partner_fields["holes"]
            * partner_fields["rho_total"]
        )
        cross_partner = (
            partner_fields["filling"]
            * partner_fields["holes"]
            * partner_fields["dressed_magnetization_per_field"]
        )
        kernel_hat = _zero_field_edge_kernel_rows_fourier(
            momenta,
            left_strings=selected,
            right_strings=right_values,
        )
        kernel_grid = (
            fftshift(ifft(kernel_hat, axis=0), axes=0).real / actual_step
        )
        del kernel_hat
        partner_index = np.repeat(
            np.arange(right_values.size, dtype=int), nodes_per_string
        )
        for row_index, (left_rapidities, left_weights, left_fields) in enumerate(
            left_cache
        ):
            differences = left_rapidities[:, None] - partner_rapidities[None, :]
            fractional = differences / actual_step + points // 2
            lower = np.floor(fractional).astype(int)
            interpolation = fractional - lower
            lower %= points
            upper = (lower + 1) % points
            kernel = (
                (1.0 - interpolation)
                * kernel_grid[lower, row_index, partner_index[None, :]]
                + interpolation
                * kernel_grid[upper, row_index, partner_index[None, :]]
            )
            pair_speed = np.abs(
                left_fields["velocity"][:, None]
                - partner_fields["velocity"][None, :]
            )
            collisions[row_index] += 0.5 * np.sum(
                partner_weights[None, :]
                * partner_active[None, :]
                * (kernel / left_fields["rho_total"][:, None]) ** 2
                * pair_speed,
                axis=1,
            )
            magnetization = left_fields["dressed_magnetization_per_field"]
            cross_sums[row_index] += np.sum(
                left_weights[:, None]
                * partner_weights[None, :]
                * (
                    left_fields["filling"]
                    * left_fields["holes"]
                    * magnetization
                )[:, None]
                * cross_partner[None, :]
                * pair_speed
                * kernel**2
            ) / susceptibility
        del kernel_grid

    rows = []
    for row_index, string in enumerate(selected):
        _, left_weights, left_fields = left_cache[row_index]
        magnetization = left_fields["dressed_magnetization_per_field"]
        left_prefactor = (
            left_fields["filling"]
            * left_fields["holes"]
            * left_fields["rho_total"]
        )
        diagonal = np.sum(
            left_weights
            * left_prefactor
            * magnetization**2
            * (2.0 * collisions[row_index])
        ) / susceptibility
        cross = cross_sums[row_index]
        rows.append(
            {
                "string": int(string),
                "diagonal_per_field_squared": float(diagonal),
                "cross_per_field_squared": float(cross),
                "full_per_field_squared": float(diagonal - cross),
            }
        )
    return {
        "partner_string_cutoff": cutoff,
        "partner_batch_size": batch_size,
        "left_strings": selected.tolist(),
        "nodes_per_string": int(nodes_per_string),
        "kernel_theta_step": actual_step,
        "rows": rows,
    }


def full_diffusion_operator_field_adaptive_rapidity(
    field: float,
    *,
    string_xi_cutoff: float = 3.0,
    string_xi_buffer: float = 3.0,
    scaled_rapidity_extent: float = 10.0,
    scaled_rapidity_map_alpha: float = 3.0,
    nodes_per_string: int = 20,
    kernel_theta_step: float = 0.25,
    string_boundary: str = "robin",
    operator_only: bool = False,
) -> dict[str, np.ndarray | float | int]:
    r"""Complete finite-field operator with string-adapted rapidity nodes.

    Each string is integrated in its natural coordinate ``theta=s*r`` using
    a sinh-mapped Gauss--Legendre rule in
    ``|r|<=scaled_rapidity_extent``.  The mapping concentrates nodes near the
    narrow central peak while retaining algebraic tails.  Consequently
    fixed strings remain resolved as ``h->0`` while giant strings retain a
    fixed resolution in ``u=h theta``.  The dressed scattering kernel is still
    obtained from the complete string-space recurrence and is interpolated on
    a separate uniform theta grid.  Every small--giant cross block is kept.
    """

    if not 0.0 < field <= 0.35:
        raise ValueError("field must lie in (0,0.35]")
    if nodes_per_string < 8:
        raise ValueError("nodes_per_string must be at least eight")
    if (
        scaled_rapidity_extent <= 0.0
        or scaled_rapidity_map_alpha < 0.0
        or kernel_theta_step <= 0.0
    ):
        raise ValueError("rapidity extent and kernel step must be positive")
    active_strings = int(ceil(string_xi_cutoff / field))
    solve_strings = max(
        active_strings + 2,
        int(ceil((string_xi_cutoff + string_xi_buffer) / field)),
    )

    legendre_nodes, legendre_weights = np.polynomial.legendre.leggauss(
        nodes_per_string
    )
    species_values = np.arange(1, active_strings + 1, dtype=float)
    species = np.repeat(species_values, nodes_per_string)
    if scaled_rapidity_map_alpha == 0.0:
        mapped_nodes = scaled_rapidity_extent * legendre_nodes
        mapped_weights = scaled_rapidity_extent * legendre_weights
    else:
        alpha = float(scaled_rapidity_map_alpha)
        mapped_nodes = (
            scaled_rapidity_extent
            * np.sinh(alpha * legendre_nodes)
            / np.sinh(alpha)
        )
        mapped_weights = (
            scaled_rapidity_extent
            * alpha
            * np.cosh(alpha * legendre_nodes)
            / np.sinh(alpha)
            * legendre_weights
        )
    rapidities = species * np.tile(mapped_nodes, active_strings)
    quadrature_weights = species * np.tile(mapped_weights, active_strings)
    species_index = species.astype(int) - 1

    maximum_difference = 2.05 * scaled_rapidity_extent * active_strings
    requested_points = int(ceil(2.0 * maximum_difference / kernel_theta_step))
    points = int(next_fast_len(max(requested_points, 256)))
    if points % 2:
        points = int(next_fast_len(points + 1))
    theta_extent = 0.5 * points * kernel_theta_step
    actual_step = 2.0 * theta_extent / points
    momenta = 2.0 * np.pi * np.fft.fftfreq(points, d=actual_step)
    kernel_hat, _ = _dressed_kernel_fourier(
        field,
        momenta,
        active_strings=active_strings,
        solve_strings=solve_strings,
        boundary=string_boundary,
    )
    dressed_grid = fftshift(ifft(kernel_hat, axis=0), axes=0).real / actual_step
    del kernel_hat

    differences = rapidities[:, None] - rapidities[None, :]
    fractional = differences / actual_step + points // 2
    lower = np.floor(fractional).astype(int)
    interpolation = fractional - lower
    lower %= points
    upper = (lower + 1) % points
    left_species = species_index[:, None]
    right_species = species_index[None, :]
    t_ij = (
        (1.0 - interpolation) * dressed_grid[lower, left_species, right_species]
        + interpolation * dressed_grid[upper, left_species, right_species]
    )
    reverse_fractional = -differences / actual_step + points // 2
    reverse_lower = np.floor(reverse_fractional).astype(int)
    reverse_interpolation = reverse_fractional - reverse_lower
    reverse_lower %= points
    reverse_upper = (reverse_lower + 1) % points
    t_ji = (
        (1.0 - reverse_interpolation)
        * dressed_grid[reverse_lower, right_species, left_species]
        + reverse_interpolation
        * dressed_grid[reverse_upper, right_species, left_species]
    )
    del (
        dressed_grid,
        differences,
        fractional,
        lower,
        upper,
        interpolation,
        reverse_fractional,
        reverse_lower,
        reverse_upper,
        reverse_interpolation,
    )

    fields = _thermodynamic_fields_nodes(field, species, rapidities)
    assembled = _assemble_nodal_diffusion_noise_weighted(
        fields["filling"],
        fields["rho_total"],
        fields["velocity"],
        t_ij,
        t_ji,
        quadrature_weights,
        retain_transition_kernel=not operator_only,
    )
    rho = fields["rho_total"]
    velocity = np.nan_to_num(fields["velocity"], copy=False)
    magnetization = fields["dressed_magnetization"]
    spin_projection = quadrature_weights * rho * magnetization
    if operator_only:
        del t_ij, t_ji
    result = {
        "field": float(field),
        "active_strings": active_strings,
        "solve_strings": solve_strings,
        "nodes_per_string": nodes_per_string,
        "mode_count": int(species.size),
        "scaled_rapidity_extent": float(scaled_rapidity_extent),
        "scaled_rapidity_map_alpha": float(scaled_rapidity_map_alpha),
        "kernel_theta_step": float(actual_step),
        "species_index": species_index,
        "species": species,
        "rapidities": rapidities,
        "quadrature_weights": quadrature_weights,
        "filling": fields["filling"],
        "holes": fields["holes"],
        "rho_total": rho,
        "velocity": velocity,
        "diffusion_operator": assembled["diffusion_operator"],
        "static_covariance": assembled["static_covariance"],
        "noise_covariance": assembled["noise_covariance"],
        "spin_projection": spin_projection,
        "collision_rate": assembled["collision_rate"],
    }
    if not operator_only:
        velocity_vertex = (
            quadrature_weights[None, :]
            * t_ij
            * rho[None, :]
            / rho[:, None]
            * (velocity[None, :] - velocity[:, None])
        )
        spin_hessian = (
            quadrature_weights[:, None]
            * quadrature_weights[None, :]
            * t_ij
            * (
                rho[None, :] * magnetization[:, None]
                + rho[:, None] * magnetization[None, :]
            )
        )
        result.update(
            {
                "dressed_scattering": t_ij,
                "reverse_dressed_scattering": t_ji,
                "velocity_vertex": velocity_vertex,
                "spin_hessian": spin_hessian,
            }
        )
    return result


def _assemble_nodal_diffusion_noise(
    filling: np.ndarray,
    rho_total: np.ndarray,
    velocity: np.ndarray,
    dressed_scattering: np.ndarray,
    reverse_dressed_scattering: np.ndarray,
    rapidity_step: float,
) -> dict[str, np.ndarray]:
    """Assemble D, C and Q from nodal dressed thermodynamic data."""

    holes = 1.0 - filling
    pair_speed = np.abs(velocity[:, None] - velocity[None, :])
    active_weight = filling * rho_total * holes
    transition_kernel = (
        0.5
        * active_weight[:, None]
        * dressed_scattering
        * reverse_dressed_scattering
        * pair_speed
        / rho_total[:, None] ** 2
    )
    collision_rate = 0.5 * rapidity_step * np.sum(
        active_weight[None, :]
        * (dressed_scattering / rho_total[:, None]) ** 2
        * pair_speed,
        axis=1,
    )
    diffusion = 2.0 * (
        np.diag(collision_rate) - rapidity_step * transition_kernel
    )
    covariance_diagonal = (
        filling * holes / rho_total / rapidity_step
    )
    covariance = np.diag(covariance_diagonal)
    # C is exactly diagonal in nodal occupation coordinates.  Writing the
    # product as row/column scaling is algebraically identical and avoids an
    # otherwise cubic dense multiplication in large regulator audits.
    noise = 0.5 * (
        diffusion * covariance_diagonal[None, :]
        + covariance_diagonal[:, None] * diffusion.T
    )
    noise = 0.5 * (noise + noise.T)
    return {
        "diffusion_operator": diffusion,
        "static_covariance": covariance,
        "noise_covariance": noise,
        "collision_rate": collision_rate,
        "transition_kernel": transition_kernel,
    }


def _assemble_nodal_diffusion_noise_weighted(
    filling: np.ndarray,
    rho_total: np.ndarray,
    velocity: np.ndarray,
    dressed_scattering: np.ndarray,
    reverse_dressed_scattering: np.ndarray,
    quadrature_weights: np.ndarray,
    *,
    retain_transition_kernel: bool = True,
) -> dict[str, np.ndarray]:
    """Assemble the full nodal operators for arbitrary rapidity weights."""

    filling = np.asarray(filling, dtype=float)
    rho_total = np.asarray(rho_total, dtype=float)
    velocity = np.asarray(velocity, dtype=float)
    weights = np.asarray(quadrature_weights, dtype=float)
    if np.any(weights <= 0.0):
        raise ValueError("quadrature weights must be positive")
    holes = 1.0 - filling
    pair_speed = np.abs(velocity[:, None] - velocity[None, :])
    active_weight = filling * rho_total * holes
    transition_kernel = (
        0.5
        * active_weight[:, None]
        * dressed_scattering
        * reverse_dressed_scattering
        * pair_speed
        / rho_total[:, None] ** 2
    )
    collision_rate = 0.5 * np.sum(
        weights[None, :]
        * active_weight[None, :]
        * (dressed_scattering / rho_total[:, None]) ** 2
        * pair_speed,
        axis=1,
    )
    diffusion = 2.0 * (
        np.diag(collision_rate) - transition_kernel * weights[None, :]
    )
    covariance_diagonal = filling * holes / rho_total / weights
    covariance = np.diag(covariance_diagonal)
    noise = 0.5 * (
        diffusion * covariance_diagonal[None, :]
        + covariance_diagonal[:, None] * diffusion.T
    )
    noise = 0.5 * (noise + noise.T)
    result = {
        "diffusion_operator": diffusion,
        "static_covariance": covariance,
        "noise_covariance": noise,
        "collision_rate": collision_rate,
    }
    if retain_transition_kernel:
        result["transition_kernel"] = transition_kernel
    return result


def full_diffusion_noise_frechet_derivatives(
    modes: dict[str, np.ndarray | float | int],
    *,
    derivative_indices: np.ndarray | None = None,
) -> dict[str, np.ndarray]:
    r"""Differentiate the complete nodal ``D``, ``C`` and ``Q`` matrices.

    The leading axis labels the occupation node with respect to which the
    derivative is taken.  Dressing is differentiated exactly through
    ``d T^dr = T^dr W(d n) T^dr``, where ``W`` is either the arbitrary
    positive rapidity quadrature or the uniform nodal step.  Selecting a
    subset of derivative indices permits finite-difference tests without
    allocating the full rank-three tensors at large cutoffs.  In particular,
    the derivatives now use the same string-adaptive measure as the regulated
    small-string/giant-string operator; no uniform-grid surrogate is inserted
    into the nonlinear vertices.
    """

    n = np.asarray(modes["filling"])
    rho = np.asarray(modes["rho_total"])
    velocity = np.asarray(modes["velocity"])
    scattering = np.asarray(modes["dressed_scattering"])
    reverse = np.asarray(modes["reverse_dressed_scattering"])
    vertex = np.asarray(modes["velocity_vertex"])
    diffusion = np.asarray(modes["diffusion_operator"])
    covariance = np.asarray(modes["static_covariance"])
    count = n.size
    if "quadrature_weights" in modes:
        weights = np.asarray(modes["quadrature_weights"], dtype=float)
    elif "rapidity_step" in modes:
        weights = np.full(count, float(modes["rapidity_step"]), dtype=float)
    else:
        raise ValueError(
            "modes must provide quadrature_weights or rapidity_step"
        )
    if weights.shape != (count,) or np.any(~np.isfinite(weights)) or np.any(
        weights <= 0.0
    ):
        raise ValueError("quadrature weights must be finite and positive")
    indices = (
        np.arange(count, dtype=int)
        if derivative_indices is None
        else np.asarray(derivative_indices, dtype=int)
    )
    if np.any(indices < 0) or np.any(indices >= count):
        raise ValueError("derivative index outside nodal range")

    holes = 1.0 - n
    speed_difference = velocity[:, None] - velocity[None, :]
    pair_speed = np.abs(speed_difference)
    speed_sign = np.sign(speed_difference)
    active_weight = n * rho * holes
    diffusion_derivatives = []
    covariance_derivatives = []
    noise_derivatives = []
    rho_derivatives = []
    scattering_derivatives = []

    for node in indices:
        delta = np.zeros(count)
        delta[node] = 1.0
        node_weight = weights[node]
        d_rho = node_weight * scattering[:, node] * rho[node]
        d_velocity = vertex[:, node]
        d_scattering = (
            node_weight
            * scattering[:, node, None]
            * scattering[node, None, :]
        )
        d_reverse = (
            node_weight
            * reverse[:, node, None]
            * reverse[node, None, :]
        )
        d_speed = speed_sign * (
            d_velocity[:, None] - d_velocity[None, :]
        )
        d_active = (
            delta * rho * (holes - n) + n * holes * d_rho
        )

        ratio = scattering / rho[:, None]
        d_ratio = (
            d_scattering / rho[:, None]
            - scattering * d_rho[:, None] / rho[:, None] ** 2
        )
        d_collision = 0.5 * np.sum(
            weights[None, :]
            * (
                d_active[None, :] * ratio**2 * pair_speed
                + active_weight[None, :]
                * 2.0
                * ratio
                * d_ratio
                * pair_speed
                + active_weight[None, :] * ratio**2 * d_speed
            ),
            axis=1,
        )
        numerator = scattering * reverse
        d_numerator = d_scattering * reverse + scattering * d_reverse
        d_transition = 0.5 * (
            d_active[:, None] * numerator * pair_speed / rho[:, None] ** 2
            + active_weight[:, None]
            * d_numerator
            * pair_speed
            / rho[:, None] ** 2
            + active_weight[:, None]
            * numerator
            * d_speed
            / rho[:, None] ** 2
            - 2.0
            * active_weight[:, None]
            * numerator
            * pair_speed
            * d_rho[:, None]
            / rho[:, None] ** 3
        )
        d_diffusion = 2.0 * (
            np.diag(d_collision) - d_transition * weights[None, :]
        )
        d_covariance_diagonal = (
            delta * (holes - n) / (rho * weights)
            - n * holes * d_rho / (rho**2 * weights)
        )
        d_covariance = np.diag(d_covariance_diagonal)
        d_noise = 0.5 * (
            d_diffusion @ covariance
            + diffusion @ d_covariance
            + d_covariance @ diffusion.T
            + covariance @ d_diffusion.T
        )
        d_noise = 0.5 * (d_noise + d_noise.T)
        diffusion_derivatives.append(d_diffusion)
        covariance_derivatives.append(d_covariance)
        noise_derivatives.append(d_noise)
        rho_derivatives.append(d_rho)
        scattering_derivatives.append(d_scattering)

    return {
        "derivative_indices": indices,
        "diffusion_derivative": np.asarray(diffusion_derivatives),
        "static_covariance_derivative": np.asarray(covariance_derivatives),
        "noise_covariance_derivative": np.asarray(noise_derivatives),
        "rho_total_derivative": np.asarray(rho_derivatives),
        "dressed_scattering_derivative": np.asarray(scattering_derivatives),
    }


def full_diffusion_noise_directional_frechet_derivative(
    modes: dict[str, np.ndarray | float | int],
    direction: np.ndarray,
) -> dict[str, np.ndarray]:
    r"""Apply the complete ``(D,C,Q)`` Jacobian to one occupation direction.

    This is the matrix-free-in-derivative-index counterpart of
    :func:`full_diffusion_noise_frechet_derivatives`.  It never forms the
    rank-three arrays ``dD[l,i,j]`` or ``dQ[l,i,j]``.  For quadrature matrix
    ``W`` and supplied direction ``x`` it evaluates the dressing variation as

    ``dT = T W diag(x) T``

    with two dense matrix products, then propagates that variation through
    the full diagonal-minus-transition diffusion operator and the FDT
    identity.  Memory is therefore ``O(N_mode**2)`` rather than
    ``O(N_mode**3)``.  No projection onto physical spin or a finite auxiliary
    mode is made by this routine.
    """

    n = np.asarray(modes["filling"], dtype=float)
    rho = np.asarray(modes["rho_total"], dtype=float)
    velocity = np.asarray(modes["velocity"], dtype=float)
    scattering = np.asarray(modes["dressed_scattering"], dtype=float)
    reverse = np.asarray(modes["reverse_dressed_scattering"], dtype=float)
    vertex = np.asarray(modes["velocity_vertex"], dtype=float)
    diffusion = np.asarray(modes["diffusion_operator"], dtype=float)
    covariance = np.asarray(modes["static_covariance"], dtype=float)
    count = n.size
    vector = np.asarray(direction)
    if vector.shape != (count,) or np.any(~np.isfinite(vector)):
        raise ValueError("direction must be a finite vector matching the modes")
    if "quadrature_weights" in modes:
        weights = np.asarray(modes["quadrature_weights"], dtype=float)
    elif "rapidity_step" in modes:
        weights = np.full(count, float(modes["rapidity_step"]), dtype=float)
    else:
        raise ValueError(
            "modes must provide quadrature_weights or rapidity_step"
        )
    if weights.shape != (count,) or np.any(~np.isfinite(weights)) or np.any(
        weights <= 0.0
    ):
        raise ValueError("quadrature weights must be finite and positive")

    weighted_direction = weights * vector
    d_rho = scattering @ (weighted_direction * rho)
    d_velocity = vertex @ vector
    d_scattering = (scattering * weighted_direction[None, :]) @ scattering
    d_reverse = (reverse * weighted_direction[None, :]) @ reverse

    holes = 1.0 - n
    speed_difference = velocity[:, None] - velocity[None, :]
    pair_speed = np.abs(speed_difference)
    d_speed = np.sign(speed_difference) * (
        d_velocity[:, None] - d_velocity[None, :]
    )
    active_weight = n * rho * holes
    d_active = vector * rho * (holes - n) + n * holes * d_rho
    ratio = scattering / rho[:, None]
    d_ratio = (
        d_scattering / rho[:, None]
        - scattering * d_rho[:, None] / rho[:, None] ** 2
    )
    d_collision = 0.5 * np.sum(
        weights[None, :]
        * (
            d_active[None, :] * ratio**2 * pair_speed
            + 2.0
            * active_weight[None, :]
            * ratio
            * d_ratio
            * pair_speed
            + active_weight[None, :] * ratio**2 * d_speed
        ),
        axis=1,
    )
    numerator = scattering * reverse
    d_numerator = d_scattering * reverse + scattering * d_reverse
    d_transition = 0.5 * (
        d_active[:, None] * numerator * pair_speed / rho[:, None] ** 2
        + active_weight[:, None]
        * d_numerator
        * pair_speed
        / rho[:, None] ** 2
        + active_weight[:, None] * numerator * d_speed / rho[:, None] ** 2
        - 2.0
        * active_weight[:, None]
        * numerator
        * pair_speed
        * d_rho[:, None]
        / rho[:, None] ** 3
    )
    d_diffusion = 2.0 * (
        np.diag(d_collision) - d_transition * weights[None, :]
    )
    d_covariance_diagonal = (
        vector * (holes - n) / (rho * weights)
        - n * holes * d_rho / (rho**2 * weights)
    )
    covariance_diagonal = np.diag(covariance)
    d_noise = 0.5 * (
        d_diffusion * covariance_diagonal[None, :]
        + diffusion * d_covariance_diagonal[None, :]
        + d_covariance_diagonal[:, None] * diffusion.T
        + covariance_diagonal[:, None] * d_diffusion.T
    )
    # This is an analytic directional derivative.  Complex Fourier
    # directions are handled by complex-linear extension, hence transpose
    # rather than Hermitian conjugation in the differentiated FDT identity.
    d_noise = 0.5 * (d_noise + d_noise.T)
    return {
        "direction": vector,
        "diffusion_directional_derivative": d_diffusion,
        "static_covariance_directional_derivative": np.diag(
            d_covariance_diagonal
        ),
        "noise_covariance_directional_derivative": d_noise,
        "rho_total_directional_derivative": d_rho,
        "velocity_directional_derivative": d_velocity,
        "dressed_scattering_directional_derivative": d_scattering,
        "reverse_dressed_scattering_directional_derivative": d_reverse,
    }


def projected_diffusion_vertex_action(
    modes: dict[str, np.ndarray | float | int],
    projection: np.ndarray,
    direction: np.ndarray,
) -> np.ndarray:
    r"""Apply the physical projected diffusion vertex without storing it.

    The dense one-loop implementation defines

    ``R[j,l] = sum_a projection[a] dD[l,a,j]``.

    This routine returns ``R @ direction`` from a single directional
    derivative of the complete diffusion operator.  It is the primitive
    needed to evaluate the quadratic diffusion force stochastically or by a
    randomized Wick contraction with ``O(N_mode**2)`` memory.
    """

    vector = np.asarray(direction)
    physical_projection = np.asarray(projection)
    if physical_projection.shape != vector.shape:
        raise ValueError("projection and direction must have matching shapes")
    derivative = full_diffusion_noise_directional_frechet_derivative(
        modes, vector
    )["diffusion_directional_derivative"]
    return np.asarray(derivative).T @ physical_projection


def effective_velocity_second_frechet_derivative(
    modes: dict[str, np.ndarray | float | int],
) -> dict[str, np.ndarray | float]:
    r"""Return the exact nodal Hessian of the dressed effective velocity.

    For quadrature weights ``w_B`` the first derivative is

    ``V_AB = w_B Tdr_AB rho_B/rho_A (v_B-v_A)``.

    Differentiating once more uses only

    ``d_C Tdr_AB = w_C Tdr_AC Tdr_CB``,
    ``d_C rho_A = w_C Tdr_AC rho_C``, and ``d_C v_A=V_AC``.

    The returned tensor is ordered ``(A,B,C)`` and is symmetrized in the two
    derivative indices after reporting the raw Schwarz residual.  This is the
    cubic advective vertex needed for the equilibrium tadpole/counterterm;
    it is not a finite-difference fit.
    """

    rho = np.asarray(modes["rho_total"], dtype=float)
    velocity = np.asarray(modes["velocity"], dtype=float)
    scattering = np.asarray(modes["dressed_scattering"], dtype=float)
    vertex = np.asarray(modes["velocity_vertex"], dtype=float)
    if "quadrature_weights" in modes:
        weights = np.asarray(modes["quadrature_weights"], dtype=float)
    else:
        weights = np.full(rho.size, float(modes["rapidity_step"]))
    count = rho.size
    if scattering.shape != (count, count) or vertex.shape != (count, count):
        raise ValueError("dressed scattering/velocity vertex has wrong shape")
    if weights.shape != (count,) or np.any(rho <= 0.0):
        raise ValueError("invalid quadrature weights or total density")

    hessian = np.empty((count, count, count), dtype=float)
    delta_v = velocity[None, :] - velocity[:, None]
    for node in range(count):
        weight_c = weights[node]
        d_scattering = (
            weight_c
            * scattering[:, node, None]
            * scattering[node, None, :]
        )
        d_rho = weight_c * scattering[:, node] * rho[node]
        density_ratio = rho[None, :] / rho[:, None]
        d_density_ratio = (
            d_rho[None, :] / rho[:, None]
            - rho[None, :] * d_rho[:, None] / rho[:, None] ** 2
        )
        d_delta_v = vertex[:, node][None, :] - vertex[:, node][:, None]
        hessian[:, :, node] = weights[None, :] * (
            d_scattering * density_ratio * delta_v
            + scattering * d_density_ratio * delta_v
            + scattering * density_ratio * d_delta_v
        )

    raw_residual = np.linalg.norm(hessian - np.swapaxes(hessian, 1, 2)) / max(
        np.linalg.norm(hessian), np.finfo(float).tiny
    )
    hessian = 0.5 * (hessian + np.swapaxes(hessian, 1, 2))
    return {
        "velocity_hessian": hessian,
        "raw_schwarz_relative_residual": float(raw_residual),
        "derivative_method": "analytic_dressing_frechet",
    }


def full_diffusion_noise_second_diagonal_frechet_derivatives(
    modes: dict[str, np.ndarray | float | int],
) -> dict[str, np.ndarray | float | str]:
    r"""Return ``d_c^2(D,C,Q)`` by analytic second-order dressing jets.

    The equilibrium occupation covariance is diagonal in the nodal basis, so
    a one-cubic-vertex tadpole contracts only the diagonal Hessian directions
    ``d^2/dn_c^2``.  Computing those directions avoids allocating the full
    rank-four Hessian while retaining exactly the information required by the
    equilibrium counterterm.

    This implementation currently targets the uniform-rapidity nodal operator
    used by the finite-cutoff one-loop certificate.  It differentiates the
    fixed branch of ``abs(v_i-v_j)``; velocity-crossing distributions are not
    included and are reported as a regulator condition.
    """

    if "rapidity_step" not in modes:
        raise ValueError("second diagonal derivatives require uniform rapidity nodes")
    n = np.asarray(modes["filling"], dtype=float)
    rho = np.asarray(modes["rho_total"], dtype=float)
    velocity = np.asarray(modes["velocity"], dtype=float)
    scattering = np.asarray(modes["dressed_scattering"], dtype=float)
    reverse = np.asarray(modes["reverse_dressed_scattering"], dtype=float)
    vertex = np.asarray(modes["velocity_vertex"], dtype=float)
    diffusion = np.asarray(modes["diffusion_operator"], dtype=float)
    covariance = np.asarray(modes["static_covariance"], dtype=float)
    step = float(modes["rapidity_step"])
    count = n.size
    velocity_second = np.asarray(
        effective_velocity_second_frechet_derivative(modes)["velocity_hessian"]
    )

    def multiply(left, right):
        a0, a1, a2 = left
        b0, b1, b2 = right
        return (
            a0 * b0,
            a1 * b0 + a0 * b1,
            a2 * b0 + 2.0 * a1 * b1 + a0 * b2,
        )

    def reciprocal(value):
        a0, a1, a2 = value
        return (
            1.0 / a0,
            -a1 / a0**2,
            2.0 * a1**2 / a0**3 - a2 / a0**2,
        )

    diffusion_second = []
    covariance_second = []
    noise_second = []
    rho_second = []
    scattering_second = []
    velocity_second_diagonal = []
    speed_difference = velocity[:, None] - velocity[None, :]
    speed_sign = np.sign(speed_difference)
    holes = 1.0 - n

    for node in range(count):
        delta = np.zeros(count)
        delta[node] = 1.0
        d_scattering = step * scattering[:, node, None] * scattering[node, None, :]
        d2_scattering = (
            2.0
            * step**2
            * scattering[node, node]
            * scattering[:, node, None]
            * scattering[node, None, :]
        )
        d_reverse = step * reverse[:, node, None] * reverse[node, None, :]
        d2_reverse = (
            2.0
            * step**2
            * reverse[node, node]
            * reverse[:, node, None]
            * reverse[node, None, :]
        )
        d_rho = step * scattering[:, node] * rho[node]
        d2_rho = (
            2.0
            * step**2
            * scattering[:, node]
            * scattering[node, node]
            * rho[node]
        )
        d_velocity = vertex[:, node]
        d2_velocity = velocity_second[:, node, node]

        n_jet = (n, delta, np.zeros_like(n))
        holes_jet = (holes, -delta, np.zeros_like(n))
        rho_jet = (rho, d_rho, d2_rho)
        active = multiply(multiply(n_jet, holes_jet), rho_jet)
        scattering_jet = (scattering, d_scattering, d2_scattering)
        reverse_jet = (reverse, d_reverse, d2_reverse)
        rho_left = tuple(value[:, None] for value in rho_jet)
        ratio = multiply(scattering_jet, reciprocal(rho_left))
        speed = (
            np.abs(speed_difference),
            speed_sign * (d_velocity[:, None] - d_velocity[None, :]),
            speed_sign * (d2_velocity[:, None] - d2_velocity[None, :]),
        )
        collision_integrand = multiply(
            tuple(value[None, :] for value in active),
            multiply(multiply(ratio, ratio), speed),
        )
        collision = tuple(0.5 * step * np.sum(value, axis=1) for value in collision_integrand)

        numerator = multiply(scattering_jet, reverse_jet)
        inverse_rho_squared = multiply(reciprocal(rho_left), reciprocal(rho_left))
        transition = multiply(
            tuple(value[:, None] for value in active),
            multiply(numerator, multiply(speed, inverse_rho_squared)),
        )
        transition = tuple(0.5 * value for value in transition)
        diffusion_jet = tuple(
            2.0 * (np.diag(collision[order]) - step * transition[order])
            for order in range(3)
        )
        covariance_diagonal = multiply(
            multiply(n_jet, holes_jet), reciprocal(rho_jet)
        )
        covariance_jet = tuple(
            np.diag(value / step) for value in covariance_diagonal
        )
        d0, d1, d2 = diffusion_jet
        c0, c1, c2 = covariance_jet
        q2 = 0.5 * (
            d2 @ c0
            + 2.0 * d1 @ c1
            + d0 @ c2
            + c2 @ d0.T
            + 2.0 * c1 @ d1.T
            + c0 @ d2.T
        )
        q2 = 0.5 * (q2 + q2.T)

        # Values and first derivatives reproduce the independently assembled
        # operator; retaining this check catches jet-product mistakes before
        # the second derivative is used in a counterterm.
        if not np.allclose(d0, diffusion, rtol=2e-12, atol=2e-12):
            raise RuntimeError("diffusion jet value does not reproduce background")
        if not np.allclose(c0, covariance, rtol=2e-12, atol=2e-12):
            raise RuntimeError("covariance jet value does not reproduce background")
        diffusion_second.append(d2)
        covariance_second.append(c2)
        noise_second.append(q2)
        rho_second.append(d2_rho)
        scattering_second.append(d2_scattering)
        velocity_second_diagonal.append(d2_velocity)

    return {
        "derivative_indices": np.arange(count, dtype=int),
        "diffusion_second_diagonal_derivative": np.asarray(diffusion_second),
        "static_covariance_second_diagonal_derivative": np.asarray(covariance_second),
        "noise_covariance_second_diagonal_derivative": np.asarray(noise_second),
        "rho_total_second_diagonal_derivative": np.asarray(rho_second),
        "dressed_scattering_second_diagonal_derivative": np.asarray(scattering_second),
        "velocity_second_diagonal_derivative": np.asarray(velocity_second_diagonal),
        "derivative_method": "analytic_second_order_dressing_jet",
        "absolute_velocity_branch": "fixed_sign_away_from_velocity_crossings",
    }


def symmetric_noise_root_frechet_derivatives(
    noise_covariance: np.ndarray,
    noise_covariance_derivative: np.ndarray,
    *,
    relative_eigenvalue_floor: float = 1.0e-12,
) -> dict[str, np.ndarray | float]:
    r"""Differentiate the symmetric PSD root ``B`` of ``Q=B B^T``.

    In the eigenbasis of ``B``, its Frechet derivative solves the Sylvester
    equation ``B dB + dB B = dQ``.  Null directions below the declared floor
    are projected out and the discarded residual is reported explicitly.
    """

    noise = 0.5 * (
        np.asarray(noise_covariance) + np.asarray(noise_covariance).T
    )
    derivatives = np.asarray(noise_covariance_derivative)
    eigenvalues, eigenvectors = np.linalg.eigh(noise)
    scale = max(float(np.max(np.abs(eigenvalues))), np.finfo(float).tiny)
    floor = relative_eigenvalue_floor * scale
    roots = np.sqrt(np.maximum(eigenvalues, 0.0))
    supported = roots[:, None] + roots[None, :] > np.sqrt(floor)
    root = (eigenvectors * roots) @ eigenvectors.T
    root_derivatives = []
    residuals = []
    denominators = roots[:, None] + roots[None, :]
    for derivative in derivatives:
        transformed = eigenvectors.T @ derivative @ eigenvectors
        transformed_root_derivative = np.divide(
            transformed,
            denominators,
            out=np.zeros_like(transformed),
            where=supported,
        )
        root_derivative = (
            eigenvectors @ transformed_root_derivative @ eigenvectors.T
        )
        reconstructed = root @ root_derivative + root_derivative @ root
        residuals.append(
            np.linalg.norm(reconstructed - derivative)
            / max(np.linalg.norm(derivative), np.finfo(float).tiny)
        )
        root_derivatives.append(root_derivative)
    return {
        "noise_root": root,
        "noise_root_derivative": np.asarray(root_derivatives),
        "relative_nullspace_residual": np.asarray(residuals),
        "eigenvalue_floor": float(floor),
    }


def symmetric_noise_root_frechet_setup(
    noise_covariance: np.ndarray,
    *,
    relative_eigenvalue_floor: float = 1.0e-12,
) -> dict[str, np.ndarray | float]:
    r"""Precompute the symmetric-root Sylvester solver for one background.

    The returned arrays require ``O(N_mode**2)`` storage and may be reused for
    arbitrarily many occupation directions.  This separates the one-time
    eigendecomposition of ``Q`` from applications of ``dQ -> dB``.
    """

    noise = np.asarray(noise_covariance)
    noise = 0.5 * (noise + noise.T)
    eigenvalues, eigenvectors = np.linalg.eigh(noise)
    scale = max(float(np.max(np.abs(eigenvalues))), np.finfo(float).tiny)
    floor = relative_eigenvalue_floor * scale
    if float(np.min(eigenvalues)) < -10.0 * floor:
        raise ValueError("noise covariance is not positive semidefinite")
    roots = np.sqrt(np.maximum(eigenvalues, 0.0))
    denominators = roots[:, None] + roots[None, :]
    supported = denominators > np.sqrt(floor)
    inverse_denominators = np.divide(
        1.0,
        denominators,
        out=np.zeros_like(denominators),
        where=supported,
    )
    root = (eigenvectors * roots) @ eigenvectors.T
    return {
        "noise_root": root,
        "eigenvectors": eigenvectors,
        "inverse_sylvester_denominators": inverse_denominators,
        "supported_sylvester_subspace": supported,
        "eigenvalue_floor": float(floor),
    }


def apply_symmetric_noise_root_frechet(
    setup: dict[str, np.ndarray | float],
    noise_covariance_directional_derivative: np.ndarray,
) -> dict[str, np.ndarray | float]:
    r"""Apply a precomputed ``dQ -> dB`` symmetric-root derivative."""

    root = np.asarray(setup["noise_root"])
    eigenvectors = np.asarray(setup["eigenvectors"])
    inverse_denominators = np.asarray(
        setup["inverse_sylvester_denominators"]
    )
    derivative = np.asarray(noise_covariance_directional_derivative)
    if derivative.shape != root.shape:
        raise ValueError("noise derivative must match the root setup")
    transformed = eigenvectors.T @ derivative @ eigenvectors
    transformed_root_derivative = transformed * inverse_denominators
    root_derivative = (
        eigenvectors @ transformed_root_derivative @ eigenvectors.T
    )
    reconstructed = root @ root_derivative + root_derivative @ root
    residual = float(
        np.linalg.norm(reconstructed - derivative)
        / max(np.linalg.norm(derivative), np.finfo(float).tiny)
    )
    return {
        "noise_root_directional_derivative": root_derivative,
        "relative_nullspace_residual": residual,
    }


def projected_noise_root_vertex_action(
    modes: dict[str, np.ndarray | float | int],
    projection: np.ndarray,
    direction: np.ndarray,
    root_setup: dict[str, np.ndarray | float],
) -> dict[str, np.ndarray | float]:
    r"""Apply the physical projected multiplicative-noise vertex.

    If ``Z[l,r]=p_a dB[l,a,r]``, this routine returns ``Z.T @ direction``
    without storing ``dB[l,a,r]``.  It uses the complete directional ``dQ``
    and the reusable symmetric-root Sylvester setup.
    """

    vector = np.asarray(direction)
    physical_projection = np.asarray(projection)
    if vector.shape != physical_projection.shape:
        raise ValueError("projection and direction must have matching shapes")
    q_derivative = full_diffusion_noise_directional_frechet_derivative(
        modes, vector
    )["noise_covariance_directional_derivative"]
    applied = apply_symmetric_noise_root_frechet(root_setup, q_derivative)
    root_derivative = np.asarray(
        applied["noise_root_directional_derivative"]
    )
    return {
        "projected_noise_root_vertex_action": root_derivative.T
        @ physical_projection,
        "relative_nullspace_residual": float(
            applied["relative_nullspace_residual"]
        ),
    }


def symmetric_noise_root_second_diagonal_frechet_derivatives(
    noise_covariance: np.ndarray,
    noise_covariance_derivative: np.ndarray,
    noise_covariance_second_diagonal_derivative: np.ndarray,
    *,
    relative_eigenvalue_floor: float = 1.0e-12,
) -> dict[str, np.ndarray | float]:
    r"""Differentiate ``Q=B^2`` twice along each occupation node.

    The first root derivative obeys ``B dB+dB B=dQ``.  Along the same nodal
    direction the second derivative is the Sylvester equation

    ``B d2B+d2B B=d2Q-2 dB dB``.

    The same declared null-space projection as in the first-derivative root is
    used, and both first- and second-order reconstruction residuals are
    reported.
    """

    first = symmetric_noise_root_frechet_derivatives(
        noise_covariance,
        noise_covariance_derivative,
        relative_eigenvalue_floor=relative_eigenvalue_floor,
    )
    noise = 0.5 * (
        np.asarray(noise_covariance) + np.asarray(noise_covariance).T
    )
    first_q = np.asarray(noise_covariance_derivative)
    second_q = np.asarray(noise_covariance_second_diagonal_derivative)
    first_root = np.asarray(first["noise_root_derivative"])
    if second_q.shape != first_q.shape or first_root.shape != first_q.shape:
        raise ValueError("first/second noise derivatives have incompatible shapes")
    eigenvalues, eigenvectors = np.linalg.eigh(noise)
    scale = max(float(np.max(np.abs(eigenvalues))), np.finfo(float).tiny)
    floor = relative_eigenvalue_floor * scale
    roots = np.sqrt(np.maximum(eigenvalues, 0.0))
    denominators = roots[:, None] + roots[None, :]
    supported = denominators > np.sqrt(floor)
    root = np.asarray(first["noise_root"])
    second_root = []
    residuals = []
    for d_root, d2_noise in zip(first_root, second_q):
        source = d2_noise - 2.0 * d_root @ d_root
        transformed = eigenvectors.T @ source @ eigenvectors
        transformed_second = np.divide(
            transformed,
            denominators,
            out=np.zeros_like(transformed),
            where=supported,
        )
        d2_root = eigenvectors @ transformed_second @ eigenvectors.T
        reconstructed = root @ d2_root + d2_root @ root + 2.0 * d_root @ d_root
        residuals.append(
            np.linalg.norm(reconstructed - d2_noise)
            / max(np.linalg.norm(d2_noise), np.finfo(float).tiny)
        )
        second_root.append(d2_root)
    return {
        **first,
        "noise_root_second_diagonal_derivative": np.asarray(second_root),
        "second_order_relative_nullspace_residual": np.asarray(residuals),
        "second_derivative_method": "second_sylvester_equation",
    }


def evaluate(
    field: float,
    *,
    string_xi_cutoff: float,
    string_xi_buffer: float,
    rapidity_u_extent: float,
    rapidity_step: float,
    velocity_series_terms: int,
    velocity_group_ratio: float = 2.0,
    string_boundary: str = "zero",
    compute_cross_diagnostic: bool = True,
) -> dict[str, float | int | bool | str | None]:
    """Evaluate the diagonal and full finite-cutoff GHD contractions."""

    values = np.asarray(
        [
            field,
            string_xi_cutoff,
            string_xi_buffer,
            rapidity_u_extent,
            rapidity_step,
            velocity_group_ratio,
        ],
        dtype=float,
    )
    if np.any(~np.isfinite(values)) or np.any(values <= 0.0):
        raise ValueError("All continuum and cutoff parameters must be positive")
    if field > 0.35:
        raise ValueError("The small-field extraction requires h <= 0.35")
    if velocity_series_terms < 50:
        raise ValueError("Use at least 50 velocity Fourier modes")
    if velocity_group_ratio <= 1.0:
        raise ValueError("velocity_group_ratio must exceed one")
    if string_boundary not in {"zero", "robin"}:
        raise ValueError("string_boundary must be 'zero' or 'robin'")

    active_strings = int(ceil(string_xi_cutoff / field))
    solve_strings = max(
        active_strings + 2,
        int(ceil((string_xi_cutoff + string_xi_buffer) / field)),
    )
    theta_extent = rapidity_u_extent / field
    requested_points = int(ceil(2.0 * theta_extent / rapidity_step))
    points = int(next_fast_len(max(requested_points, 128)))
    if points % 2:
        points = int(next_fast_len(points + 1))
    actual_step = 2.0 * theta_extent / points
    rapidities = (np.arange(points) - points // 2) * actual_step
    momenta = 2.0 * np.pi * np.fft.fftfreq(points, d=actual_step)

    kernel_hat, physical_hat = _dressed_kernel_fourier(
        field,
        momenta,
        active_strings=active_strings,
        solve_strings=solve_strings,
        boundary=string_boundary,
    )
    physical_density_fft = fftshift(
        ifft(physical_hat, axis=0), axes=0
    ).real.T / actual_step
    dressed_kernel = fftshift(
        ifft(kernel_hat, axis=0), axes=0
    ).real / actual_step
    del kernel_hat, physical_hat

    fields = _thermodynamic_fields(field, active_strings, rapidities)
    filling = fields["filling"]
    holes = fields["holes"]
    rho_total = fields["rho_total"]
    velocity = fields["velocity"]
    magnetization = fields["dressed_magnetization"]

    # The thermodynamic identity is exact on the infinite rapidity line and
    # is a stringent normalization/sign check on the dressing recurrence.
    rho_error = np.linalg.norm(physical_density_fft - rho_total) / np.linalg.norm(
        rho_total
    )
    susceptibility_exact = 1.0 / (4.0 * np.cosh(field) ** 2)
    susceptibility_grid = float(
        np.sum(
            trapezoid(
                filling[:, None]
                * holes[:, None]
                * rho_total
                * magnetization[:, None] ** 2,
                rapidities,
                axis=1,
            )
        )
    )

    left_weight = (
        filling[:, None]
        * holes[:, None]
        * magnetization[:, None] ** 2
        / rho_total
    )
    right_weight = filling[:, None] * holes[:, None] * rho_total
    left_weight = np.nan_to_num(left_weight, copy=False)
    velocity = np.nan_to_num(velocity, copy=False)

    # On a sampled rapidity grid the cells with identical species and
    # rapidity have exactly ``v-v'=0``.  A truncated Fourier series for
    # ``|v-v'|`` is positive at the cusp, so leaving those nodes untouched
    # creates an artificial O(1/N_series) contribution that is absent in the
    # continuum integral.  Retain T^dr_{s,s}(0)^2 so that this nodal error can
    # be removed exactly below.
    zero_rapidity_index = points // 2
    self_kernel_squared = np.diag(
        dressed_kernel[zero_rapidity_index, :, :]
    ) ** 2
    kernel_squared_hat = fft(
        ifftshift(dressed_kernel**2, axes=0), axis=0
    )
    del dressed_kernel
    species_velocity_bound = np.max(np.abs(velocity), axis=1)
    velocity_bound = float(np.max(species_velocity_bound)) * (1.0 + 1.0e-12)
    positive_velocity = np.maximum(
        species_velocity_bound,
        velocity_bound * np.finfo(float).eps,
    )
    velocity_bin = np.floor(
        np.log(velocity_bound / positive_velocity)
        / np.log(float(velocity_group_ratio))
    ).astype(int)
    velocity_groups = [
        np.flatnonzero(velocity_bin == label)
        for label in np.unique(velocity_bin)
    ]

    def velocity_characteristic(
        momentum: float,
        left: np.ndarray,
        right: np.ndarray,
        left_indices: np.ndarray,
        right_indices: np.ndarray,
    ) -> float:
        left_block = left[left_indices]
        right_block = right[right_indices]
        right_hat = fft(
            ifftshift(
                right_block
                * np.exp(-1j * momentum * velocity[right_indices]),
                axes=1,
            ),
            axis=1,
        ).T
        convolution_hat = np.einsum(
            "kij,kj->ki",
            kernel_squared_hat[:, left_indices][:, :, right_indices],
            right_hat,
            optimize=True,
        )
        convolution = fftshift(
            ifft(convolution_hat, axis=0), axes=0
        ).T * actual_step
        return float(
            actual_step
            * np.sum(
                left_block
                * np.exp(1j * momentum * velocity[left_indices])
                * convolution
            ).real
        )

    def absolute_velocity_contraction(
        left: np.ndarray,
        right: np.ndarray,
    ) -> tuple[float, float]:
        raw = 0.0
        inverse_odd_square_sum = sum(
            1.0 / (2 * mode + 1) ** 2
            for mode in range(velocity_series_terms)
        )
        for left_indices in velocity_groups:
            left_max = float(np.max(species_velocity_bound[left_indices]))
            for right_indices in velocity_groups:
                right_max = float(
                    np.max(species_velocity_bound[right_indices])
                )
                # The velocity difference for this Cartesian string block is
                # in [-L,L].  The Fourier series of |x| on that interval is
                # L/2 - 4L/pi^2 sum cos((2n+1)pi*x/L)/(2n+1)^2.
                interval = (left_max + right_max) * (1.0 + 1.0e-12)
                block_zero = velocity_characteristic(
                    0.0, left, right, left_indices, right_indices
                )
                block_odd_sum = 0.0
                for mode in range(velocity_series_terms):
                    odd = 2 * mode + 1
                    momentum = odd * np.pi / interval
                    block_odd_sum += velocity_characteristic(
                        momentum,
                        left,
                        right,
                        left_indices,
                        right_indices,
                    ) / odd**2
                raw += interval * (
                    0.5 * block_zero
                    - 4.0 / np.pi**2 * block_odd_sum
                )

        # All exact self nodes fall into equal group pairs.  Their truncated
        # Fourier value depends on each species' group interval, so compute
        # the correction species by species.
        species_interval = np.empty(active_strings, dtype=float)
        for indices in velocity_groups:
            group_max = float(np.max(species_velocity_bound[indices]))
            species_interval[indices] = 2.0 * group_max * (1.0 + 1.0e-12)
        approximate_abs_at_zero = 0.5 * species_interval * (
            1.0 - 8.0 / np.pi**2 * inverse_odd_square_sum
        )
        correction = actual_step**2 * float(
            np.sum(
                left
                * right
                * self_kernel_squared[:, None]
                * approximate_abs_at_zero[:, None]
            )
        )
        return raw - correction, correction

    # Eq. (13) of arXiv:2003.13708 (supplement): the diagonal part of
    # (mathfrak D C)_mm.  Expanding the exact symmetric charge-difference
    # square in Eq. (DCgeneralmainsym) of arXiv:1812.00767 gives
    #
    #   1/2 * W_a W_b T_ab^2 * (m_b/rho_b-m_a/rho_a)^2
    #       = diagonal - cross.
    #
    # The two equal square terms combine into ``diagonal`` below and the
    # factor two multiplying the mixed term cancels the prefactor 1/2.  Thus
    # ``cross`` is the physical off-diagonal DC contraction.  Whether a
    # finite-cutoff number approximates its infinite-string limit remains a
    # separate convergence question.
    dc_spin_diagonal, diagonal_zero_node_correction = absolute_velocity_contraction(
        left_weight,
        right_weight,
    )
    cross_weight = filling[:, None] * holes[:, None] * magnetization[:, None]
    if compute_cross_diagnostic:
        dc_spin_cross, cross_zero_node_correction = absolute_velocity_contraction(
            cross_weight,
            cross_weight,
        )
        dc_spin_full = dc_spin_diagonal - dc_spin_cross
        full_diffusion = dc_spin_full / susceptibility_exact
    else:
        dc_spin_cross = None
        cross_zero_node_correction = None
        dc_spin_full = None
        full_diffusion = None
    diagonal_diffusion = dc_spin_diagonal / susceptibility_exact
    # A published finite-s_max curve truncates both Eq. (16) and the
    # susceptibility sum in Eq. (17).  This normalization is useful only for
    # reproducing that cutoff sequence; the physical finite-field diffusion
    # uses the exact susceptibility above.
    diagonal_diffusion_truncated_chi = dc_spin_diagonal / susceptibility_grid
    spectral = finite_field_spectral_regulator_diffusion(field)

    return {
        "field": float(field),
        "active_strings": active_strings,
        "solve_strings": solve_strings,
        "string_boundary": string_boundary,
        "rapidity_points": points,
        "rapidity_step": actual_step,
        "rapidity_u_extent": float(rapidity_u_extent),
        "velocity_series_terms": int(velocity_series_terms),
        "rho_total_relative_l2_error": float(rho_error),
        "susceptibility_exact": float(susceptibility_exact),
        "susceptibility_grid": susceptibility_grid,
        "susceptibility_relative_truncation": float(
            susceptibility_grid / susceptibility_exact - 1.0
        ),
        "velocity_bound": velocity_bound,
        "velocity_group_ratio": float(velocity_group_ratio),
        "velocity_group_count": len(velocity_groups),
        "diagonal_zero_velocity_node_correction": float(
            diagonal_zero_node_correction
        ),
        "cross_zero_velocity_node_correction": (
            None
            if cross_zero_node_correction is None
            else float(cross_zero_node_correction)
        ),
        "diagonal_dc": float(dc_spin_diagonal),
        "off_diagonal_cross_contraction_dc": (
            None if dc_spin_cross is None else float(dc_spin_cross)
        ),
        "full_dc_finite_cutoff": (
            None if dc_spin_full is None else float(dc_spin_full)
        ),
        "diagonal_diffusion": float(diagonal_diffusion),
        "h_times_diagonal_diffusion": float(field * diagonal_diffusion),
        "diagonal_diffusion_truncated_chi": float(
            diagonal_diffusion_truncated_chi
        ),
        "h_times_diagonal_diffusion_truncated_chi": float(
            field * diagonal_diffusion_truncated_chi
        ),
        "truncated_chi_is_physical_finite_field_normalization": False,
        "diagonal_leading_subtracted": float(
            diagonal_diffusion - EXACT_D0_INFINITY_T / field
        ),
        "full_diffusion_finite_cutoff": (
            None if full_diffusion is None else float(full_diffusion)
        ),
        "h_times_full_diffusion_finite_cutoff": (
            None if full_diffusion is None else float(field * full_diffusion)
        ),
        "full_diffusion_finite_cutoff_leading_subtracted": (
            None
            if full_diffusion is None
            else float(full_diffusion - EXACT_D0_INFINITY_T / field)
        ),
        "cross_is_exact_physical_off_diagonal_dc_term": True,
        "full_finite_cutoff_is_converged_physical_diffusion": False,
        "cross_computed": bool(compute_cross_diagnostic),
        "spectral_regulator_diffusion": float(spectral),
        "spectral_leading_subtracted": float(
            spectral - EXACT_D0_INFINITY_T / field
        ),
        "uses_heisenberg_trajectory": False,
    }


def main() -> int:
    args = _arguments()
    result = evaluate(
        args.field,
        string_xi_cutoff=args.string_xi_cutoff,
        string_xi_buffer=args.string_xi_buffer,
        rapidity_u_extent=args.rapidity_u_extent,
        rapidity_step=args.rapidity_step,
        velocity_series_terms=args.velocity_series_terms,
        velocity_group_ratio=args.velocity_group_ratio,
        string_boundary=args.string_boundary,
        compute_cross_diagnostic=not args.skip_cross_diagnostic,
    )
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(payload, end="")
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
