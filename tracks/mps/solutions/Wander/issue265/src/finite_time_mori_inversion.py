"""Finite-time structure-factor and Mori-correction inversion.

The routines use spin profiles generated from opposite weak walls to isolate
the odd, linear-response propagator.  They never accept Burgers coefficients
as inputs.  A converged numerical dataset can therefore determine the missing
``F1_perp`` without tuning to a target ``a`` or ``D``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.integrate import trapezoid
from scipy.signal import savgol_filter


Array = np.ndarray


@dataclass(frozen=True)
class FiniteTimeStructure:
    k: Array
    t: Array
    q: Array
    structure: Array
    leading: Array
    correction: Array


def opposite_wall_linear_response(up: Array, down: Array) -> Array:
    """Return the orientation-odd normalized wall and cancel even powers."""

    up = np.asarray(up, dtype=float)
    down = np.asarray(down, dtype=float)
    if up.shape != down.shape or up.ndim != 2:
        raise ValueError("up/down walls must have the same (Nt,Nx) shape")
    if np.any(~np.isfinite(up)) or np.any(~np.isfinite(down)):
        raise ValueError("wall profiles must be finite")
    return 0.5 * (up - down)


def local_current_vertex(
    x: Array,
    t: Array,
    field: Array,
    current: Array,
    *,
    mu: float,
    orientation: int,
    t_window: tuple[float, float],
    x_crop: tuple[float, float],
    smoothing_window: int = 31,
    smoothing_order: int = 7,
) -> dict[str, float | int]:
    r"""Project the normalized linear-response current onto a quadratic basis.

    The bond current is put in the same canonical wall orientation as the
    article-normalized field and regressed against

    ``j/mu = c(t) + a*U_bond**2/2 - D_local*grad(U) + residual``.

    Spatial centering removes the arbitrary current zero mode ``c(t)`` at
    every time.  ``D_local`` is an instantaneous local projection and is not
    the zero-frequency Mori coefficient when the residual has memory.
    """

    x = np.asarray(x, dtype=float)
    t = np.asarray(t, dtype=float)
    field = np.asarray(field, dtype=float)
    current = np.asarray(current, dtype=float)
    if field.shape != (t.size, x.size):
        raise ValueError("field must have shape (Nt,Nx)")
    if current.shape != (t.size, x.size - 1):
        raise ValueError("current must have shape (Nt,Nx-1)")
    if orientation not in (-1, 1) or mu <= 0.0:
        raise ValueError("orientation must be +/-1 and mu must be positive")
    if smoothing_window <= smoothing_order or smoothing_window % 2 != 1:
        raise ValueError("smoothing window must be odd and exceed the order")
    canonical = float(orientation) * field
    canonical_current = float(orientation) * current / float(mu)
    smooth = savgol_filter(
        canonical,
        window_length=smoothing_window,
        polyorder=smoothing_order,
        axis=1,
        mode="interp",
    )
    bond_field = 0.5 * (smooth[:, :-1] + smooth[:, 1:])
    gradient = np.diff(smooth, axis=1) / np.diff(x)[None, :]
    bond_x = 0.5 * (x[:-1] + x[1:])
    selected_t = (t >= t_window[0]) & (t <= t_window[1])
    selected_x = (bond_x >= x_crop[0]) & (bond_x <= x_crop[1])
    if np.count_nonzero(selected_t) < 3 or np.count_nonzero(selected_x) < 20:
        raise ValueError("current-vertex window is too small")
    response = canonical_current[selected_t][:, selected_x].copy()
    nonlinear = 0.5 * bond_field[selected_t][:, selected_x] ** 2
    diffusion = -gradient[selected_t][:, selected_x]
    # Project out the spatially constant current independently at each time.
    response -= np.mean(response, axis=1, keepdims=True)
    nonlinear -= np.mean(nonlinear, axis=1, keepdims=True)
    diffusion -= np.mean(diffusion, axis=1, keepdims=True)
    design = np.column_stack((nonlinear.ravel(), diffusion.ravel()))
    target = response.ravel()
    coefficients, *_ = np.linalg.lstsq(design, target, rcond=None)
    residual = target - design @ coefficients
    return {
        "a_current_vertex": float(coefficients[0]),
        "D_instantaneous_local": float(coefficients[1]),
        "residual_rms": float(np.sqrt(np.mean(residual**2))),
        "current_rms": float(np.sqrt(np.mean(target**2))),
        "design_condition_number": float(np.linalg.cond(design)),
        "n_observations": int(target.size),
    }


def conditional_vertex_zero_amplitude_limit(
    mu: Array,
    orientation: Array,
    coefficient: Array,
) -> dict[str, Array | float | int]:
    r"""Extrapolate the conditional current projection to ``mu->0``.

    Spin flip allows the canonical, orientation-conditioned coefficient to
    have the expansion

    ``a_sigma(mu)=a0+e2*mu**2+e4*mu**4+sigma*(o1*mu+o3*mu**3)+...``.

    For an exact spin-flip pair, the odd orientation terms vanish; they are
    retained as numerical-symmetry diagnostics.  The intercept ``a0`` is a
    quadratic-basis coordinate of the normalized *linear* response current,
    not the ordinary zero-field quadratic Kubo vertex (which remains zero).
    This routine never accepts a target value for ``a0``.
    """

    mu = np.asarray(mu, dtype=float)
    orientation = np.asarray(orientation, dtype=int)
    coefficient = np.asarray(coefficient, dtype=float)
    if (
        mu.ndim != 1
        or orientation.shape != mu.shape
        or coefficient.shape != mu.shape
        or mu.size < 8
        or np.any(~np.isfinite(mu + coefficient))
        or np.any(mu <= 0.0)
        or np.any(~np.isin(orientation, (-1, 1)))
    ):
        raise ValueError("need at least eight finite paired-amplitude observations")
    amplitudes = np.unique(mu)
    if amplitudes.size < 4:
        raise ValueError("at least four distinct amplitudes are required")
    for amplitude in amplitudes:
        signs = orientation[np.isclose(mu, amplitude, rtol=0.0, atol=1e-14)]
        if np.count_nonzero(signs == 1) != 1 or np.count_nonzero(signs == -1) != 1:
            raise ValueError("each amplitude must have exactly one observation per orientation")

    full_design = np.column_stack(
        [
            np.ones(mu.size),
            mu**2,
            mu**4,
            orientation * mu,
            orientation * mu**3,
        ]
    )
    restricted_design = np.column_stack(
        [np.ones(mu.size), mu**2, orientation * mu, orientation * mu**3]
    )

    def solve(design: Array) -> tuple[Array, Array, Array]:
        beta, *_ = np.linalg.lstsq(design, coefficient, rcond=None)
        residual = coefficient - design @ beta
        dof = max(coefficient.size - design.shape[1], 1)
        covariance = float(residual @ residual / dof) * np.linalg.pinv(
            design.T @ design
        )
        return beta, covariance, residual

    full, covariance, residual = solve(full_design)
    restricted, _, restricted_residual = solve(restricted_design)
    leave_one_out: list[float] = []
    for amplitude in amplitudes:
        selected = ~np.isclose(mu, amplitude, rtol=0.0, atol=1e-14)
        beta, *_ = np.linalg.lstsq(
            restricted_design[selected], coefficient[selected], rcond=None
        )
        leave_one_out.append(float(beta[0]))
    return {
        "a0_one_sided": float(full[0]),
        "a0_restricted": float(restricted[0]),
        "even_mu2": float(full[1]),
        "even_mu4": float(full[2]),
        "odd_mu1": float(full[3]),
        "odd_mu3": float(full[4]),
        "a0_standard_error": float(np.sqrt(max(covariance[0, 0], 0.0))),
        "a0_scheme_difference": float(abs(full[0] - restricted[0])),
        "leave_one_amplitude_out_a0": np.asarray(leave_one_out),
        "leave_one_amplitude_out_spread": float(np.ptp(leave_one_out)),
        "full_residual_rms": float(np.sqrt(np.mean(residual**2))),
        "restricted_residual_rms": float(
            np.sqrt(np.mean(restricted_residual**2))
        ),
        "full_design_condition_number": float(np.linalg.cond(full_design)),
        "n_amplitudes": int(amplitudes.size),
        "n_observations": int(mu.size),
    }


def even_amplitude_zero_limit(mu: Array, values: Array) -> dict[str, Array | float]:
    r"""Extrapolate an orientation-even observable to ``mu=0``.

    ``values`` may contain trailing frequency or observable axes.  The full
    model is ``v(mu)=v0+v2*mu**2+v4*mu**4``; comparison with the restricted
    ``v0+v2*mu**2`` model reports the leading scheme dependence.  This is used
    for the opposite-wall linear Mori correction, where odd powers have
    already been cancelled before the extrapolation.
    """

    mu = np.asarray(mu, dtype=float)
    values = np.asarray(values, dtype=float)
    if (
        mu.ndim != 1
        or values.shape[0] != mu.size
        or mu.size < 4
        or np.unique(mu).size != mu.size
        or np.any(mu <= 0.0)
        or np.any(~np.isfinite(mu))
        or np.any(~np.isfinite(values))
    ):
        raise ValueError("need at least four distinct finite positive amplitudes")
    full_design = np.column_stack([np.ones(mu.size), mu**2, mu**4])
    restricted_design = np.column_stack([np.ones(mu.size), mu**2])
    flattened = values.reshape(mu.size, -1)
    full, *_ = np.linalg.lstsq(full_design, flattened, rcond=None)
    restricted, *_ = np.linalg.lstsq(restricted_design, flattened, rcond=None)
    residual = flattened - full_design @ full
    dof = max(mu.size - full_design.shape[1], 1)
    inverse_gram = np.linalg.pinv(full_design.T @ full_design)
    residual_variance = np.sum(residual**2, axis=0) / dof
    standard_error = np.sqrt(np.maximum(inverse_gram[0, 0] * residual_variance, 0.0))
    trailing = values.shape[1:]
    reshape = lambda value: np.asarray(value).reshape(trailing)  # noqa: E731
    return {
        "zero_amplitude_limit": reshape(full[0]),
        "mu2_coefficient": reshape(full[1]),
        "mu4_coefficient": reshape(full[2]),
        "zero_amplitude_restricted": reshape(restricted[0]),
        "zero_amplitude_standard_error": reshape(standard_error),
        "zero_amplitude_scheme_difference": reshape(np.abs(full[0] - restricted[0])),
        "residual_rms": reshape(np.sqrt(np.mean(residual**2, axis=0))),
        "condition_number": float(np.linalg.cond(full_design)),
    }


def structure_factor_from_wall(
    x: Array,
    t: Array,
    wall: Array,
    mode_indices: Array,
) -> tuple[Array, Array]:
    r"""Deconvolve the initial wall gradient to obtain ``S(k,t)/S(k,0)``.

    The spatial transform is evaluated by direct trapezoidal quadrature rather
    than assuming the wall itself is periodic.  Only its localized derivative
    is transformed.
    """

    x = np.asarray(x, dtype=float)
    t = np.asarray(t, dtype=float)
    wall = np.asarray(wall, dtype=float)
    modes = np.asarray(mode_indices, dtype=int)
    if x.ndim != 1 or t.ndim != 1 or wall.shape != (t.size, x.size):
        raise ValueError("expected x:(Nx,), t:(Nt,), wall:(Nt,Nx)")
    if x.size < 16 or t.size < 3 or np.any(np.diff(x) <= 0.0) or np.any(np.diff(t) <= 0.0):
        raise ValueError("grids must be sufficiently large and increasing")
    if modes.ndim != 1 or modes.size == 0 or np.any(modes <= 0):
        raise ValueError("mode indices must be a non-empty positive vector")
    dx = np.diff(x)
    if not np.allclose(dx, dx[0], rtol=1e-10, atol=1e-12):
        raise ValueError("x must be uniformly spaced")
    length = float(dx[0] * x.size)
    k = 2.0 * np.pi * modes / length
    gradient = np.gradient(wall, x, axis=1, edge_order=2)
    transform = np.empty((t.size, modes.size), dtype=complex)
    for index, wavenumber in enumerate(k):
        phase = np.exp(-1j * wavenumber * x)
        transform[:, index] = trapezoid(gradient * phase[None, :], x, axis=1)
    initial = transform[0]
    if np.any(np.abs(initial) < 1e-10):
        raise ValueError("initial wall has insufficient weight at a requested mode")
    normalized = transform / initial[None, :]
    return k, np.real(normalized)


def finite_time_structure_correction(
    k: Array,
    t: Array,
    structure: Array,
    leading_fourier,
    *,
    lambda_kpz: float,
    t_window: tuple[float, float],
) -> FiniteTimeStructure:
    r"""Return samples of ``F1=t**(1/3)*(F-F0)`` at ``q=k*(lambda*t)**(2/3)``."""

    k = np.asarray(k, dtype=float)
    t = np.asarray(t, dtype=float)
    structure = np.asarray(structure, dtype=float)
    if structure.shape != (t.size, k.size):
        raise ValueError("structure must have shape (Nt,Nk)")
    if lambda_kpz <= 0.0 or not 0.0 < t_window[0] < t_window[1]:
        raise ValueError("invalid KPZ scale or time window")
    selected = (t >= t_window[0]) & (t <= t_window[1])
    if np.count_nonzero(selected) < 3:
        raise ValueError("time window contains fewer than three samples")
    ts = t[selected]
    values = structure[selected]
    q = ts[:, None] ** (2.0 / 3.0) * lambda_kpz ** (2.0 / 3.0) * k[None, :]
    leading = np.asarray(leading_fourier(q), dtype=float)
    if leading.shape != q.shape or np.any(~np.isfinite(leading)):
        raise ValueError("leading Fourier function returned invalid values")
    correction = ts[:, None] ** (1.0 / 3.0) * (values - leading)
    return FiniteTimeStructure(
        k=np.broadcast_to(k[None, :], q.shape),
        t=np.broadcast_to(ts[:, None], q.shape),
        q=q,
        structure=values,
        leading=leading,
        correction=correction,
    )


def decompose_dilation_correction(
    q: Array,
    correction: Array,
    leading_fourier_derivative,
    *,
    weights: Array | None = None,
) -> dict[str, Array | float]:
    r"""Project ``F1`` onto dilation ``q*d_q F0`` and return ``F1_perp``."""

    q = np.asarray(q, dtype=float)
    correction = np.asarray(correction, dtype=float)
    if q.shape != correction.shape or np.any(~np.isfinite(q + correction)):
        raise ValueError("q and correction must be finite arrays of equal shape")
    basis = q * np.asarray(leading_fourier_derivative(q), dtype=float)
    if basis.shape != q.shape or np.any(~np.isfinite(basis)):
        raise ValueError("leading derivative returned invalid values")
    if weights is None:
        weight = np.ones_like(q)
    else:
        weight = np.broadcast_to(np.asarray(weights, dtype=float), q.shape)
    if np.any(~np.isfinite(weight)) or np.any(weight < 0.0):
        raise ValueError("weights must be finite and non-negative")
    denominator = float(np.sum(weight * basis**2))
    if denominator <= 0.0:
        raise ValueError("dilation basis has zero weighted norm")
    coefficient = float(np.sum(weight * basis * correction) / denominator)
    perpendicular = correction - coefficient * basis
    return {
        "dilation_coefficient": coefficient,
        "dilation_basis": basis,
        "perpendicular": perpendicular,
        "relative_perpendicular_norm": float(
            np.sqrt(np.sum(weight * perpendicular**2) / np.sum(weight * correction**2))
        )
        if np.sum(weight * correction**2) > 0.0
        else 0.0,
    }


def finite_q_mori_k0_correction(
    q: Array,
    correction: Array,
    leading_fourier,
    *,
    lambda_kpz: float,
    s_values: Array,
    q_max: float | None = None,
    n_bins: int = 96,
    n_grid: int = 4001,
) -> dict[str, Array | float | int]:
    r"""Numerically evaluate the finite-time ``k**0`` Mori correction.

    With ``u=q**(3/2)``, the transform in the finite-time expansion becomes

    ``Phi1(s) = 3/2 int_0^inf dq exp(-s*q**(3/2))*F1(q)``.

    Scattered ``(q,F1)`` samples are first averaged in fixed bins and then
    linearly interpolated.  The integral is deliberately truncated at the
    largest supported ``q``; ``tail_exponential_weight`` reports
    ``exp(-s*q_max**(3/2))`` so callers can reject poorly controlled small-s
    values.  No target transport coefficient enters this calculation.
    """

    q = np.asarray(q, dtype=float).ravel()
    correction = np.asarray(correction, dtype=float).ravel()
    s_values = np.asarray(s_values, dtype=float).ravel()
    if q.shape != correction.shape or q.size < 8:
        raise ValueError("q and correction must contain at least eight samples")
    if np.any(~np.isfinite(q + correction)) or np.any(q < 0.0):
        raise ValueError("q and correction must be finite with q non-negative")
    if lambda_kpz <= 0.0 or np.any(~np.isfinite(s_values)) or np.any(s_values <= 0.0):
        raise ValueError("lambda and all Laplace variables must be positive")
    supported_max = float(np.max(q)) if q_max is None else min(float(q_max), float(np.max(q)))
    if supported_max <= 0.0 or n_bins < 8 or n_grid < 101:
        raise ValueError("invalid quadrature support or resolution")
    selected = q <= supported_max
    edges = np.linspace(0.0, supported_max, n_bins + 1)
    index = np.minimum(np.searchsorted(edges, q[selected], side="right") - 1, n_bins - 1)
    centers: list[float] = [0.0]
    values: list[float] = [0.0]
    for bin_index in range(n_bins):
        mask = index == bin_index
        if np.any(mask):
            centers.append(float(np.mean(q[selected][mask])))
            values.append(float(np.mean(correction[selected][mask])))
    order = np.argsort(centers)
    centers_array = np.asarray(centers)[order]
    values_array = np.asarray(values)[order]
    grid = np.linspace(0.0, supported_max, n_grid)
    f1 = np.interp(grid, centers_array, values_array)
    f0 = np.asarray(leading_fourier(grid), dtype=float)
    if f0.shape != grid.shape or np.any(~np.isfinite(f0)):
        raise ValueError("leading Fourier function returned invalid values")
    phi0 = np.empty_like(s_values)
    phi1 = np.empty_like(s_values)
    for position, laplace in enumerate(s_values):
        exponential = np.exp(-laplace * grid ** 1.5)
        phi0[position] = 1.5 * trapezoid(
            grid**0.5 * exponential * f0, grid
        )
        phi1[position] = 1.5 * trapezoid(exponential * f1, grid)
    if np.any(phi0 <= 0.0):
        raise ValueError("truncated leading transform is non-positive")
    delta_kernel = -(lambda_kpz ** (4.0 / 3.0)) * phi1 / phi0**2
    return {
        "s": s_values,
        "Phi0_truncated": phi0,
        "Phi1_truncated": phi1,
        "delta_K1_truncated": delta_kernel,
        "q_max": supported_max,
        "tail_exponential_weight": np.exp(-s_values * supported_max**1.5),
        "n_input_samples": int(np.count_nonzero(selected)),
        "n_nonempty_bins": int(centers_array.size - 1),
    }


def cross_validate_finite_time_structure(
    k: Array,
    t: Array,
    structure: Array,
    leading_fourier,
    *,
    lambda_kpz: float,
    train_window: tuple[float, float],
    test_window: tuple[float, float],
    q_max: float,
    n_bins: int = 64,
) -> dict[str, float | int]:
    r"""Fit ``F1(q)`` on one time interval and predict a disjoint interval."""

    if train_window[1] >= test_window[0]:
        raise ValueError("training and test windows must be ordered and disjoint")
    train = finite_time_structure_correction(
        k,
        t,
        structure,
        leading_fourier,
        lambda_kpz=lambda_kpz,
        t_window=train_window,
    )
    test = finite_time_structure_correction(
        k,
        t,
        structure,
        leading_fourier,
        lambda_kpz=lambda_kpz,
        t_window=test_window,
    )
    selected = train.q <= q_max
    q_train = train.q[selected]
    f1_train = train.correction[selected]
    edges = np.linspace(float(np.min(q_train)), float(np.max(q_train)), n_bins + 1)
    centers: list[float] = []
    values: list[float] = []
    for left, right in zip(edges[:-1], edges[1:], strict=True):
        mask = (q_train >= left) & (q_train < right if right < edges[-1] else q_train <= right)
        if np.any(mask):
            centers.append(float(np.mean(q_train[mask])))
            values.append(float(np.mean(f1_train[mask])))
    if len(centers) < 8:
        raise ValueError("training interval has insufficient q coverage")
    centers_array = np.asarray(centers)
    values_array = np.asarray(values)
    supported = (
        (test.q >= centers_array[0])
        & (test.q <= min(q_max, centers_array[-1]))
    )
    if np.count_nonzero(supported) < 8:
        raise ValueError("test interval has insufficient overlap with training q support")
    predicted_f1 = np.interp(test.q[supported], centers_array, values_array)
    leading_prediction = test.leading[supported]
    corrected_prediction = leading_prediction + test.t[supported] ** (-1.0 / 3.0) * predicted_f1
    observed = test.structure[supported]
    leading_rms = float(np.sqrt(np.mean((observed - leading_prediction) ** 2)))
    corrected_rms = float(np.sqrt(np.mean((observed - corrected_prediction) ** 2)))
    return {
        "leading_rms": leading_rms,
        "corrected_rms": corrected_rms,
        "rms_ratio_corrected_to_leading": corrected_rms / leading_rms
        if leading_rms > 0.0
        else 0.0,
        "fractional_rms_reduction": 1.0 - corrected_rms / leading_rms
        if leading_rms > 0.0
        else 0.0,
        "n_test_samples": int(np.count_nonzero(supported)),
        "q_train_min": float(centers_array[0]),
        "q_train_max": float(centers_array[-1]),
    }
