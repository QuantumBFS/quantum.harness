from dataclasses import asdict, dataclass

import numpy as np


@dataclass(frozen=True)
class FreeEnergyFit:
    minimum_width: int
    widths: list[int]
    phi_infinity: float
    central_charge: float
    l4_amplitude: float
    residual_rms: float

    def to_dict(self) -> dict:
        return asdict(self)


def fit_free_energy(
    widths: np.ndarray, phi: np.ndarray, minimum_width: int
) -> FreeEnergyFit:
    widths = np.asarray(widths, dtype=float)
    phi = np.asarray(phi, dtype=float)
    if widths.ndim != 1 or phi.ndim != 1 or widths.shape != phi.shape:
        raise ValueError("widths and phi must be same-length one-dimensional arrays")
    if not np.all(np.isfinite(widths)) or not np.all(np.isfinite(phi)):
        raise ValueError("fit inputs must be finite")

    selected = widths >= minimum_width
    selected_widths = widths[selected]
    selected_phi = phi[selected]
    if len(selected_widths) < 3:
        raise ValueError("finite-size fit requires at least three widths")
    if len(np.unique(selected_widths)) != len(selected_widths):
        raise ValueError("finite-size fit widths must be distinct")

    design = design_matrix(selected_widths)
    coefficients, _, rank, _ = np.linalg.lstsq(design, selected_phi, rcond=None)
    if rank != 3:
        raise ValueError("finite-size fit design matrix is rank deficient")
    residual = selected_phi - design @ coefficients
    return FreeEnergyFit(
        minimum_width=int(minimum_width),
        widths=[int(width) for width in selected_widths],
        phi_infinity=float(coefficients[0]),
        central_charge=float(coefficients[1]),
        l4_amplitude=float(coefficients[2]),
        residual_rms=float(np.sqrt(np.mean(residual**2))),
    )


def design_matrix(widths: np.ndarray) -> np.ndarray:
    widths = np.asarray(widths, dtype=float)
    return np.column_stack(
        [
            np.ones_like(widths),
            np.pi / (6.0 * widths**2),
            1.0 / widths**4,
        ]
    )


def evaluate_fit(fit: FreeEnergyFit, widths: np.ndarray) -> np.ndarray:
    widths = np.asarray(widths, dtype=float)
    return (
        fit.phi_infinity
        + np.pi * fit.central_charge / (6.0 * widths**2)
        + fit.l4_amplitude / widths**4
    )
