"""Numerical convergence gate for confirmatory Burgers tests."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

import numpy as np
from scipy.interpolate import RegularGridInterpolator

from .analytic_mechanism import front_linear_response_diagnostics
from .research_dataset import ResearchDataset
from .tension_resolution import front_width_series, validate_grid_data


Array = np.ndarray
ConvergenceStatus = Literal[
    "accepted",
    "boundary_contaminated",
    "bond_unresolved",
    "time_step_unresolved",
    "conservation_failed",
]


@dataclass(frozen=True)
class ConvergenceResult:
    accepted: bool
    status: ConvergenceStatus
    profile_error: float
    endpoint_profile_error: float
    width_error: float
    center_drift: float
    plateau_drift: float
    conservation_defect: float
    shape_factor_error: float
    moment_slope_error: float
    coarse_medium_profile_error: float
    numerical_floor: float
    boundary_clearance_in_widths: float
    common_shape: tuple[int, int]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _relative_l2(observed: Array, reference: Array) -> float:
    centered = reference - np.mean(reference, axis=1, keepdims=True)
    return float(
        np.linalg.norm(observed - reference)
        / max(float(np.linalg.norm(centered)), 1e-30)
    )


def _profile_shape_factor(x: Array, t: Array, u: Array) -> Array:
    try:
        diagnostics = front_linear_response_diagnostics(
            x,
            t,
            u,
            moment_smooth_window=min(11, t.size // 2 * 2 - 1),
        )
        return np.asarray(diagnostics["shape_factor"], dtype=float)
    except ValueError:
        return np.full(t.size, np.nan)


def _slope_w32(t: Array, width: Array) -> float:
    design = np.column_stack([np.ones(t.size), t])
    beta, *_ = np.linalg.lstsq(design, width**1.5, rcond=None)
    return float(beta[1])


def _pair_profile_error(candidate: Array, reference: Array) -> float:
    return _relative_l2(candidate, reference)


def audit_convergence(
    *,
    x: Array,
    t: Array,
    coarse: Array,
    medium: Array,
    fine: Array,
    profile_max: float,
    width_max: float,
    unresolved_kind: Literal[
        "bond_unresolved", "time_step_unresolved"
    ] = "bond_unresolved",
) -> ConvergenceResult:
    """Audit three resolutions already represented on one common grid.

    The confirmatory error is the medium-to-fine discrepancy.  The
    coarse-to-medium discrepancy is retained as a convergence-rate diagnostic.
    A front must remain at least four final widths from either boundary.
    """

    x = np.asarray(x, dtype=float)
    t = np.asarray(t, dtype=float)
    arrays = [
        np.asarray(value, dtype=float) for value in (coarse, medium, fine)
    ]
    for value in arrays:
        validate_grid_data(x, t, value)
    if profile_max <= 0 or width_max <= 0:
        raise ValueError("Convergence thresholds must be positive")
    if unresolved_kind not in ("bond_unresolved", "time_step_unresolved"):
        raise ValueError("Unsupported unresolved_kind")
    coarse, medium, fine = arrays

    # Signed-gradient moments preserve the exact conservation identities.
    # Clipping small negative discretization ripples creates a positive tail
    # bias and can turn an O(1e-3) profile error into an O(1e-2) width error.
    width_coarse = front_width_series(x, t, coarse)
    width_medium = front_width_series(x, t, medium)
    width_fine = front_width_series(x, t, fine)
    preliminary_fine_width = np.asarray(width_fine["width"], dtype=float)
    preliminary_center = np.asarray(width_fine["center"], dtype=float)
    clearance = np.minimum(
        preliminary_center - x[0], x[-1] - preliminary_center
    )
    boundary_clearance = float(
        np.min(clearance / np.maximum(preliminary_fine_width, 1e-30))
    )
    margin = 4.0 * float(np.max(preliminary_fine_width))
    comparison_mask = (x >= x[0] + margin) & (x <= x[-1] - margin)
    boundary_contaminated = (
        boundary_clearance < 4.0 or np.count_nonzero(comparison_mask) < 20
    )
    if boundary_contaminated:
        comparison_x = x
        comparison_coarse = coarse
        comparison_medium = medium
        comparison_fine = fine
    else:
        comparison_x = x[comparison_mask]
        comparison_coarse = coarse[:, comparison_mask]
        comparison_medium = medium[:, comparison_mask]
        comparison_fine = fine[:, comparison_mask]

    width_coarse = front_width_series(
        comparison_x, t, comparison_coarse
    )
    width_medium = front_width_series(
        comparison_x, t, comparison_medium
    )
    width_fine = front_width_series(comparison_x, t, comparison_fine)
    fine_width = np.asarray(width_fine["width"], dtype=float)
    medium_width = np.asarray(width_medium["width"], dtype=float)

    profile_error = _pair_profile_error(comparison_medium, comparison_fine)
    endpoint_profile_error = _relative_l2(
        comparison_medium[-1:], comparison_fine[-1:]
    )
    coarse_medium_profile_error = _pair_profile_error(
        comparison_coarse, comparison_medium
    )
    width_error = float(
        np.max(
            np.abs(medium_width - fine_width)
            / np.maximum(fine_width, 1e-30)
        )
    )
    center_drift = float(
        np.max(
            np.abs(
                np.asarray(width_medium["center"])
                - np.asarray(width_fine["center"])
            )
            / np.maximum(fine_width, 1e-30)
        )
    )

    edge_n = min(10, max(2, x.size // 20))
    plateau_medium = np.column_stack(
        [np.mean(medium[:, :edge_n], axis=1), np.mean(medium[:, -edge_n:], axis=1)]
    )
    plateau_fine = np.column_stack(
        [np.mean(fine[:, :edge_n], axis=1), np.mean(fine[:, -edge_n:], axis=1)]
    )
    jump = max(
        float(np.median(np.abs(plateau_fine[:, 1] - plateau_fine[:, 0]))),
        1e-30,
    )
    plateau_drift = float(np.max(np.abs(plateau_medium - plateau_fine)) / jump)

    fine_integral = np.trapezoid(fine, x=x, axis=1)
    conservation_defect = float(
        np.ptp(fine_integral)
        / max(jump * float(x[-1] - x[0]), 1e-30)
    )

    cf_medium = _profile_shape_factor(
        comparison_x, t, comparison_medium
    )
    cf_fine = _profile_shape_factor(comparison_x, t, comparison_fine)
    valid_cf = np.isfinite(cf_medium) & np.isfinite(cf_fine)
    if np.any(valid_cf):
        shape_factor_error = float(
            np.linalg.norm(cf_medium[valid_cf] - cf_fine[valid_cf])
            / max(float(np.linalg.norm(cf_fine[valid_cf])), 1e-30)
        )
    else:
        shape_factor_error = float("nan")

    slope_medium = _slope_w32(t, medium_width)
    slope_fine = _slope_w32(t, fine_width)
    moment_slope_error = abs(slope_medium - slope_fine) / max(
        abs(slope_fine), 1e-30
    )

    numerical_floor = float(
        max(
            profile_error,
            endpoint_profile_error,
            width_error,
            center_drift,
            plateau_drift,
            conservation_defect,
            moment_slope_error,
            0.0 if not np.isfinite(shape_factor_error) else shape_factor_error,
        )
    )
    if boundary_contaminated:
        status: ConvergenceStatus = "boundary_contaminated"
    elif conservation_defect > max(profile_max, width_max):
        status = "conservation_failed"
    elif profile_error > profile_max or width_error > width_max:
        status = unresolved_kind
    else:
        status = "accepted"

    return ConvergenceResult(
        accepted=status == "accepted",
        status=status,
        profile_error=profile_error,
        endpoint_profile_error=endpoint_profile_error,
        width_error=width_error,
        center_drift=center_drift,
        plateau_drift=plateau_drift,
        conservation_defect=conservation_defect,
        shape_factor_error=shape_factor_error,
        moment_slope_error=moment_slope_error,
        coarse_medium_profile_error=coarse_medium_profile_error,
        numerical_floor=numerical_floor,
        boundary_clearance_in_widths=boundary_clearance,
        common_shape=(int(t.size), int(comparison_x.size)),
    )


def _interpolate_to(
    dataset: ResearchDataset,
    target_t: Array,
    target_x: Array,
) -> Array:
    interpolator = RegularGridInterpolator(
        (dataset.t, dataset.x),
        dataset.u,
        method="linear",
        bounds_error=True,
    )
    tt, xx = np.meshgrid(target_t, target_x, indexing="ij")
    return np.asarray(
        interpolator(np.column_stack([tt.ravel(), xx.ravel()])).reshape(
            target_t.size, target_x.size
        )
    )


def audit_dataset_convergence(
    coarse: ResearchDataset,
    medium: ResearchDataset,
    fine: ResearchDataset,
    *,
    profile_max: float,
    width_max: float,
    unresolved_kind: Literal[
        "bond_unresolved", "time_step_unresolved"
    ] = "bond_unresolved",
) -> ConvergenceResult:
    """Interpolate coarser datasets onto the finest common grid and audit."""

    condition_ids = {coarse.condition_id, medium.condition_id, fine.condition_id}
    if len(condition_ids) != 1:
        raise ValueError("Convergence datasets must share condition_id")
    t_min = max(float(value.t[0]) for value in (coarse, medium, fine))
    t_max = min(float(value.t[-1]) for value in (coarse, medium, fine))
    x_min = max(float(value.x[0]) for value in (coarse, medium, fine))
    x_max = min(float(value.x[-1]) for value in (coarse, medium, fine))
    target_t_mask = (fine.t >= t_min) & (fine.t <= t_max)
    target_x_mask = (fine.x >= x_min) & (fine.x <= x_max)
    target_t = np.asarray(fine.t[target_t_mask], dtype=float)
    target_x = np.asarray(fine.x[target_x_mask], dtype=float)
    if target_t.size < 5 or target_x.size < 20:
        raise ValueError("Common convergence grid is too small")
    return audit_convergence(
        x=target_x,
        t=target_t,
        coarse=_interpolate_to(coarse, target_t, target_x),
        medium=_interpolate_to(medium, target_t, target_x),
        fine=np.asarray(fine.u[np.ix_(target_t_mask, target_x_mask)]),
        profile_max=profile_max,
        width_max=width_max,
        unresolved_kind=unresolved_kind,
    )
