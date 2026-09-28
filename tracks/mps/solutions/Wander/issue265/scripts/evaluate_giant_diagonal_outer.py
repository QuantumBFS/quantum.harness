#!/usr/bin/env python3
"""Evaluate the leading and first outer giant-string diagonal diffusion."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.heisenberg_burgers_bridge import (  # noqa: E402
    EXACT_D0_INFINITY_T,
    giant_bare_scattering_fourier_kernel,
    giant_diagonal_diffusion_outer_factors,
    giant_dressed_scattering_common_shift_derivative_fourier_kernel,
)


def _legendre_interval(left: float, right: float, order: int):
    nodes, weights = np.polynomial.legendre.leggauss(order)
    return (
        0.5 * (right - left) * (nodes + 1.0) + left,
        0.5 * (right - left) * weights,
    )


def _geometric_legendre_interval(
    left: float,
    right: float,
    order_per_panel: int,
    *,
    ratio: float = 2.0,
) -> tuple[np.ndarray, np.ndarray, int]:
    """Composite Gauss rule with geometric panels near a small lower edge."""

    if not 0.0 < left < right or order_per_panel < 2 or ratio <= 1.0:
        raise ValueError("invalid geometric interval")
    edges = [float(left)]
    while edges[-1] * ratio < right:
        edges.append(edges[-1] * ratio)
    if edges[-1] < right:
        edges.append(float(right))
    nodes = []
    weights = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        panel_nodes, panel_weights = _legendre_interval(lo, hi, order_per_panel)
        nodes.append(panel_nodes)
        weights.append(panel_weights)
    return np.concatenate(nodes), np.concatenate(weights), len(edges) - 1


def _outer_dressed_fourier(
    outer_xi: np.ndarray,
    dress_xi: np.ndarray,
    dress_weight: np.ndarray,
    wave_numbers: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, float]:
    """Solve the leading and first dressed kernels on a common k grid."""

    xi_points = int(outer_xi.size)
    dressing_xi_points = int(dress_xi.size)
    n0 = 1.0 / np.sinh(dress_xi) ** 2
    weighted_n0 = dress_weight * n0
    x0_hat = np.empty((wave_numbers.size, xi_points, xi_points), dtype=float)
    x1_hat = np.empty_like(x0_hat)
    leading_resolvent_errors = []

    check_indices = {0, wave_numbers.size // 4, wave_numbers.size // 2}
    for wave_index, wave_number in enumerate(wave_numbers):
        t0_nn = giant_bare_scattering_fourier_kernel(
            dress_xi[:, None], dress_xi[None, :], wave_number
        )
        t0_ny = giant_bare_scattering_fourier_kernel(
            dress_xi[:, None], outer_xi[None, :], wave_number
        )
        t0_xn = giant_bare_scattering_fourier_kernel(
            outer_xi[:, None], dress_xi[None, :], wave_number
        )
        t0_xy = giant_bare_scattering_fourier_kernel(
            outer_xi[:, None], outer_xi[None, :], wave_number
        )
        operator = np.eye(dressing_xi_points) + t0_nn * weighted_n0[None, :]
        x0_ny = np.linalg.solve(operator, t0_ny)
        x0_hat[wave_index] = t0_xy - t0_xn @ (weighted_n0[:, None] * x0_ny)
        if wave_index in check_indices:
            residual = operator @ x0_ny - t0_ny
            leading_resolvent_errors.append(float(np.max(np.abs(residual))))

        x1_hat[wave_index] = (
            giant_dressed_scattering_common_shift_derivative_fourier_kernel(
                outer_xi[:, None], outer_xi[None, :], wave_number
            )
        )
    return x0_hat, x1_hat, max(leading_resolvent_errors)


def evaluate(
    *,
    matching_scale: float,
    xi_extent: float,
    xi_points: int,
    dressing_xi_extent: float,
    dressing_xi_points: int,
    rapidity_extent: float,
    rapidity_points: int,
) -> dict[str, object]:
    """Return outer ``D0(eta)`` and ``D1_outer(eta)`` on shared FFT grids."""

    eta = float(matching_scale)
    if not 0.0 < eta < xi_extent < dressing_xi_extent:
        raise ValueError("require 0 < matching_scale < xi_extent < dressing extent")
    if xi_points < 8 or dressing_xi_points < 24:
        raise ValueError("too few xi points")
    if rapidity_points < 32 or rapidity_points % 2:
        raise ValueError("rapidity_points must be even and at least 32")

    outer_xi, outer_weight = _legendre_interval(eta, xi_extent, xi_points)
    dress_xi, dress_weight = _legendre_interval(
        0.0, dressing_xi_extent, dressing_xi_points
    )
    rapidity_step = 2.0 * rapidity_extent / rapidity_points
    rapidities = (
        np.arange(rapidity_points, dtype=float) - rapidity_points // 2
    ) * rapidity_step
    kernel_points = 2 * rapidity_points
    wave_numbers = 2.0 * np.pi * np.fft.fftfreq(
        kernel_points, d=rapidity_step
    )

    n0 = 1.0 / np.sinh(dress_xi) ** 2
    weighted_n0 = dress_weight * n0
    x0_hat = np.empty((kernel_points, xi_points, xi_points), dtype=float)
    x1_hat = np.empty_like(x0_hat)
    leading_resolvent_errors = []

    for wave_index, wave_number in enumerate(wave_numbers):
        t0_nn = giant_bare_scattering_fourier_kernel(
            dress_xi[:, None], dress_xi[None, :], wave_number
        )
        t0_ny = giant_bare_scattering_fourier_kernel(
            dress_xi[:, None], outer_xi[None, :], wave_number
        )
        t0_xn = giant_bare_scattering_fourier_kernel(
            outer_xi[:, None], dress_xi[None, :], wave_number
        )
        t0_xy = giant_bare_scattering_fourier_kernel(
            outer_xi[:, None], outer_xi[None, :], wave_number
        )
        operator = np.eye(dressing_xi_points) + t0_nn * weighted_n0[None, :]
        x0_ny = np.linalg.solve(operator, t0_ny)
        x0_xy = t0_xy - t0_xn @ (weighted_n0[:, None] * x0_ny)
        x0_hat[wave_index] = x0_xy
        if wave_index in (0, kernel_points // 8, kernel_points // 4):
            residual = operator @ x0_ny - t0_ny
            leading_resolvent_errors.append(float(np.max(np.abs(residual))))

        x1_hat[wave_index] = (
            giant_dressed_scattering_common_shift_derivative_fourier_kernel(
                outer_xi[:, None], outer_xi[None, :], wave_number
            )
        )

    x0_grid = (
        np.fft.fftshift(np.fft.ifft(x0_hat, axis=0), axes=0).real
        / rapidity_step
    )
    x1_grid = (
        np.fft.fftshift(np.fft.ifft(x1_hat, axis=0), axes=0).real
        / rapidity_step
    )
    fields = giant_diagonal_diffusion_outer_factors(
        outer_xi[:, None], rapidities[None, :]
    )
    difference_index = (
        np.arange(rapidity_points)[:, None]
        - np.arange(rapidity_points)[None, :]
        + kernel_points // 2
    )

    leading_integral = 0.0
    first_integral = 0.0
    cross_leading_integral = 0.0
    cross_first_integral = 0.0
    for left in range(xi_points):
        for right in range(xi_points):
            kernel0 = x0_grid[difference_index, left, right]
            kernel1 = x1_grid[difference_index, left, right]
            velocity0 = (
                fields["velocity_leading"][left, :, None]
                - fields["velocity_leading"][right, None, :]
            )
            velocity1 = (
                fields["velocity_first"][left, :, None]
                - fields["velocity_first"][right, None, :]
            )
            absolute0 = np.abs(velocity0)
            absolute1 = np.where(
                absolute0 > 1.0e-14,
                np.sign(velocity0) * velocity1,
                np.abs(velocity1),
            )
            a0 = fields["left_weight_leading"][left, :, None]
            a1 = fields["left_weight_first"][left, :, None]
            b0 = fields["partner_weight_leading"][right, None, :]
            b1 = fields["partner_weight_first"][right, None, :]
            c0_left = fields["cross_weight_leading"][left, :, None]
            c1_left = fields["cross_weight_first"][left, :, None]
            c0_right = fields["cross_weight_leading"][right, None, :]
            c1_right = fields["cross_weight_first"][right, None, :]
            measure = (
                outer_weight[left]
                * outer_weight[right]
                * rapidity_step**2
                / 0.25
            )
            leading_integral += measure * np.sum(
                a0 * b0 * absolute0 * kernel0**2
            )
            first_integral += measure * np.sum(
                (a1 * b0 + a0 * b1) * absolute0 * kernel0**2
                + a0 * b0 * absolute1 * kernel0**2
                + 2.0 * a0 * b0 * absolute0 * kernel0 * kernel1
            )
            cross_leading_integral += measure * np.sum(
                c0_left * c0_right * absolute0 * kernel0**2
            )
            cross_first_integral += measure * np.sum(
                (c1_left * c0_right + c0_left * c1_right)
                * absolute0
                * kernel0**2
                + c0_left * c0_right * absolute1 * kernel0**2
                + 2.0
                * c0_left
                * c0_right
                * absolute0
                * kernel0
                * kernel1
            )

    return {
        "schema": 1,
        "method": "outer_giant_diagonal_shared_fft_nystrom",
        "inputs": {
            "matching_scale": eta,
            "xi_extent": float(xi_extent),
            "xi_points": int(xi_points),
            "dressing_xi_extent": float(dressing_xi_extent),
            "dressing_xi_points": int(dressing_xi_points),
            "rapidity_extent": float(rapidity_extent),
            "rapidity_points": int(rapidity_points),
            "rapidity_step": float(rapidity_step),
            "kernel_points": int(kernel_points),
        },
        "outer_leading_integral": float(leading_integral),
        "outer_first_integral": float(first_integral),
        "outer_cross_leading_integral": float(cross_leading_integral),
        "outer_cross_first_integral": float(cross_first_integral),
        "outer_full_leading_integral": float(
            leading_integral - cross_leading_integral
        ),
        "outer_full_first_integral": float(
            first_integral - cross_first_integral
        ),
        "exact_full_leading_D0": float(EXACT_D0_INFINITY_T),
        "leading_difference_from_exact_full_D0": float(
            EXACT_D0_INFINITY_T - leading_integral
        ),
        "diagnostics": {
            "leading_resolvent_max_abs_error": max(leading_resolvent_errors),
            "physical_D1_certified": False,
            "reason": (
                "both leading and first outer integrals require eta->0 "
                "cancellation against the fixed-string inner/overlap finite part"
            ),
        },
    }


def evaluate_adaptive_rapidity(
    *,
    matching_scale: float,
    xi_extent: float,
    xi_points: int,
    dressing_xi_extent: float,
    dressing_xi_points: int,
    scaled_rapidity_ratio_extent: float,
    scaled_rapidity_ratio_points: int,
    wave_number_cutoff: float,
    wave_number_points: int,
) -> dict[str, object]:
    r"""Integrate the outer problem in the natural coordinate ``r=u/xi``.

    A fixed uniform ``u`` grid is non-uniform as ``xi -> 0`` because the
    thermodynamic rapidity profiles have width ``u=O(xi)``.  Here each string
    instead uses ``u=xi*r`` and ``du=xi*dr``.  The dressed kernels are inverse
    Fourier transformed directly at the resulting non-uniform differences;
    no interpolation on a fixed-u mesh is involved.
    """

    eta = float(matching_scale)
    ratio_extent = float(scaled_rapidity_ratio_extent)
    k_cutoff = float(wave_number_cutoff)
    if not 0.0 < eta < xi_extent < dressing_xi_extent:
        raise ValueError("require 0 < matching_scale < xi_extent < dressing extent")
    if xi_points < 8 or dressing_xi_points < 24:
        raise ValueError("too few xi points")
    if ratio_extent <= 0.0 or scaled_rapidity_ratio_points < 8:
        raise ValueError("rapidity-ratio quadrature is too small")
    if k_cutoff <= 0.0 or wave_number_points < 32:
        raise ValueError("wave-number quadrature is too small")

    outer_xi, outer_weight = _legendre_interval(eta, xi_extent, xi_points)
    dress_xi, dress_weight = _legendre_interval(
        0.0, dressing_xi_extent, dressing_xi_points
    )
    left_ratio, left_ratio_weight = _legendre_interval(
        -ratio_extent, ratio_extent, scaled_rapidity_ratio_points
    )
    # Use the adjacent Gauss rule on the partner leg.  A tensor product of
    # identical nodes samples the logarithmic kernel singularity on a finite-
    # weight diagonal, which is a quadrature artefact.  Adjacent rules never
    # share a node and converge to the same continuum integral.
    right_ratio, right_ratio_weight = _legendre_interval(
        -ratio_extent, ratio_extent, scaled_rapidity_ratio_points + 1
    )
    wave_numbers, wave_weights = _legendre_interval(
        0.0, k_cutoff, wave_number_points
    )
    x0_hat, x1_hat, resolvent_error = _outer_dressed_fourier(
        outer_xi, dress_xi, dress_weight, wave_numbers
    )

    left_scaled_rapidities = outer_xi[:, None] * left_ratio[None, :]
    right_scaled_rapidities = outer_xi[:, None] * right_ratio[None, :]
    left_fields = giant_diagonal_diffusion_outer_factors(
        outer_xi[:, None], left_scaled_rapidities
    )
    right_fields = giant_diagonal_diffusion_outer_factors(
        outer_xi[:, None], right_scaled_rapidities
    )
    # X(u-v)=pi^-1 int_0^K dk cos(k(u-v)) Xhat(k).  Splitting the
    # difference cosine permits a pair of BLAS products for each xi block.
    left_cosine = np.cos(
        outer_xi[:, None, None] * left_ratio[None, :, None]
        * wave_numbers[None, None, :]
    )
    left_sine = np.sin(
        outer_xi[:, None, None] * left_ratio[None, :, None]
        * wave_numbers[None, None, :]
    )
    right_cosine = np.cos(
        outer_xi[:, None, None] * right_ratio[None, :, None]
        * wave_numbers[None, None, :]
    )
    right_sine = np.sin(
        outer_xi[:, None, None] * right_ratio[None, :, None]
        * wave_numbers[None, None, :]
    )
    spectral_weight = wave_weights / np.pi

    leading_integral = 0.0
    first_integral = 0.0
    cross_leading_integral = 0.0
    cross_first_integral = 0.0
    for left in range(xi_points):
        cosine_l = left_cosine[left]
        sine_l = left_sine[left]
        for right in range(xi_points):
            weighted0 = spectral_weight * x0_hat[:, left, right]
            weighted1 = spectral_weight * x1_hat[:, left, right]
            kernel0 = (cosine_l * weighted0) @ right_cosine[right].T
            kernel0 += (sine_l * weighted0) @ right_sine[right].T
            kernel1 = (cosine_l * weighted1) @ right_cosine[right].T
            kernel1 += (sine_l * weighted1) @ right_sine[right].T

            velocity0 = (
                left_fields["velocity_leading"][left, :, None]
                - right_fields["velocity_leading"][right, None, :]
            )
            velocity1 = (
                left_fields["velocity_first"][left, :, None]
                - right_fields["velocity_first"][right, None, :]
            )
            absolute0 = np.abs(velocity0)
            absolute1 = np.where(
                absolute0 > 1.0e-14,
                np.sign(velocity0) * velocity1,
                np.abs(velocity1),
            )
            a0 = left_fields["left_weight_leading"][left, :, None]
            a1 = left_fields["left_weight_first"][left, :, None]
            b0 = right_fields["partner_weight_leading"][right, None, :]
            b1 = right_fields["partner_weight_first"][right, None, :]
            c0_left = left_fields["cross_weight_leading"][left, :, None]
            c1_left = left_fields["cross_weight_first"][left, :, None]
            c0_right = right_fields["cross_weight_leading"][right, None, :]
            c1_right = right_fields["cross_weight_first"][right, None, :]
            measure = (
                outer_weight[left]
                * outer_weight[right]
                * outer_xi[left]
                * outer_xi[right]
                * left_ratio_weight[:, None]
                * right_ratio_weight[None, :]
                / 0.25
            )
            leading_term = np.sum(
                measure * a0 * b0 * absolute0 * kernel0**2
            )
            first_term = np.sum(
                measure
                * (
                    (a1 * b0 + a0 * b1) * absolute0 * kernel0**2
                    + a0 * b0 * absolute1 * kernel0**2
                    + 2.0 * a0 * b0 * absolute0 * kernel0 * kernel1
                )
            )
            cross_leading_term = np.sum(
                measure * c0_left * c0_right * absolute0 * kernel0**2
            )
            cross_first_term = np.sum(
                measure
                * (
                    (c1_left * c0_right + c0_left * c1_right)
                    * absolute0
                    * kernel0**2
                    + c0_left * c0_right * absolute1 * kernel0**2
                    + 2.0
                    * c0_left
                    * c0_right
                    * absolute0
                    * kernel0
                    * kernel1
                )
            )
            leading_integral += leading_term
            first_integral += first_term
            cross_leading_integral += cross_leading_term
            cross_first_integral += cross_first_term
            leading_by_left[left] += leading_term
            first_by_left[left] += first_term
            cross_leading_by_left[left] += cross_leading_term
            cross_first_by_left[left] += cross_first_term

    return {
        "schema": 1,
        "method": "outer_giant_diagonal_adaptive_u_over_xi",
        "inputs": {
            "matching_scale": eta,
            "xi_extent": float(xi_extent),
            "xi_points": int(xi_points),
            "dressing_xi_extent": float(dressing_xi_extent),
            "dressing_xi_points": int(dressing_xi_points),
            "scaled_rapidity_ratio_extent": ratio_extent,
            "scaled_rapidity_ratio_points": int(scaled_rapidity_ratio_points),
            "wave_number_cutoff": k_cutoff,
            "wave_number_points": int(wave_number_points),
        },
        "outer_leading_integral": float(leading_integral),
        "outer_first_integral": float(first_integral),
        "outer_cross_leading_integral": float(cross_leading_integral),
        "outer_cross_first_integral": float(cross_first_integral),
        "outer_full_leading_integral": float(
            leading_integral - cross_leading_integral
        ),
        "outer_full_first_integral": float(
            first_integral - cross_first_integral
        ),
        "left_xi_density": {
            "xi": outer_xi.tolist(),
            "leading_diagonal": np.divide(
                leading_by_left, outer_weight
            ).tolist(),
            "first_diagonal": np.divide(first_by_left, outer_weight).tolist(),
            "leading_cross": np.divide(
                cross_leading_by_left, outer_weight
            ).tolist(),
            "first_cross": np.divide(
                cross_first_by_left, outer_weight
            ).tolist(),
            "leading_full": np.divide(
                leading_by_left - cross_leading_by_left, outer_weight
            ).tolist(),
            "first_full": np.divide(
                first_by_left - cross_first_by_left, outer_weight
            ).tolist(),
        },
        "exact_full_leading_D0": float(EXACT_D0_INFINITY_T),
        "leading_difference_from_exact_full_D0": float(
            EXACT_D0_INFINITY_T - leading_integral
        ),
        "diagnostics": {
            "leading_resolvent_max_abs_error": float(resolvent_error),
            "physical_D1_certified": False,
            "reason": (
                "adaptive rapidity closes the u=O(xi) layer, but the "
                "eta limit and fixed-string overlap remain to be certified"
            ),
        },
    }


def _sinh_nodes_with_central_scale(
    extent: float,
    central_scale: float,
    order: int,
) -> tuple[np.ndarray, np.ndarray, float]:
    """Gauss nodes on ``[-extent,extent]`` resolving ``central_scale``."""

    base, base_weight = np.polynomial.legendre.leggauss(order)
    ratio = min(max(float(central_scale) / float(extent), 1.0e-12), 1.0)
    if ratio > 1.0 - 1.0e-10:
        alpha = 0.0
        return extent * base, extent * base_weight, alpha
    low, high = 0.0, 50.0
    for _ in range(80):
        mid = 0.5 * (low + high)
        value = mid / np.sinh(mid) if mid else 1.0
        if value > ratio:
            low = mid
        else:
            high = mid
    alpha = 0.5 * (low + high)
    denominator = np.sinh(alpha)
    nodes = extent * np.sinh(alpha * base) / denominator
    weights = (
        extent
        * alpha
        * np.cosh(alpha * base)
        / denominator
        * base_weight
    )
    return nodes, weights, alpha


def evaluate_adaptive_rapidity_fft(
    *,
    matching_scale: float,
    xi_extent: float,
    xi_points: int,
    dressing_xi_extent: float,
    dressing_xi_points: int,
    rapidity_extent: float,
    rapidity_step: float,
    rapidity_nodes_per_string: int,
    xi_geometric_panels: bool = False,
) -> dict[str, object]:
    r"""Outer integral with a fixed-domain, string-adaptive rapidity rule.

    The inverse Fourier transform is evaluated once on a uniform auxiliary
    mesh.  Thermodynamic integration uses non-uniform nodes whose central
    Jacobian is ``O(xi)`` and whose endpoints remain at ``+/-U``.  This
    resolves both the ``u=O(xi)`` boundary layer and the algebraic rapidity
    tails without the hard-cutoff ringing of pointwise Fourier quadrature.
    """

    eta = float(matching_scale)
    if not 0.0 < eta < xi_extent < dressing_xi_extent:
        raise ValueError("require 0 < matching_scale < xi_extent < dressing extent")
    if rapidity_extent <= 0.0 or rapidity_step <= 0.0:
        raise ValueError("rapidity extent and step must be positive")
    if rapidity_nodes_per_string < 8:
        raise ValueError("need at least eight rapidity nodes per string")
    if xi_geometric_panels:
        outer_xi, outer_weight, xi_panel_count = _geometric_legendre_interval(
            eta, xi_extent, xi_points
        )
        actual_xi_points = int(outer_xi.size)
    else:
        outer_xi, outer_weight = _legendre_interval(eta, xi_extent, xi_points)
        xi_panel_count = 1
        actual_xi_points = int(xi_points)
    dress_xi, dress_weight = _legendre_interval(
        0.0, dressing_xi_extent, dressing_xi_points
    )
    rapidity_points = int(np.ceil(2.0 * rapidity_extent / rapidity_step))
    if rapidity_points % 2:
        rapidity_points += 1
    actual_step = 2.0 * rapidity_extent / rapidity_points
    kernel_points = 2 * rapidity_points
    wave_numbers = 2.0 * np.pi * np.fft.fftfreq(
        kernel_points, d=actual_step
    )
    x0_hat, x1_hat, resolvent_error = _outer_dressed_fourier(
        outer_xi, dress_xi, dress_weight, wave_numbers
    )
    x0_grid = (
        np.fft.fftshift(np.fft.ifft(x0_hat, axis=0), axes=0).real
        / actual_step
    )
    x1_grid = (
        np.fft.fftshift(np.fft.ifft(x1_hat, axis=0), axes=0).real
        / actual_step
    )
    del x0_hat, x1_hat

    left_nodes = []
    left_weights = []
    right_nodes = []
    right_weights = []
    alphas = []
    for xi in outer_xi:
        nodes, weights, alpha = _sinh_nodes_with_central_scale(
            rapidity_extent, xi, rapidity_nodes_per_string
        )
        partner_nodes, partner_weights, _ = _sinh_nodes_with_central_scale(
            rapidity_extent, xi, rapidity_nodes_per_string + 1
        )
        left_nodes.append(nodes)
        left_weights.append(weights)
        right_nodes.append(partner_nodes)
        right_weights.append(partner_weights)
        alphas.append(alpha)
    left_nodes = np.asarray(left_nodes)
    left_weights = np.asarray(left_weights)
    right_nodes = np.asarray(right_nodes)
    right_weights = np.asarray(right_weights)
    left_fields = giant_diagonal_diffusion_outer_factors(
        outer_xi[:, None], left_nodes
    )
    right_fields = giant_diagonal_diffusion_outer_factors(
        outer_xi[:, None], right_nodes
    )

    leading_integral = 0.0
    first_integral = 0.0
    cross_leading_integral = 0.0
    cross_first_integral = 0.0
    leading_by_left = np.zeros(actual_xi_points, dtype=float)
    first_by_left = np.zeros(actual_xi_points, dtype=float)
    cross_leading_by_left = np.zeros(actual_xi_points, dtype=float)
    cross_first_by_left = np.zeros(actual_xi_points, dtype=float)
    for left in range(actual_xi_points):
        for right in range(actual_xi_points):
            differences = left_nodes[left, :, None] - right_nodes[right, None, :]
            fractional = differences / actual_step + kernel_points // 2
            lower = np.floor(fractional).astype(int)
            interpolation = fractional - lower
            lower %= kernel_points
            upper = (lower + 1) % kernel_points
            kernel0 = (
                (1.0 - interpolation) * x0_grid[lower, left, right]
                + interpolation * x0_grid[upper, left, right]
            )
            kernel1 = (
                (1.0 - interpolation) * x1_grid[lower, left, right]
                + interpolation * x1_grid[upper, left, right]
            )
            velocity0 = (
                left_fields["velocity_leading"][left, :, None]
                - right_fields["velocity_leading"][right, None, :]
            )
            velocity1 = (
                left_fields["velocity_first"][left, :, None]
                - right_fields["velocity_first"][right, None, :]
            )
            absolute0 = np.abs(velocity0)
            absolute1 = np.where(
                absolute0 > 1.0e-14,
                np.sign(velocity0) * velocity1,
                np.abs(velocity1),
            )
            a0 = left_fields["left_weight_leading"][left, :, None]
            a1 = left_fields["left_weight_first"][left, :, None]
            b0 = right_fields["partner_weight_leading"][right, None, :]
            b1 = right_fields["partner_weight_first"][right, None, :]
            c0_left = left_fields["cross_weight_leading"][left, :, None]
            c1_left = left_fields["cross_weight_first"][left, :, None]
            c0_right = right_fields["cross_weight_leading"][right, None, :]
            c1_right = right_fields["cross_weight_first"][right, None, :]
            measure = (
                outer_weight[left]
                * outer_weight[right]
                * left_weights[left, :, None]
                * right_weights[right, None, :]
                / 0.25
            )
            leading_term = np.sum(
                measure * a0 * b0 * absolute0 * kernel0**2
            )
            first_term = np.sum(
                measure
                * (
                    (a1 * b0 + a0 * b1) * absolute0 * kernel0**2
                    + a0 * b0 * absolute1 * kernel0**2
                    + 2.0 * a0 * b0 * absolute0 * kernel0 * kernel1
                )
            )
            cross_leading_term = np.sum(
                measure * c0_left * c0_right * absolute0 * kernel0**2
            )
            cross_first_term = np.sum(
                measure
                * (
                    (c1_left * c0_right + c0_left * c1_right)
                    * absolute0
                    * kernel0**2
                    + c0_left * c0_right * absolute1 * kernel0**2
                    + 2.0
                    * c0_left
                    * c0_right
                    * absolute0
                    * kernel0
                    * kernel1
                )
            )
            leading_integral += leading_term
            first_integral += first_term
            cross_leading_integral += cross_leading_term
            cross_first_integral += cross_first_term
            leading_by_left[left] += leading_term
            first_by_left[left] += first_term
            cross_leading_by_left[left] += cross_leading_term
            cross_first_by_left[left] += cross_first_term
    return {
        "schema": 1,
        "method": "outer_giant_diagonal_adaptive_rapidity_fft",
        "inputs": {
            "matching_scale": eta,
            "xi_extent": float(xi_extent),
            "xi_points": actual_xi_points,
            "xi_order_per_panel": int(xi_points) if xi_geometric_panels else None,
            "xi_panel_count": int(xi_panel_count),
            "xi_geometric_panels": bool(xi_geometric_panels),
            "dressing_xi_extent": float(dressing_xi_extent),
            "dressing_xi_points": int(dressing_xi_points),
            "rapidity_extent": float(rapidity_extent),
            "rapidity_step": float(actual_step),
            "rapidity_nodes_per_string": int(rapidity_nodes_per_string),
            "kernel_points": int(kernel_points),
            "sinh_map_alpha_range": [float(min(alphas)), float(max(alphas))],
        },
        "outer_leading_integral": float(leading_integral),
        "outer_first_integral": float(first_integral),
        "outer_cross_leading_integral": float(cross_leading_integral),
        "outer_cross_first_integral": float(cross_first_integral),
        "outer_full_leading_integral": float(
            leading_integral - cross_leading_integral
        ),
        "outer_full_first_integral": float(
            first_integral - cross_first_integral
        ),
        "left_xi_density": {
            "xi": outer_xi.tolist(),
            "leading_diagonal": np.divide(
                leading_by_left, outer_weight
            ).tolist(),
            "first_diagonal": np.divide(first_by_left, outer_weight).tolist(),
            "leading_cross": np.divide(
                cross_leading_by_left, outer_weight
            ).tolist(),
            "first_cross": np.divide(
                cross_first_by_left, outer_weight
            ).tolist(),
            "leading_full": np.divide(
                leading_by_left - cross_leading_by_left, outer_weight
            ).tolist(),
            "first_full": np.divide(
                first_by_left - cross_first_by_left, outer_weight
            ).tolist(),
        },
        "exact_full_leading_D0": float(EXACT_D0_INFINITY_T),
        "leading_difference_from_exact_full_D0": float(
            EXACT_D0_INFINITY_T - leading_integral
        ),
        "diagnostics": {
            "leading_resolvent_max_abs_error": float(resolvent_error),
            "physical_D1_certified": False,
            "reason": (
                "the u=O(xi) rapidity layer is explicitly resolved; eta and "
                "fixed-string overlap convergence remain separate gates"
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matching-scale", type=float, required=True)
    parser.add_argument("--xi-extent", type=float, default=10.0)
    parser.add_argument("--xi-points", type=int, default=32)
    parser.add_argument("--dressing-xi-extent", type=float, default=14.0)
    parser.add_argument("--dressing-xi-points", type=int, default=120)
    parser.add_argument("--rapidity-extent", type=float, default=20.0)
    parser.add_argument("--rapidity-points", type=int, default=128)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate(
        matching_scale=args.matching_scale,
        xi_extent=args.xi_extent,
        xi_points=args.xi_points,
        dressing_xi_extent=args.dressing_xi_extent,
        dressing_xi_points=args.dressing_xi_points,
        rapidity_extent=args.rapidity_extent,
        rapidity_points=args.rapidity_points,
    )
    encoded = json.dumps(result, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    print(encoded, end="")


if __name__ == "__main__":
    main()
