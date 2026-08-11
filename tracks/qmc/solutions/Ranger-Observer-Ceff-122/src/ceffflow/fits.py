"""Covariance-aware finite-size fits for Casimir central charges."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.optimize import LinearConstraint, minimize


@dataclass(frozen=True, slots=True)
class CasimirFit:
    """Result of a generalized least-squares Casimir fit."""

    central_charge: float
    standard_error: float
    parameters: dict[str, float]
    parameter_covariance: NDArray[np.float64]
    chi2: float
    dof: int
    leave_one_out: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class MonotonicityResult:
    """Likelihood-ratio test against a nonincreasing resolution curve."""

    constrained_curve: NDArray[np.float64]
    statistic: float
    bootstrap_p_value: float
    bootstrap_draws: int


def _validated_inputs(
    lengths: ArrayLike,
    values: ArrayLike,
    covariance: ArrayLike,
) -> tuple[
    NDArray[np.float64],
    NDArray[np.float64],
    NDArray[np.float64],
]:
    sizes = np.asarray(lengths, dtype=float)
    observations = np.asarray(values, dtype=float)
    matrix = np.asarray(covariance, dtype=float)
    if sizes.ndim != 1 or observations.shape != sizes.shape:
        raise ValueError("lengths and values must be one-dimensional and aligned")
    if matrix.shape != (sizes.size, sizes.size):
        raise ValueError("covariance has the wrong shape")
    if np.any(sizes <= 0.0) or not np.all(np.isfinite(observations)):
        raise ValueError("lengths must be positive and values finite")
    if not np.allclose(matrix, matrix.T, rtol=1e-12, atol=1e-15):
        raise ValueError("covariance must be symmetric")
    try:
        np.linalg.cholesky(matrix)
    except np.linalg.LinAlgError as exc:
        raise ValueError("covariance must be positive definite") from exc
    return sizes, observations, matrix


def _fit_once(
    lengths: NDArray[np.float64],
    values: NDArray[np.float64],
    covariance: NDArray[np.float64],
    *,
    alpha: float,
    include_l3: bool,
) -> tuple[
    NDArray[np.float64],
    NDArray[np.float64],
    float,
    int,
]:
    columns = [lengths, 1.0 / lengths]
    if include_l3:
        columns.append(1.0 / lengths**3)
    design = np.column_stack(columns)
    if design.shape[0] < design.shape[1]:
        raise ValueError("not enough widths for the requested fit")
    cholesky = np.linalg.cholesky(covariance)
    whitened_design = np.linalg.solve(cholesky, design)
    whitened_values = np.linalg.solve(cholesky, values)
    normal = whitened_design.T @ whitened_design
    right_hand_side = whitened_design.T @ whitened_values
    try:
        parameter_covariance = np.linalg.inv(normal)
        parameters = np.linalg.solve(normal, right_hand_side)
    except np.linalg.LinAlgError as exc:
        raise ValueError("finite-size design matrix is singular") from exc
    residual = whitened_values - whitened_design @ parameters
    chi2 = float(residual @ residual)
    dof = int(design.shape[0] - design.shape[1])
    return parameters, parameter_covariance, chi2, dof


def casimir_gls(
    lengths: ArrayLike,
    values: ArrayLike,
    covariance: ArrayLike,
    *,
    alpha: float,
    include_l3: bool = True,
    compute_leave_one_out: bool = True,
) -> CasimirFit:
    r"""Fit \(fL-\pi\alpha c/(6L)+b/L^3\) by GLS."""

    if alpha <= 0.0:
        raise ValueError("alpha must be positive")
    sizes, observations, matrix = _validated_inputs(
        lengths, values, covariance
    )
    parameters, parameter_covariance, chi2, dof = _fit_once(
        sizes,
        observations,
        matrix,
        alpha=alpha,
        include_l3=include_l3,
    )
    casimir_coefficient = float(parameters[1])
    scale = -6.0 / (np.pi * alpha)
    central_charge = scale * casimir_coefficient
    standard_error = abs(scale) * float(
        np.sqrt(max(parameter_covariance[1, 1], 0.0))
    )
    leave_one_out: list[float] = []
    if compute_leave_one_out and sizes.size > len(parameters):
        for omitted in range(sizes.size):
            keep = np.arange(sizes.size) != omitted
            reduced_parameters, _, _, _ = _fit_once(
                sizes[keep],
                observations[keep],
                matrix[np.ix_(keep, keep)],
                alpha=alpha,
                include_l3=include_l3,
            )
            leave_one_out.append(scale * float(reduced_parameters[1]))
    names = ["bulk", "casimir"]
    if include_l3:
        names.append("l3")
    return CasimirFit(
        central_charge=float(central_charge),
        standard_error=standard_error,
        parameters={
            name: float(value) for name, value in zip(names, parameters, strict=True)
        },
        parameter_covariance=parameter_covariance,
        chi2=chi2,
        dof=dof,
        leave_one_out=tuple(leave_one_out),
    )


def blockwise_casimir(
    lengths: ArrayLike,
    blocks: ArrayLike,
    *,
    background: ArrayLike | None = None,
    include_l3: bool = True,
) -> NDArray[np.float64]:
    """Return one OLS Casimir coefficient per longitudinal block."""

    sizes = np.asarray(lengths, dtype=float)
    values = np.asarray(blocks, dtype=float)
    if values.ndim != 2 or values.shape[1] != sizes.size:
        raise ValueError("blocks must have shape (n_blocks, n_lengths)")
    corrected = values.copy()
    if background is not None:
        curve = np.asarray(background, dtype=float)
        if curve.shape != sizes.shape:
            raise ValueError("background must align with lengths")
        corrected -= curve[None, :]
    columns = [sizes, 1.0 / sizes]
    if include_l3:
        columns.append(1.0 / sizes**3)
    design = np.column_stack(columns)
    if design.shape[0] <= design.shape[1]:
        raise ValueError("not enough widths for blockwise Casimir fit")
    coefficients = corrected @ np.linalg.pinv(design).T
    return -6.0 * coefficients[:, 1] / np.pi


def covariance_weighted_casimir_samples(
    lengths: ArrayLike,
    blocks: ArrayLike,
    *,
    background: ArrayLike | None = None,
    alpha: float = 1.0,
    include_l3: bool = True,
) -> NDArray[np.float64]:
    """Return block samples whose mean and error equal the width-GLS fit.

    The empirical coupled-width covariance fixes one linear GLS weight vector.
    Applying that vector to every block preserves common-random-number
    alignment across resolution points while reproducing the GLS estimate and
    its propagated standard error exactly.
    """

    if alpha <= 0.0:
        raise ValueError("alpha must be positive")
    sizes = np.asarray(lengths, dtype=float)
    values = np.asarray(blocks, dtype=float)
    if sizes.ndim != 1 or np.any(sizes <= 0.0):
        raise ValueError("lengths must be one-dimensional and positive")
    if values.ndim != 2 or values.shape[1] != sizes.size:
        raise ValueError("blocks must have shape (n_blocks, n_lengths)")
    if values.shape[0] < 2 or not np.all(np.isfinite(values)):
        raise ValueError("at least two finite blocks are required")
    corrected = values.copy()
    if background is not None:
        curve = np.asarray(background, dtype=float)
        if curve.shape != sizes.shape:
            raise ValueError("background must align with lengths")
        corrected -= curve[None, :]
    columns = [sizes, 1.0 / sizes]
    if include_l3:
        columns.append(1.0 / sizes**3)
    design = np.column_stack(columns)
    if design.shape[0] <= design.shape[1]:
        raise ValueError("not enough widths for covariance-weighted fitting")
    covariance = np.cov(corrected, rowvar=False, ddof=1)
    try:
        np.linalg.cholesky(covariance)
        inverse_design = np.linalg.solve(covariance, design)
        normal = design.T @ inverse_design
        mapping = np.linalg.solve(normal, inverse_design.T)
    except np.linalg.LinAlgError as exc:
        raise ValueError("empirical width covariance is not positive definite") from exc
    scale = -6.0 / (np.pi * alpha)
    weights = scale * mapping[1]
    return np.asarray(corrected @ weights, dtype=float)


def _constrained_curve(
    values: NDArray[np.float64],
    covariance: NDArray[np.float64],
) -> tuple[NDArray[np.float64], float]:
    # ``monotonicity_test`` already requires a positive-definite covariance.
    # A pseudoinverse is therefore both unnecessary and scientifically wrong
    # for high-precision analytic anchors: its relative singular-value cutoff
    # can silently assign an exact endpoint zero weight.  Solve against the
    # identity so every positive covariance eigenmode remains in the GLS
    # metric, even when the condition number is large.
    inverse = np.linalg.solve(covariance, np.eye(values.size))
    inverse = 0.5 * (inverse + inverse.T)
    optimization_inverse = inverse / max(float(np.linalg.norm(inverse, 2)), 1.0)

    def objective(candidate: NDArray[np.float64]) -> float:
        residual = candidate - values
        return float(residual @ optimization_inverse @ residual)

    def gradient(candidate: NDArray[np.float64]) -> NDArray[np.float64]:
        return 2.0 * optimization_inverse @ (candidate - values)

    count = values.size
    difference = np.zeros((count - 1, count))
    for index in range(count - 1):
        difference[index, index] = 1.0
        difference[index, index + 1] = -1.0
    result = minimize(
        objective,
        np.minimum.accumulate(values),
        jac=gradient,
        method="SLSQP",
        constraints=LinearConstraint(difference, 0.0, np.inf),
        options={"ftol": 1e-12, "maxiter": 1_000},
    )
    if not result.success:
        raise RuntimeError(f"isotonic optimization failed: {result.message}")
    constrained = np.asarray(result.x, dtype=float)
    residual = constrained - values
    statistic = float(residual @ inverse @ residual)
    return constrained, statistic


def monotonicity_test(
    values: ArrayLike,
    covariance: ArrayLike,
    *,
    bootstrap_draws: int = 2_000,
    seed: int = 0,
) -> MonotonicityResult:
    """Bootstrap a global test of a nonincreasing resolution curve."""

    estimates = np.asarray(values, dtype=float)
    matrix = np.asarray(covariance, dtype=float)
    if estimates.ndim != 1 or estimates.size < 2:
        raise ValueError("values need at least two resolutions")
    if matrix.shape != (estimates.size, estimates.size):
        raise ValueError("covariance has the wrong shape")
    if bootstrap_draws < 100:
        raise ValueError("bootstrap_draws must be at least 100")
    np.linalg.cholesky(matrix)
    constrained, statistic = _constrained_curve(estimates, matrix)
    rng = np.random.default_rng(seed)
    simulated = rng.multivariate_normal(
        constrained, matrix, size=bootstrap_draws
    )
    exceedances = 0
    for draw in simulated:
        _, bootstrap_statistic = _constrained_curve(draw, matrix)
        exceedances += bootstrap_statistic >= statistic - 1e-12
    p_value = (exceedances + 1.0) / (bootstrap_draws + 1.0)
    return MonotonicityResult(
        constrained_curve=constrained,
        statistic=statistic,
        bootstrap_p_value=float(p_value),
        bootstrap_draws=bootstrap_draws,
    )
