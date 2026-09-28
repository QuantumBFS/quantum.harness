"""Positive-continuum matching of hydrodynamic Mori kernels to exact moments.

The microscopic XXX commutator algebra fixes a finite prefix of the symmetric
Mori continued fraction.  This module never closes the remaining fraction by
one or two poles.  Instead it peels the exact prefix from a candidate kernel,
tests whether the remainder is compatible with a positive symmetric spectral
measure, and represents that measure on a convergence-controlled quadrature.
Reinsertion through the exact prefix preserves all supplied recurrents
algebraically.
"""

from __future__ import annotations

import math
import numpy as np
from scipy.optimize import nnls

from src.heisenberg_burgers_bridge import (
    mori_kernel_from_lanczos_terminator,
    mori_lanczos_stieltjes_bounds,
    mori_lanczos_terminator_from_kernel,
    xxx_mori_even_moments,
    xxx_mori_lanczos_recurrents,
    xxx_mori_long_wave_lanczos,
)


Array = np.ndarray


def mori_hierarchy_kernel_from_terminator(
    times: Array,
    normalized_terminator: Array,
    *,
    mu0: float,
    squared_recurrents: Array,
) -> Array:
    r"""Propagate a normalized deep terminator through an exact Mori prefix.

    At each level ``g_n'=-b_{n+1}^2 (g_{n+1}*g_n)`` with ``g_n(0)=1``.
    The convolution is discretized by the implicit trapezoidal rule.  The
    returned physical kernel is ``mu0*g_0`` and therefore has the exact
    zero-time value regardless of the hydrodynamic terminator amplitude.
    """

    t = np.asarray(times, dtype=float)
    hierarchy = np.asarray(normalized_terminator, dtype=float)
    squared = np.asarray(squared_recurrents, dtype=float)
    if (
        t.ndim != 1
        or hierarchy.shape != t.shape
        or t.size < 3
        or not np.isclose(t[0], 0.0)
        or np.any(np.diff(t) <= 0.0)
        or not np.allclose(np.diff(t), np.diff(t)[0], rtol=1.0e-11, atol=1.0e-14)
    ):
        raise ValueError("Mori hierarchy needs a uniform time grid from zero")
    if (
        not np.isfinite(mu0)
        or mu0 <= 0.0
        or np.any(~np.isfinite(hierarchy))
        or hierarchy[0] <= 0.0
        or squared.ndim != 1
        or squared.size == 0
        or np.any(~np.isfinite(squared))
        or np.any(squared <= 0.0)
    ):
        raise ValueError("Mori hierarchy inputs must be finite and positive at zero")
    hierarchy = hierarchy / hierarchy[0]
    dt = float(t[1] - t[0])
    for coupling in squared[::-1]:
        next_level = hierarchy
        current_level = np.ones(t.size, dtype=float)
        previous_convolution = 0.0
        denominator = 1.0 + 0.25 * dt**2 * coupling * next_level[0]
        for index in range(1, t.size):
            interior = (
                0.0
                if index == 1
                else float(next_level[1:index][::-1] @ current_level[1:index])
            )
            known = dt * (
                interior + 0.5 * next_level[index] * current_level[0]
            )
            current_level[index] = (
                current_level[index - 1]
                - 0.5 * dt * coupling * (known + previous_convolution)
            ) / denominator
            previous_convolution = (
                known + 0.5 * dt * next_level[0] * current_level[index]
            )
        hierarchy = current_level
    return float(mu0) * hierarchy


