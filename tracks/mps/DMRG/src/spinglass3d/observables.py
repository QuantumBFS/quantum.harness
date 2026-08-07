"""Whole-disorder spin-glass overlap observables."""

from __future__ import annotations

from dataclasses import dataclass
import math
from collections.abc import Sequence

import numpy as np

from .overlap import DisorderRecord


@dataclass(frozen=True)
class DisorderObservables:
    temperature: float
    length: int
    disorder_count: int
    mean_q2: float
    mean_q4: float
    binder: float
    chi_sg_0: float
    chi_sg_kmin_axes: tuple[float, float, float]
    chi_sg_kmin: float
    xi_l: float
    xi_l_over_l: float

    @property
    def chi_sg0(self) -> float:
        return self.chi_sg_0


def aggregate_disorder(records: Sequence[DisorderRecord]) -> DisorderObservables:
    """Average whole-J records, then form nonlinear dimensionless ratios."""
    items = tuple(records)
    if len(items) < 2:
        raise ValueError("at least two disorder records are required")
    if not all(isinstance(record, DisorderRecord) for record in items):
        raise TypeError("records must contain only DisorderRecord values")
    identifiers = [record.j_id for record in items]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("duplicate j_id would double-count one disorder sample")

    length = items[0].length
    temperature = items[0].temperature
    if any(record.length != length for record in items[1:]):
        raise ValueError("all disorder records must have the same length")
    if any(record.temperature != temperature for record in items[1:]):
        raise ValueError("all disorder records must have the same temperature")

    mean_q2 = float(np.mean([record.q2 for record in items], dtype=np.float64))
    mean_q4 = float(np.mean([record.q4 for record in items], dtype=np.float64))
    if not math.isfinite(mean_q2) or mean_q2 <= 0.0:
        raise ValueError("mean q2 must be positive and finite")
    axes = np.mean(
        np.asarray([record.qk2_axes for record in items], dtype=np.float64),
        axis=0,
    )
    mean_qk2 = float(np.mean(axes, dtype=np.float64))
    if not math.isfinite(mean_qk2) or mean_qk2 <= 0.0:
        raise ValueError("mean k_min overlap susceptibility must be positive")

    n_sites = length**3
    chi0 = n_sites * mean_q2
    chi_axes = n_sites * axes
    chik = n_sites * mean_qk2
    radicand = chi0 / chik - 1.0
    tolerance = 64.0 * np.finfo(np.float64).eps
    if radicand < -tolerance:
        raise ValueError("correlation-length radicand is negative")
    radicand = max(0.0, radicand)
    xi_l = math.sqrt(radicand) / (2.0 * math.sin(math.pi / length))
    binder = 0.5 * (3.0 - mean_q4 / mean_q2**2)
    values = (mean_q4, binder, chi0, chik, xi_l)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("aggregated observables must be finite")

    return DisorderObservables(
        temperature=temperature,
        length=length,
        disorder_count=len(items),
        mean_q2=mean_q2,
        mean_q4=mean_q4,
        binder=binder,
        chi_sg_0=chi0,
        chi_sg_kmin_axes=tuple(float(value) for value in chi_axes),
        chi_sg_kmin=chik,
        xi_l=xi_l,
        xi_l_over_l=xi_l / length,
    )
