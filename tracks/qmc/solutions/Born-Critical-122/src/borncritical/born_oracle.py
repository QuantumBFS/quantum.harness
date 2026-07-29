"""Exact Born-distribution oracle for tiny self-dual lattices.

This module deliberately scales exponentially and is restricted by an explicit
``max_variables`` guard.  Its purpose is to validate the production
conditional Gaussian sampler, not to produce physics data.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Protocol

import numpy as np

from .exact import BondFields, direct_amplitude


class RandomSource(Protocol):
    def random(self) -> float: ...


@dataclass(frozen=True)
class BornOutcome:
    bits: tuple[int, ...]
    fields: BondFields
    log_weight: float
    probability: float


def vacuum_wilson_loop(fields: BondFields) -> int:
    """Return the reference-row ``m`` Wilson loop, ``prod_x s[x, y=0]``."""

    return int(np.prod(fields.s_horizontal[0], dtype=np.int64))


def _bits_to_signs(bits: tuple[int, ...]) -> np.ndarray:
    return np.asarray([1 if bit == 0 else -1 for bit in bits], dtype=np.int8)


def _fields_from_bits(nx: int, ny: int, bits: tuple[int, ...]) -> BondFields:
    horizontal_count = nx * ny
    vertical_count = nx * (ny - 1)
    edge_count = horizontal_count + vertical_count
    values = _bits_to_signs(bits)
    s_values = values[:edge_count]
    t_values = values[edge_count:]
    return BondFields(
        s_horizontal=s_values[:horizontal_count].reshape(ny, nx),
        s_vertical=s_values[horizontal_count:].reshape(ny - 1, nx),
        t_horizontal=t_values[:horizontal_count].reshape(ny, nx),
        t_vertical=t_values[horizontal_count:].reshape(ny - 1, nx),
    )


def enumerate_born_distribution(
    nx: int,
    ny: int,
    coupling: float,
    *,
    vacuum_only: bool = True,
    max_variables: int = 20,
) -> tuple[BornOutcome, ...]:
    """Enumerate ``P(s,t) proportional to abs(Z(s,t))**2`` exactly."""

    if nx < 2 or ny < 1:
        raise ValueError("Born oracle requires nx >= 2 and ny >= 1")
    edge_count = nx * ny + nx * (ny - 1)
    variable_count = 2 * edge_count
    if variable_count > max_variables:
        raise ValueError(
            f"{variable_count} binary outcome variables exceeds max_variables="
            f"{max_variables}"
        )

    raw: list[tuple[tuple[int, ...], BondFields, float]] = []
    for encoded in range(1 << variable_count):
        bits = tuple((encoded >> position) & 1 for position in range(variable_count))
        fields = _fields_from_bits(nx, ny, bits)
        if vacuum_only and vacuum_wilson_loop(fields) != 1:
            continue
        sign, log_abs_amplitude = direct_amplitude(fields, coupling)
        log_weight = -math.inf if sign == 0 else 2.0 * log_abs_amplitude
        raw.append((bits, fields, log_weight))

    finite_weights = [entry[2] for entry in raw if math.isfinite(entry[2])]
    if not finite_weights:
        raise RuntimeError("all exact Born weights vanished")
    offset = max(finite_weights)
    scaled = [
        0.0 if not math.isfinite(entry[2]) else math.exp(entry[2] - offset)
        for entry in raw
    ]
    normalization = math.fsum(scaled)
    if not math.isfinite(normalization) or normalization <= 0.0:
        raise RuntimeError("invalid exact Born normalization")

    return tuple(
        BornOutcome(
            bits=bits,
            fields=fields,
            log_weight=log_weight,
            probability=weight / normalization,
        )
        for (bits, fields, log_weight), weight in zip(raw, scaled, strict=True)
    )


def sample_by_exact_conditionals(
    outcomes: tuple[BornOutcome, ...], rng: RandomSource
) -> tuple[BornOutcome, float]:
    """Sample one exact outcome bit-by-bit and return its accumulated log P."""

    if not outcomes:
        raise ValueError("outcomes must not be empty")
    bit_count = len(outcomes[0].bits)
    if any(len(outcome.bits) != bit_count for outcome in outcomes):
        raise ValueError("all outcomes must use the same bit encoding")
    if not math.isclose(
        math.fsum(outcome.probability for outcome in outcomes),
        1.0,
        rel_tol=0.0,
        abs_tol=2e-14,
    ):
        raise ValueError("outcome probabilities must be normalized")

    candidates = list(outcomes)
    log_probability = 0.0
    for position in range(bit_count):
        weight_zero = math.fsum(
            item.probability for item in candidates if item.bits[position] == 0
        )
        weight_one = math.fsum(
            item.probability for item in candidates if item.bits[position] == 1
        )
        total = weight_zero + weight_one
        if total <= 0.0:
            raise RuntimeError("conditional probability has zero support")
        probability_zero = weight_zero / total
        chosen = 0 if float(rng.random()) < probability_zero else 1
        chosen_probability = probability_zero if chosen == 0 else 1.0 - probability_zero
        if chosen_probability <= 0.0:
            chosen = 1 - chosen
            chosen_probability = 1.0
        log_probability += math.log(chosen_probability)
        candidates = [item for item in candidates if item.bits[position] == chosen]

    if len(candidates) != 1:
        raise RuntimeError("bit encoding did not identify a unique Born outcome")
    return candidates[0], log_probability