def density_structure_from_mori_kernels(
    times: Array,
    wavenumbers: Array,
    kernels: Array,
    *,
    lattice: bool = True,
) -> Array:
    r"""Solve ``F'=-khat^2 K_k*F`` for one kernel per wave number."""

    t = np.asarray(times, dtype=float)
    waves = np.asarray(wavenumbers, dtype=float)
    memory = np.asarray(kernels, dtype=float)
    if (
        t.ndim != 1
        or waves.ndim != 1
        or t.size < 3
        or not np.isclose(t[0], 0.0)
        or np.any(np.diff(t) <= 0.0)
        or not np.allclose(np.diff(t), np.diff(t)[0], rtol=1.0e-11, atol=1.0e-14)
    ):
        raise ValueError("density Mori solver needs uniform times from zero")
    if memory.ndim == 1:
        memory = np.repeat(memory[:, None], waves.size, axis=1)
    if memory.shape != (t.size, waves.size) or np.any(~np.isfinite(memory)):
        raise ValueError("kernels must have shape (time,wavenumber)")
    khat = 2.0 * np.sin(0.5 * waves) if lattice else waves
    khat_squared = khat**2
    dt = float(t[1] - t[0])
    structure = np.ones((t.size, waves.size), dtype=float)
    previous_convolution = np.zeros(waves.size, dtype=float)
    denominator = 1.0 + 0.25 * dt**2 * khat_squared * memory[0]
    for index in range(1, t.size):
        interior = (
            np.zeros(waves.size, dtype=float)
            if index == 1
            else np.sum(
                memory[1:index][::-1] * structure[1:index], axis=0
            )
        )
        known = dt * (interior + 0.5 * memory[index] * structure[0])
        structure[index] = (
            structure[index - 1]
            - 0.5
            * dt
            * khat_squared
            * (known + previous_convolution)
        ) / denominator
        previous_convolution = known + 0.5 * dt * memory[0] * structure[index]
    return structure


def exponential_jet_counterterm(
    zero_time_derivatives: Array,
    *,
    matching_rate: float,
) -> dict[str, object]:
    r"""Construct ``P(t)e^{-Omega t}`` with a prescribed zero-time jet.

    ``P(t)=sum_m p_m t^m/m!``.  The triangular Leibniz relation

    ``d_n=sum_{m<=n} binom(n,m) p_m (-Omega)^(n-m)``

    fixes every ``p_m`` uniquely.  Subtracting this localized function from a
    colored hydrodynamic memory makes its first supplied derivatives vanish
    while leaving its long-time nonlocal tail unchanged exponentially.
    """

    derivatives = np.asarray(zero_time_derivatives, dtype=complex)
    if derivatives.ndim != 1 or derivatives.size == 0 or np.any(~np.isfinite(derivatives)):
        raise ValueError("zero-time derivatives must be a non-empty finite vector")
    if not np.isfinite(matching_rate) or matching_rate <= 0.0:
        raise ValueError("matching_rate must be positive and finite")
    coefficients = np.zeros_like(derivatives)
    for order in range(derivatives.size):
        lower = sum(
            math.comb(order, m)
            * coefficients[m]
            * (-matching_rate) ** (order - m)
            for m in range(order)
        )
        coefficients[order] = derivatives[order] - lower
    reconstructed = np.asarray(
        [
            sum(
                math.comb(order, m)
                * coefficients[m]
                * (-matching_rate) ** (order - m)
                for m in range(order + 1)
            )
            for order in range(derivatives.size)
        ]
    )
    residual = float(
        np.linalg.norm(reconstructed - derivatives)
        / max(np.linalg.norm(derivatives), np.finfo(float).tiny)
    )
    return {
        "matching_rate": float(matching_rate),
        "polynomial_derivatives_at_zero": coefficients,
        "reconstructed_zero_time_derivatives": reconstructed,
        "relative_jet_residual": residual,
        "matched_derivative_count": int(derivatives.size),
    }


