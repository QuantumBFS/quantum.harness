#!/usr/bin/env python3
"""Stable II→TI cross-reweight diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Sequence


@dataclass(frozen=True)
class ReweightEstimate:
    energy: float
    ess: float
    maximum_normalized_weight: float
    top_one_percent_share: float
    diagnostic_only: bool


def _scaled_weights(log_values: Sequence[float]) -> list[float]:
    maximum = max(log_values)
    return [math.exp(value - maximum) for value in log_values]


def cross_reweight_ii_to_ti(
    rows: Sequence[Mapping[str, object]],
) -> ReweightEstimate:
    if not rows:
        raise ValueError("cross reweight requires paths")
    log_ratio = [
        float(row["logabs_d_ti"]) - float(row["logabs_d_alf_ii"])
        for row in rows
    ]
    signs = [int(row["sign_d_ti"]) for row in rows]
    if any(sign not in (-1, 1) for sign in signs):
        raise ValueError("cross reweight encountered zero/invalid sign")
    scaled = _scaled_weights(log_ratio)
    signed = [sign * weight for sign, weight in zip(signs, scaled)]
    denominator = math.fsum(signed)
    if abs(denominator) <= 1.0e-14 * math.fsum(scaled):
        raise ValueError("cross-reweight signed denominator vanishes")
    energy = math.fsum(
        weight * float(row["central_ti_etot"])
        for weight, row in zip(signed, rows)
    ) / denominator
    total = math.fsum(scaled)
    normalized = sorted((value / total for value in scaled), reverse=True)
    ess = total * total / math.fsum(value * value for value in scaled)
    count = max(1, math.ceil(0.01 * len(normalized)))
    top_share = math.fsum(normalized[:count])
    return ReweightEstimate(
        energy=energy,
        ess=ess,
        maximum_normalized_weight=normalized[0],
        top_one_percent_share=top_share,
        diagnostic_only=ess < max(20.0, 0.05 * len(rows)),
    )
