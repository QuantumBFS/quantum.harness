"""Observable residues and tracking for Floquet transfer poles."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import linear_sum_assignment


@dataclass(frozen=True)
class TransferPole:
    eigenvalue: complex
    decay_rate: float
    quasifrequency: float
    eigenpair_residual: float


@dataclass(frozen=True)
class PoleResidue:
    pole: TransferPole
    residue: complex


@dataclass(frozen=True)
class PoleFit:
    residues: tuple[PoleResidue, ...]
    reconstruction: NDArray[np.complex128]
    stroboscopic_delays: NDArray[np.float64]
    reconstruction_residual: float
    condition_number: float


@dataclass(frozen=True)
class PoleMatch:
    previous_index: int
    current_index: int
    distance: float
    ambiguous: bool


def transfer_poles(
    eigenvalues: NDArray[np.complex128],
    eigenpair_residuals: NDArray[np.float64],
    period: float,
    *,
    steady_tolerance: float = 5e-3,
) -> tuple[TransferPole, ...]:
    """Remove the resolved steady pole and convert the rest to rates."""
    values = np.asarray(eigenvalues, dtype=np.complex128)
    residuals = np.asarray(eigenpair_residuals, dtype=float)
    if values.ndim != 1 or residuals.ndim != 1 or values.shape != residuals.shape:
        raise ValueError("transfer eigenvalues and residuals must be equal vectors")
    if values.size < 2:
        raise ValueError("at least one steady and one decaying pole are required")
    if period <= 0 or steady_tolerance <= 0:
        raise ValueError("period and steady_tolerance must be positive")
    if not np.all(np.isfinite(values)) or not np.all(np.isfinite(residuals)):
        raise ValueError("transfer pole data must be finite")
    if np.any(residuals < 0):
        raise ValueError("eigenpair residuals must be nonnegative")

    steady = int(np.argmin(abs(values - 1)))
    if abs(values[steady] - 1) > steady_tolerance:
        raise ValueError("transfer spectrum has no resolved steady pole")

    records: list[TransferPole] = []
    for index, (value, residual) in enumerate(
        zip(values, residuals, strict=True)
    ):
        if index == steady:
            continue
        magnitude = float(abs(value))
        if magnitude <= np.finfo(float).tiny:
            raise ValueError("zero transfer eigenvalues cannot define finite rates")
        records.append(
            TransferPole(
                eigenvalue=complex(value),
                decay_rate=float(-np.log(magnitude) / period),
                quasifrequency=float(np.angle(value) / period),
                eigenpair_residual=float(residual),
            )
        )
    return tuple(
        sorted(records, key=lambda item: abs(item.eigenvalue), reverse=True)
    )


def fit_pole_residues(
    poles: tuple[TransferPole, ...],
    delays: NDArray[np.float64],
    connected: NDArray[np.complex128],
    period: float,
    max_modes: int,
) -> PoleFit:
    """Fit transfer-pole residues to stroboscopic connected correlations."""
    delay_values = np.asarray(delays, dtype=float)
    data_values = np.asarray(connected, dtype=np.complex128)
    if (
        delay_values.ndim != 1
        or data_values.ndim != 1
        or delay_values.shape != data_values.shape
    ):
        raise ValueError("delays and connected correlation must be equal vectors")
    if period <= 0:
        raise ValueError("period must be positive")
    if isinstance(max_modes, bool) or max_modes < 1 or max_modes > len(poles):
        raise ValueError("max_modes must select one or more available poles")
    if not np.all(np.isfinite(delay_values)) or not np.all(np.isfinite(data_values)):
        raise ValueError("correlation fit data must be finite")
    if np.any(delay_values < 0):
        raise ValueError("delays must be nonnegative")

    scaled = delay_values / period
    orders = np.rint(scaled).astype(int)
    mask = np.isclose(scaled, orders, rtol=0.0, atol=1e-8)
    stroboscopic_delays = delay_values[mask]
    stroboscopic_orders = orders[mask]
    stroboscopic_data = data_values[mask]
    if len(stroboscopic_data) <= max_modes:
        raise ValueError(
            "the pole fit requires more stroboscopic samples than modes"
        )

    selected = poles[:max_modes]
    design = np.column_stack(
        [item.eigenvalue**stroboscopic_orders for item in selected]
    ).astype(np.complex128, copy=False)
    coefficients, _, _, _ = np.linalg.lstsq(
        design,
        stroboscopic_data,
        rcond=None,
    )
    reconstruction = np.asarray(design @ coefficients, dtype=np.complex128)
    denominator = float(np.sum(abs(stroboscopic_data))) + 1e-15
    reconstruction_residual = float(
        np.sum(abs(reconstruction - stroboscopic_data)) / denominator
    )
    return PoleFit(
        residues=tuple(
            PoleResidue(pole=pole, residue=complex(residue))
            for pole, residue in zip(selected, coefficients, strict=True)
        ),
        reconstruction=reconstruction,
        stroboscopic_delays=np.asarray(stroboscopic_delays, dtype=float),
        reconstruction_residual=reconstruction_residual,
        condition_number=float(np.linalg.cond(design)),
    )


def match_transfer_poles(
    previous: tuple[TransferPole, ...],
    current: tuple[TransferPole, ...],
    *,
    ambiguity_tolerance: float = 1e-6,
) -> tuple[PoleMatch, ...]:
    """Match two transfer spectra by minimum total complex-plane distance."""
    if ambiguity_tolerance < 0:
        raise ValueError("ambiguity_tolerance must be nonnegative")
    if not previous or not current:
        return ()
    cost = np.asarray(
        [
            [
                abs(previous_pole.eigenvalue - current_pole.eigenvalue)
                for current_pole in current
            ]
            for previous_pole in previous
        ],
        dtype=float,
    )
    rows, columns = linear_sum_assignment(cost)
    records: list[PoleMatch] = []
    for row, column in zip(rows, columns, strict=True):
        ordered = np.sort(cost[row])
        ambiguous = bool(
            len(ordered) > 1
            and ordered[1] - ordered[0] <= ambiguity_tolerance
        )
        records.append(
            PoleMatch(
                previous_index=int(row),
                current_index=int(column),
                distance=float(cost[row, column]),
                ambiguous=ambiguous,
            )
        )
    return tuple(sorted(records, key=lambda item: item.previous_index))