def moment_preserving_jet_subtraction(
    laplace_frequency: Array,
    raw_colored_laplace: Array,
    zero_time_derivatives: Array,
    *,
    white_contact: complex,
    matching_rate: float,
) -> dict[str, object]:
    r"""Remove a hydrodynamic UV contact and its known short-time jet.

    A regular microscopic Mori kernel has no frequency-independent term at
    large ``z``.  Therefore the coarse-grained white contact is cancelled in
    full.  The supplied colored derivatives are removed with the localized
    exponential jet from :func:`exponential_jet_counterterm`.  The remaining
    correction starts at ``O(z^(-N-1))`` for ``N`` supplied derivatives and
    cannot alter the exact microscopic moment prefix through that order.
    """

    z = np.asarray(laplace_frequency, dtype=float)
    raw = np.asarray(raw_colored_laplace, dtype=complex)
    if z.ndim != 1 or raw.shape != z.shape or np.any(z <= 0.0):
        raise ValueError("laplace and colored arrays must be matching positive vectors")
    if np.any(~np.isfinite(z)) or np.any(~np.isfinite(raw)):
        raise ValueError("laplace data must be finite")
    if not np.isfinite(white_contact):
        raise ValueError("white contact must be finite")
    jet = exponential_jet_counterterm(
        zero_time_derivatives, matching_rate=matching_rate
    )
    coefficients = np.asarray(jet["polynomial_derivatives_at_zero"])
    local_laplace = np.zeros_like(raw)
    for order, coefficient in enumerate(coefficients):
        local_laplace += coefficient / (z + matching_rate) ** (order + 1)
    renormalized = raw - local_laplace
    return {
        "laplace_frequency": z,
        "raw_colored_laplace": raw,
        "localized_jet_laplace": local_laplace,
        "renormalized_colored_laplace": renormalized,
        "white_contact": complex(white_contact),
        "white_contact_counterterm": complex(-white_contact),
        "renormalized_white_contact": 0.0,
        "preserved_large_z_orders": int(coefficients.size),
        "jet": jet,
        "matching_rate_is_scheme_parameter": True,
        "trajectory_data_used": False,
        "target_coefficients_used": False,
    }


def _positive_symmetric_spectral_fit(
    laplace: Array,
    terminator: Array,
    spectral_frequencies: Array,
    *,
    mass_constraint_weight: float,
) -> dict[str, object]:
    """Fit ``T(z)=int z/(z^2+w^2) dnu(w)`` with ``dnu>=0`` and unit mass."""

    z = np.asarray(laplace, dtype=float)
    target = np.asarray(terminator, dtype=float)
    omega = np.asarray(spectral_frequencies, dtype=float)
    basis = z[:, None] / (z[:, None] ** 2 + omega[None, :] ** 2)
    scale = np.maximum(np.abs(target), np.finfo(float).tiny)
    weighted_basis = basis / scale[:, None]
    weighted_target = target / scale
    augmented = np.vstack(
        [weighted_basis, mass_constraint_weight * np.ones((1, omega.size))]
    )
    right = np.concatenate([weighted_target, [mass_constraint_weight]])
    weights, _ = nnls(augmented, right, maxiter=20 * omega.size)
    mass = float(np.sum(weights))
    if mass > 0.0:
        weights /= mass
    prediction = basis @ weights
    relative_residual = float(
        np.linalg.norm((prediction - target) / scale)
        / np.sqrt(float(z.size))
    )
    return {
        "weights": weights,
        "prediction": prediction,
        "relative_residual": relative_residual,
        "pre_normalization_mass": mass,
        "minimum_weight": float(np.min(weights)),
        "normalization_residual": float(abs(np.sum(weights) - 1.0)),
    }


