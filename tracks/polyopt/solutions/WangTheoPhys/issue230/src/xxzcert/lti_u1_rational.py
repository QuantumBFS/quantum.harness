"""Exact dual witnesses for the U(1)-blocked LTI hierarchy."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

import numpy as np

from .lti_u1 import U1LTICandidate, sector_basis
from .rational import (
    RationalMatrix,
    exact_positive_definite_ldl,
    rigorous_positive_definite_congruence,
    xxz_sector_matrix_fraction,
)


@dataclass(frozen=True)
class U1LTIDualWitness:
    sites: int
    denominator: int
    y_numerator: int
    sector_matrix_numerators: tuple[tuple[int, ...], ...]

    @property
    def y(self) -> Fraction:
        return Fraction(self.y_numerator, self.denominator)

    @property
    def energy_density_lower(self) -> Fraction:
        return -self.y

    def sector_matrices(self) -> list[RationalMatrix]:
        if len(self.sector_matrix_numerators) != self.sites:
            raise ValueError("U(1) dual sector count mismatch")
        matrices = []
        for ones, payload in enumerate(self.sector_matrix_numerators):
            size = len(sector_basis(self.sites - 1, ones))
            if len(payload) != size * size:
                raise ValueError("U(1) dual sector dimension mismatch")
            matrices.append(
                [
                    [
                        Fraction(
                            payload[row * size + column], self.denominator
                        )
                        for column in range(size)
                    ]
                    for row in range(size)
                ]
            )
        return matrices


def _local_objective_sector(
    delta: Fraction, sites: int, ones: int
) -> RationalMatrix:
    basis = sector_basis(sites, ones)
    positions = {state: index for index, state in enumerate(basis)}
    matrix = [
        [Fraction(0) for _ in range(len(basis))] for _ in range(len(basis))
    ]
    for row, state in enumerate(basis):
        first = (state >> (sites - 1)) & 1
        second = (state >> (sites - 2)) & 1
        matrix[row][row] += delta / 4 if first == second else -delta / 4
        if first != second:
            flipped = state ^ (1 << (sites - 1))
            flipped ^= 1 << (sites - 2)
            matrix[row][positions[flipped]] += Fraction(1, 2)
    return matrix


def u1_lti_dual_slacks(
    delta: Fraction, witness: U1LTIDualWitness
) -> tuple[RationalMatrix, ...]:
    duals = witness.sector_matrices()
    slacks: list[RationalMatrix] = []
    for global_ones in range(witness.sites + 1):
        global_basis = sector_basis(witness.sites, global_ones)
        global_positions = {
            state: index for index, state in enumerate(global_basis)
        }
        size = len(global_basis)
        slack = _local_objective_sector(
            delta, witness.sites, global_ones
        )
        for row in range(size):
            slack[row][row] += witness.y
        for removed_bit in (0, 1):
            reduced_ones = global_ones - removed_bit
            if reduced_ones < 0 or reduced_ones >= witness.sites:
                continue
            dual = duals[reduced_ones]
            reduced_basis = sector_basis(witness.sites - 1, reduced_ones)
            first_positions = [
                global_positions[
                    (removed_bit << (witness.sites - 1)) | state
                ]
                for state in reduced_basis
            ]
            last_positions = [
                global_positions[(state << 1) | removed_bit]
                for state in reduced_basis
            ]
            for row, values in enumerate(dual):
                first_row = first_positions[row]
                last_row = last_positions[row]
                for column, value in enumerate(values):
                    if value:
                        slack[first_row][first_positions[column]] += value
                        slack[last_row][last_positions[column]] -= value
        slacks.append(slack)
    return tuple(slacks)


def verify_u1_lti_dual_witness(
    delta: Fraction, witness: U1LTIDualWitness
) -> bool:
    for slack in u1_lti_dual_slacks(delta, witness):
        if len(slack) <= 32:
            positive = exact_positive_definite_ldl(slack)[0]
        else:
            positive = rigorous_positive_definite_congruence(slack)
        if not positive:
            return False
    return True


def make_u1_lti_dual_witness(
    delta: Fraction,
    candidate: U1LTICandidate,
    scale: int = 10**8,
    safety_steps: int = 2,
) -> U1LTIDualWitness:
    """Rationalize all sector multipliers and repair them with one trace shift."""
    payloads: list[tuple[int, ...]] = []
    for dual in candidate.dual_sectors:
        symmetric = (np.asarray(dual) + np.asarray(dual).T) / 2
        payloads.append(
            tuple(int(round(float(value) * scale)) for value in symmetric.reshape(-1))
        )
    base_y = Fraction(int(round(candidate.dual_trace * scale)), scale)

    def witness_with(y: Fraction) -> U1LTIDualWitness:
        return U1LTIDualWitness(
            sites=candidate.level,
            denominator=scale,
            y_numerator=int(y * scale),
            sector_matrix_numerators=tuple(payloads),
        )

    base = witness_with(base_y)
    minimum = min(
        float(
            np.linalg.eigvalsh(
                (np.array(slack, dtype=float) + np.array(slack, dtype=float).T)
                / 2
            )[0]
        )
        for slack in u1_lti_dual_slacks(delta, base)
    )
    steps = max(1, int(np.ceil(max(0.0, -minimum) * scale)) + safety_steps)
    while True:
        repaired = witness_with(base_y + Fraction(steps, scale))
        if verify_u1_lti_dual_witness(delta, repaired):
            return repaired
        steps *= 2