def embed_colored_memory_behind_exact_lanczos(
    times: Array,
    colored_memory: Array,
    laplace_frequency: Array,
    *,
    spectral_frequencies: Array,
    wavenumber: float | None = None,
    exchange: float = 1.0,
    mass_constraint_weight: float = 1.0e4,
) -> dict[str, object]:
    r"""Use a colored F-GHD correlation only as the deep Mori terminator.

    The microscopic XXX recurrents through ``mu26`` remain untouched.  The
    supplied finite-time colored correlation is normalized at ``t=0``,
    Laplace transformed, and represented by a nonnegative symmetric spectral
    quadrature of unit mass.  This guarantees a ``1/z`` large-frequency
    terminator and therefore cannot change the exact moment prefix.  A white
    hydrodynamic contact is deliberately not an input to this construction.
    """

    times = np.asarray(times, dtype=float)
    memory = np.asarray(colored_memory, dtype=float)
    z = np.asarray(laplace_frequency, dtype=float)
    omega = np.asarray(spectral_frequencies, dtype=float)
    if (
        times.ndim != 1
        or memory.shape != times.shape
        or times.size < 3
        or not np.isclose(times[0], 0.0)
        or np.any(np.diff(times) <= 0.0)
    ):
        raise ValueError("times and colored memory need an increasing grid from zero")
    if np.any(~np.isfinite(memory)) or memory[0] <= 0.0:
        raise ValueError("colored memory must be finite and positive at zero")
    if z.ndim != 1 or z.size < 3 or np.any(z <= 0.0) or np.any(~np.isfinite(z)):
        raise ValueError("laplace frequencies must be positive and finite")
    if (
        omega.ndim != 1
        or omega.size < 8
        or np.any(omega < 0.0)
        or np.any(np.diff(omega) <= 0.0)
    ):
        raise ValueError("spectral frequencies must be increasing and nonnegative")
    normalized_memory = memory / memory[0]
    target_terminator = np.asarray(
        [
            np.trapezoid(np.exp(-value * times) * normalized_memory, times)
            for value in z
        ]
    )
    fit = _positive_symmetric_spectral_fit(
        z,
        target_terminator,
        omega,
        mass_constraint_weight=mass_constraint_weight,
    )
    fitted_terminator = np.asarray(fit.pop("prediction"))
    weights = np.asarray(fit.pop("weights"))
    if wavenumber is None:
        lanczos = xxx_mori_long_wave_lanczos(exchange=exchange)
        mu0 = float(lanczos["mu0"])
        squared = np.asarray(lanczos["squared_recurrents"], dtype=float)
        prefix_kind = "long_wave_mu26"
    else:
        wave = float(wavenumber)
        if not np.isfinite(wave):
            raise ValueError("wavenumber must be finite")
        moments = xxx_mori_even_moments(
            np.asarray([wave]), exchange=exchange
        )
        mu0 = float(np.asarray(moments[0])[0])
        squared = np.asarray(
            xxx_mori_lanczos_recurrents(
                np.asarray([wave]), exchange=exchange
            )[0],
            dtype=float,
        )
        prefix_kind = "momentum_dependent_mu16"
    reconstructed = mori_kernel_from_lanczos_terminator(
        z, fitted_terminator, mu0, squared
    )
    return {
        "times": times,
        "normalized_colored_memory": normalized_memory,
        "laplace_frequency": z,
        "finite_time_target_terminator": target_terminator,
        "positive_spectral_terminator": fitted_terminator,
        "reconstructed_exact_prefix_kernel": reconstructed,
        "spectral_frequencies": omega,
        "spectral_weights": weights,
        "spectral_fit": fit,
        "nonzero_spectral_weights": int(np.count_nonzero(weights > 1.0e-14)),
        "exact_recurrent_count_preserved": int(squared.size),
        "exact_moment_order_preserved": int(2 * squared.size),
        "exact_squared_recurrents": squared,
        "exact_mu0": mu0,
        "exact_prefix_kind": prefix_kind,
        "wavenumber": None if wavenumber is None else float(wavenumber),
        "white_contact_input": 0.0,
        "white_contact_excluded_by_microscopic_large_z_regularity": True,
        "finite_pole_count_assumed": False,
        "spectral_grid_is_continuum_quadrature": True,
        "finite_time_tail_truncation_controlled": False,
        "spectral_node_convergence_controlled": False,
        "trajectory_data_used": False,
        "target_coefficients_used": False,
    }


def match_hydrodynamic_structure_through_exact_lanczos(
    times: Array,
    structure_factor: Array,
    laplace_frequency: Array,
    *,
    spectral_frequencies: Array,
    wavenumber: float,
    exchange: float = 1.0,
    lattice: bool = True,
    mass_constraint_weight: float = 1.0e4,
) -> dict[str, object]:
    r"""Match the *top-level* hydrodynamic kernel through an exact prefix.

    The finite-time structure factor fixes the physical Mori kernel on the
    declared Laplace band by the exact continuity inversion

    ``K_hyd(k,z)=(1/F_hyd(k,z)-z)/khat**2``.

    The exact finite-``k`` XXX recurrents are then peeled from this top-level
    kernel.  Only the resulting deep terminator is represented by a positive
    symmetric continuum.  This differs essentially from identifying a
    normalized hydrodynamic force correlator with the deep terminator: the
    inversion retains the absolute finite-frequency amplitude carried by the
    complete diffusion/noise propagation.
    """

    t = np.asarray(times, dtype=float)
    structure = np.asarray(structure_factor, dtype=float)
    z = np.asarray(laplace_frequency, dtype=float)
    omega = np.asarray(spectral_frequencies, dtype=float)
    if (
        t.ndim != 1
        or structure.shape != t.shape
        or t.size < 3
        or not np.isclose(t[0], 0.0)
        or np.any(np.diff(t) <= 0.0)
        or np.any(~np.isfinite(structure))
        or not np.isclose(structure[0], 1.0, rtol=1.0e-6, atol=1.0e-8)
    ):
        raise ValueError("structure factor needs an increasing grid from F(k,0)=1")
    if z.ndim != 1 or z.size < 3 or np.any(z <= 0.0) or np.any(~np.isfinite(z)):
        raise ValueError("Laplace frequencies must be positive and finite")
    if (
        omega.ndim != 1
        or omega.size < 8
        or np.any(omega < 0.0)
        or np.any(np.diff(omega) <= 0.0)
    ):
        raise ValueError("spectral frequencies must be increasing and nonnegative")
    wave = float(wavenumber)
    if not np.isfinite(wave):
        raise ValueError("wavenumber must be finite")
    effective_wave = 2.0 * np.sin(0.5 * wave) if lattice else wave
    if abs(effective_wave) <= np.finfo(float).eps:
        raise ValueError("wavenumber must be nonzero")

    structure_laplace = np.asarray(
        [np.trapezoid(np.exp(-value * t) * structure, t) for value in z]
    )
    top_kernel = (1.0 / structure_laplace - z) / effective_wave**2
    if np.any(~np.isfinite(top_kernel)) or np.any(top_kernel <= 0.0):
        raise RuntimeError("finite-window structure gives a nonpositive top-level kernel")

    moments = xxx_mori_even_moments(np.asarray([wave]), exchange=exchange)
    mu0 = float(np.asarray(moments[0])[0])
    squared = np.asarray(
        xxx_mori_lanczos_recurrents(np.asarray([wave]), exchange=exchange)[0],
        dtype=float,
    )
    peeled = mori_lanczos_terminator_from_kernel(z, top_kernel, mu0, squared)
    if np.any(~np.isfinite(peeled)):
        raise RuntimeError("exact-prefix inverse produced a nonfinite terminator")
    input_inside_exact_moment_interval = bool(np.all(peeled > 0.0))
    fit = _positive_symmetric_spectral_fit(
        z, peeled, omega, mass_constraint_weight=mass_constraint_weight
    )
    fitted_terminator = np.asarray(fit.pop("prediction"))
    weights = np.asarray(fit.pop("weights"))
    reconstructed = mori_kernel_from_lanczos_terminator(
        z, fitted_terminator, mu0, squared
    )
    relative_top_residual = float(
        np.linalg.norm((reconstructed - top_kernel) / top_kernel)
        / np.sqrt(float(z.size))
    )
    return {
        "times": t,
        "structure_factor_over_chi": structure,
        "laplace_frequency": z,
        "finite_time_structure_laplace": structure_laplace,
        "hydrodynamic_top_level_mori_kernel": top_kernel,
        "peeled_exact_prefix_terminator": peeled,
        "positive_spectral_terminator": fitted_terminator,
        "reconstructed_exact_prefix_kernel": reconstructed,
        "spectral_frequencies": omega,
        "spectral_weights": weights,
        "spectral_fit": fit,
        "top_level_relative_residual": relative_top_residual,
        "hydrodynamic_input_inside_exact_moment_interval": (
            input_inside_exact_moment_interval
        ),
        "nonzero_spectral_weights": int(np.count_nonzero(weights > 1.0e-14)),
        "exact_recurrent_count_preserved": int(squared.size),
        "exact_moment_order_preserved": int(2 * squared.size),
        "exact_squared_recurrents": squared,
        "exact_mu0": mu0,
        "exact_prefix_kind": "momentum_dependent_mu16",
        "wavenumber": wave,
        "effective_lattice_wavenumber": float(effective_wave),
        "white_contact_input": 0.0,
        "finite_pole_count_assumed": False,
        "hydrodynamic_force_shape_used_as_deep_terminator": False,
        "top_level_amplitude_retained_by_continuity_inversion": True,
        "trajectory_data_used": False,
        "target_coefficients_used": False,
    }


def match_kernels_to_exact_lanczos(
    laplace_frequency: Array,
    candidate_kernels: Array,
    *,
    spectral_frequencies: Array,
    spectral_relative_tolerance: float = 1.0e-2,
    cutoff_relative_tolerance: float = 5.0e-2,
    moment_interval_relative_tolerance: float = 1.0e-10,
    mass_constraint_weight: float = 1.0e4,
    required_tail_count: int | None = None,
) -> dict[str, object]:
    r"""Match a regulator sequence to the exact ten-recurrent XXX prefix.

    ``candidate_kernels[r,j]`` is a target-free theoretical Mori kernel at
    regulator ``r`` and Laplace frequency ``z[j]``.  The last two rows are
    treated as the finest regulator pair.  A pass requires every candidate to
    lie in the exact Stieltjes moment interval, a positive continuum
    terminator reconstruction at every regulator, and stability of the last
    pair over the whole frequency band.

    The finite frequency grid is a quadrature of an unrestricted positive
    measure, not a physical pole-count ansatz.  Its own node convergence must
    be audited by callers before a final physical claim.
    """

    z = np.asarray(laplace_frequency, dtype=float)
    kernels = np.asarray(candidate_kernels, dtype=float)
    omega = np.asarray(spectral_frequencies, dtype=float)
    if z.ndim != 1 or z.size < 3 or np.any(~np.isfinite(z)) or np.any(z <= 0.0):
        raise ValueError("laplace frequencies must be a positive finite vector")
    if kernels.ndim != 2 or kernels.shape[1] != z.size or kernels.shape[0] < 2:
        raise ValueError("candidate kernels must have shape (regulator,z) with >=2 rows")
    if np.any(~np.isfinite(kernels)):
        raise ValueError("candidate kernels must be finite")
    if (
        omega.ndim != 1
        or omega.size < 8
        or np.any(~np.isfinite(omega))
        or np.any(omega < 0.0)
        or np.any(np.diff(omega) <= 0.0)
    ):
        raise ValueError("spectral frequencies must be finite, nonnegative, and increasing")
    for value, name in [
        (spectral_relative_tolerance, "spectral tolerance"),
        (cutoff_relative_tolerance, "cutoff tolerance"),
        (moment_interval_relative_tolerance, "moment tolerance"),
        (mass_constraint_weight, "mass weight"),
    ]:
        if not np.isfinite(value) or value <= 0.0:
            raise ValueError(f"{name} must be positive and finite")
    if required_tail_count is None:
        required_tail_count = kernels.shape[0]
    if (
        not isinstance(required_tail_count, (int, np.integer))
        or required_tail_count < 2
        or required_tail_count > kernels.shape[0]
    ):
        raise ValueError("required_tail_count must lie between 2 and the regulator count")

    lanczos = xxx_mori_long_wave_lanczos()
    mu0 = float(lanczos["mu0"])
    squared = np.asarray(lanczos["squared_recurrents"], dtype=float)
    bounds = mori_lanczos_stieltjes_bounds(z, mu0, squared)
    lower = np.asarray(bounds["lower"])
    upper = np.asarray(bounds["upper"])
    slack = moment_interval_relative_tolerance * np.maximum(
        np.abs(upper), np.finfo(float).tiny
    )
    candidate_positive = kernels > 0.0
    inside = candidate_positive & (kernels >= lower[None, :] - slack[None, :]) & (
        kernels <= upper[None, :] + slack[None, :]
    )

    fits: list[dict[str, object]] = []
    reconstructed = []
    all_positive = True
    residuals = []
    for row, row_inside in zip(kernels, inside, strict=True):
        if np.all(row > 0.0):
            terminator = mori_lanczos_terminator_from_kernel(z, row, mu0, squared)
            terminator_positive = bool(
                np.all(np.isfinite(terminator)) and np.all(terminator > 0.0)
            )
        else:
            terminator_positive = False
        if terminator_positive and bool(np.all(row_inside)):
            fit = _positive_symmetric_spectral_fit(
                z,
                terminator,
                omega,
                mass_constraint_weight=mass_constraint_weight,
            )
            fitted_terminator = np.asarray(fit.pop("prediction"))
            reconstructed_row = mori_kernel_from_lanczos_terminator(
                z, fitted_terminator, mu0, squared
            )
            residual = float(fit["relative_residual"])
            weights = np.asarray(fit.pop("weights"))
            fit["nonzero_quadrature_weights"] = int(
                np.count_nonzero(weights > 1.0e-14)
            )
            fit["terminator_positive"] = True
            fit["spectral_weights_nonnegative"] = bool(np.all(weights >= 0.0))
        else:
            reconstructed_row = np.full_like(z, np.nan)
            residual = float("inf")
            fit = {
                "relative_residual": residual,
                "pre_normalization_mass": 0.0,
                "minimum_weight": float("nan"),
                "normalization_residual": float("inf"),
                "nonzero_quadrature_weights": 0,
                "terminator_positive": terminator_positive,
                "spectral_weights_nonnegative": False,
            }
        all_positive = all_positive and bool(fit["spectral_weights_nonnegative"])
        residuals.append(residual)
        fits.append(fit)
        reconstructed.append(reconstructed_row)

    last_scale = np.maximum(
        0.5 * np.abs(kernels[-1] + kernels[-2]), np.finfo(float).tiny
    )
    last_pair_relative_change = float(
        np.max(np.abs(kernels[-1] - kernels[-2]) / last_scale)
    )
    all_inside = bool(np.all(inside))
    required_slice = slice(kernels.shape[0] - required_tail_count, kernels.shape[0])
    tail_inside = bool(np.all(inside[required_slice]))
    spectral_pass_all = bool(
        np.all(np.asarray(residuals) <= spectral_relative_tolerance)
    )
    spectral_pass = bool(
        np.all(
            np.asarray(residuals)[required_slice]
            <= spectral_relative_tolerance
        )
    )
    tail_positive = bool(
        all(
            bool(fit["spectral_weights_nonnegative"])
            for fit in fits[required_slice]
        )
    )
    cutoff_pass = bool(last_pair_relative_change <= cutoff_relative_tolerance)
    matching_complete = bool(
        tail_inside and tail_positive and spectral_pass and cutoff_pass
    )
    return {
        "laplace_frequency": z,
        "moment_bounds_lower": lower,
        "moment_bounds_upper": upper,
        "inside_moment_interval": inside,
        "candidate_kernels_positive": candidate_positive,
        "reconstructed_moment_preserving_kernels": np.asarray(reconstructed),
        "spectral_fits": fits,
        "maximum_spectral_relative_residual": float(np.max(residuals)),
        "last_pair_maximum_relative_change": last_pair_relative_change,
        "all_candidates_inside_stieltjes_bounds": all_inside,
        "required_tail_count": int(required_tail_count),
        "required_tail_inside_stieltjes_bounds": tail_inside,
        "all_spectral_weights_nonnegative": all_positive,
        "required_tail_spectral_weights_nonnegative": tail_positive,
        "all_regulators_spectral_reconstruction_pass": spectral_pass_all,
        "spectral_reconstruction_pass": spectral_pass,
        "cutoff_stability_pass": cutoff_pass,
        "matching_complete": matching_complete,
        "exact_recurrent_count_preserved": int(squared.size),
        "exact_moment_order_preserved": int(2 * squared.size),
        "finite_pole_count_assumed": False,
        "spectral_grid_is_continuum_quadrature": True,
        "spectral_node_convergence_still_required": True,
        "trajectory_data_used": False,
        "target_coefficients_used": False,
    }
