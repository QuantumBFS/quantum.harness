from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from itertools import product
from math import factorial
from typing import Iterable, Sequence

import mpmath as mp
import numpy as np

from .algebra import PauliSum, commutator
from .local_commutators import (
    LocalDensityEvaluator,
    SymplecticDyadicLocalDensityEvaluator,
)


@dataclass(frozen=True)
class ScalarStage:
    fragment_index: int
    coefficient: mp.mpf


def _second_order_scalar_stages(
    n_fragments: int,
    scale: mp.mpf,
) -> list[ScalarStage]:
    stages = [
        ScalarStage(index, scale / 2)
        for index in range(n_fragments - 1)
    ]
    stages.append(ScalarStage(n_fragments - 1, scale))
    stages.extend(
        ScalarStage(index, scale / 2)
        for index in reversed(range(n_fragments - 1))
    )
    return stages


def merge_scalar_stages(stages: Sequence[ScalarStage]) -> tuple[ScalarStage, ...]:
    merged: list[ScalarStage] = []
    for stage in stages:
        if merged and merged[-1].fragment_index == stage.fragment_index:
            previous = merged.pop()
            coefficient = previous.coefficient + stage.coefficient
            if coefficient:
                merged.append(ScalarStage(stage.fragment_index, coefficient))
        else:
            merged.append(stage)
    return tuple(merged)


def fourth_order_suzuki_stages(n_fragments: int) -> tuple[ScalarStage, ...]:
    """Five-copy Suzuki fractal S4 built from the symmetric S2 kernel."""

    mp.mp.dps = max(mp.mp.dps, 80)
    u = 1 / (4 - mp.root(4, 3))
    scales = (u, u, 1 - 4 * u, u, u)
    stages: list[ScalarStage] = []
    for scale in scales:
        stages.extend(_second_order_scalar_stages(n_fragments, scale))
    return merge_scalar_stages(stages)


def fourth_order_triple_jump_stages(n_fragments: int) -> tuple[ScalarStage, ...]:
    """Three-copy fourth-order symmetric composition of S2."""

    mp.mp.dps = max(mp.mp.dps, 80)
    a = 1 / (2 - mp.root(2, 3))
    b = 1 - 2 * a
    stages: list[ScalarStage] = []
    for scale in (a, b, a):
        stages.extend(_second_order_scalar_stages(n_fragments, scale))
    return merge_scalar_stages(stages)


def weak_compositions(total: int, length: int) -> Iterable[tuple[int, ...]]:
    if length == 1:
        yield (total,)
        return
    for first in range(total + 1):
        for tail in weak_compositions(total - first, length - 1):
            yield (first,) + tail


def _multinomial(total: int, composition: Sequence[int]) -> int:
    result = factorial(total)
    for value in composition:
        result //= factorial(value)
    return result


def higher_order_triangle_weights(
    stages_left_to_right: Sequence[ScalarStage],
    order: int,
    center: int | None = None,
) -> dict[tuple[int, ...], mp.mpf]:
    """Aggregate Schubert--Mendl theorem weights by base-fragment sequence.

    The returned key is ``(outermost, ..., innermost, base)``. The norm of
    the corresponding pure nested commutator is multiplied by the positive
    weight. Expanding ``B_j`` by a triangle inequality keeps this routine
    conservative and easy to verify.
    """

    # Their A_1 is the rightmost exponential.
    stages = tuple(reversed(stages_left_to_right))
    count = len(stages)
    s = center if center is not None else (count + 1) // 2
    if not 1 <= s <= count:
        raise ValueError("center must use one-based stage indexing")
    weights: dict[tuple[int, ...], mp.mpf] = {}

    def add_range(j: int, indices: tuple[int, ...], composition: tuple[int, ...]) -> None:
        outer: list[int] = []
        coefficient = mp.mpf(_multinomial(order, composition))
        for stage_index, power in zip(indices, composition):
            coefficient *= abs(stages[stage_index - 1].coefficient) ** power
        # ad operators appear in the theorem in the same order as indices.
        for stage_index, power in zip(indices, composition):
            outer.extend([stages[stage_index - 1].fragment_index] * power)
        for base_index in range(1, j):
            base_stage = stages[base_index - 1]
            key = tuple(outer) + (base_stage.fragment_index,)
            weights[key] = weights.get(key, mp.mpf("0")) + (
                coefficient * abs(base_stage.coefficient)
            )

    for j in range(2, s + 1):
        indices = tuple(range(s, j - 1, -1))
        # q_j is the final entry because indices descend s,...,j.
        for composition in weak_compositions(order, len(indices)):
            if composition[-1] == 0:
                continue
            add_range(j, indices, composition)

    for j in range(s + 1, count + 1):
        indices = tuple(range(s + 1, j + 1))
        # q_j is the final entry because indices ascend s+1,...,j.
        for composition in weak_compositions(order, len(indices)):
            if composition[-1] == 0:
                continue
            add_range(j, indices, composition)
    return weights


def nested_commutator(
    fragments: Sequence[PauliSum],
    key: tuple[int, ...],
    cache: dict[tuple[int, ...], PauliSum] | None = None,
) -> PauliSum:
    """Evaluate a key ``(outermost,...,innermost,base)`` exactly."""

    memo = cache if cache is not None else {}
    if key in memo:
        return memo[key]
    if len(key) == 1:
        result = fragments[key[0]]
    else:
        result = commutator(
            fragments[key[0]],
            nested_commutator(fragments, key[1:], memo),
        )
    memo[key] = result
    return result


def fourth_order_pauli_l1_constant(
    fragments: Sequence[PauliSum],
) -> tuple[mp.mpf, dict[tuple[int, ...], mp.mpf]]:
    stages = fourth_order_suzuki_stages(len(fragments))
    weights = higher_order_triangle_weights(stages, order=4)
    cache: dict[tuple[int, ...], PauliSum] = {}
    total = mp.mpf("0")
    for key, weight in weights.items():
        operator = nested_commutator(fragments, key, cache)
        total += weight * operator.pauli_l1()
    return total / factorial(5), weights


def fourth_order_local_pauli_l1_density(
    n_fragments: int = 4,
) -> tuple[mp.mpf, dict[tuple[int, ...], mp.mpf]]:
    """Uniform 2x2-cell fourth-order bound for the four matching model."""

    if n_fragments != 4:
        raise ValueError("local matching density currently supports four fragments")
    stages = fourth_order_suzuki_stages(n_fragments)
    weights = higher_order_triangle_weights(stages, order=4)
    evaluator = LocalDensityEvaluator()
    total = mp.mpf("0")
    for key, weight in weights.items():
        if key[-2] == key[-1]:
            continue
        norm = evaluator.pauli_l1_density(key)
        total += weight * int(norm.numerator) / int(
            norm.denominator
        )
    return total / factorial(5), weights


def local_pauli_l1_constant_from_norms(
    stages: Sequence[ScalarStage],
    norm_density: dict[tuple[int, ...], Fraction],
    *,
    order: int = 4,
) -> mp.mpf:
    weights = higher_order_triangle_weights(stages, order)
    total = mp.mpf("0")
    for key, weight in weights.items():
        norm = norm_density.get(key, Fraction())
        total += weight * int(norm.numerator) / int(norm.denominator)
    return total / factorial(order + 1)


def higher_order_combined_local_l1_density(
    stages_left_to_right: Sequence[ScalarStage],
    *,
    order: int = 4,
    center: int | None = None,
) -> mp.mpf:
    """Evaluate the theorem while retaining cancellations inside each B_j."""

    stages = tuple(reversed(stages_left_to_right))
    count = len(stages)
    s = center if center is not None else (count + 1) // 2
    evaluator = LocalDensityEvaluator()
    total = mp.mpf("0")

    def evaluate_term(
        j: int,
        indices: tuple[int, ...],
        composition: tuple[int, ...],
    ) -> mp.mpf:
        outer: list[int] = []
        scalar = mp.mpf(_multinomial(order, composition))
        for stage_index, power in zip(indices, composition):
            stage = stages[stage_index - 1]
            scalar *= stage.coefficient**power
            outer.extend([stage.fragment_index] * power)
        base_coefficients = [mp.mpf("0") for _ in range(4)]
        for base_index in range(1, j):
            base = stages[base_index - 1]
            base_coefficients[base.fragment_index] += base.coefficient
        pauli_coefficients: dict[object, mp.mpf] = {}
        for fragment_index, base_coefficient in enumerate(base_coefficients):
            if not base_coefficient:
                continue
            operator = evaluator.evaluate(tuple(outer) + (fragment_index,))
            for pauli, coefficient in operator.terms.items():
                if coefficient.imag:
                    raise ArithmeticError("degree-five commutator should be Hermitian")
                pauli_coefficients[pauli] = pauli_coefficients.get(
                    pauli, mp.mpf("0")
                ) + base_coefficient * mp.mpf(coefficient.real.numerator) / mp.mpf(
                    coefficient.real.denominator
                )
        return abs(scalar) * sum(abs(value) for value in pauli_coefficients.values())

    for j in range(2, s + 1):
        indices = tuple(range(s, j - 1, -1))
        for composition in weak_compositions(order, len(indices)):
            if composition[-1]:
                total += evaluate_term(j, indices, composition)
    for j in range(s + 1, count + 1):
        indices = tuple(range(s + 1, j + 1))
        for composition in weak_compositions(order, len(indices)):
            if composition[-1]:
                total += evaluate_term(j, indices, composition)
    return total / factorial(order + 1)


def higher_order_combined_local_l1_density_fast(
    stages_left_to_right: Sequence[ScalarStage],
    *,
    order: int = 4,
    center: int | None = None,
) -> float:
    """Vectorized discovery evaluation retaining cancellations inside B_j."""

    stages = tuple(reversed(stages_left_to_right))
    count = len(stages)
    s = center if center is not None else (count + 1) // 2
    grouped_terms: dict[
        tuple[int, ...], list[tuple[float, tuple[float, ...]]]
    ] = {}

    def collect(
        j: int,
        indices: tuple[int, ...],
        composition: tuple[int, ...],
    ) -> None:
        outer: list[int] = []
        scalar = float(_multinomial(order, composition))
        for stage_index, power in zip(indices, composition):
            stage = stages[stage_index - 1]
            scalar *= float(stage.coefficient) ** power
            outer.extend([stage.fragment_index] * power)
        base = [0.0] * 4
        for base_index in range(1, j):
            stage = stages[base_index - 1]
            base[stage.fragment_index] += float(stage.coefficient)
        grouped_terms.setdefault(tuple(outer), []).append(
            (abs(scalar), tuple(base))
        )

    for j in range(2, s + 1):
        indices = tuple(range(s, j - 1, -1))
        for composition in weak_compositions(order, len(indices)):
            if composition[-1]:
                collect(j, indices, composition)
    for j in range(s + 1, count + 1):
        indices = tuple(range(s + 1, j + 1))
        for composition in weak_compositions(order, len(indices)):
            if composition[-1]:
                collect(j, indices, composition)

    evaluator = LocalDensityEvaluator()
    total = 0.0
    for outer, terms in grouped_terms.items():
        operators = [evaluator.evaluate(outer + (base,)) for base in range(4)]
        paulis = sorted(set().union(*(set(operator.terms) for operator in operators)))
        matrix = np.zeros((len(paulis), 4), dtype=np.float64)
        for column, operator in enumerate(operators):
            for row, pauli in enumerate(paulis):
                coefficient = operator.terms.get(pauli)
                if coefficient is not None:
                    matrix[row, column] = float(coefficient.real)
        scalars = np.asarray([term[0] for term in terms], dtype=np.float64)
        base_matrix = np.asarray([term[1] for term in terms], dtype=np.float64).T
        norms = np.abs(matrix @ base_matrix).sum(axis=0)
        total += float(scalars @ norms)
    return total / factorial(order + 1)


def higher_order_combined_local_l1_density_symplectic(
    stages_left_to_right: Sequence[ScalarStage],
    *,
    order: int = 4,
    center: int | None = None,
    evaluator: SymplecticDyadicLocalDensityEvaluator | None = None,
) -> float:
    """Fast discovery bound retaining exact Pauli cancellation inside ``B_j``.

    Local nested commutators are evaluated exactly as integer coefficient
    vectors. Formula coefficients are converted to double precision only
    at the final small linear combinations, so this is a discovery value,
    not yet an outward-rounded certificate.
    """

    stages = tuple(reversed(stages_left_to_right))
    count = len(stages)
    s = center if center is not None else (count + 1) // 2
    grouped_terms: dict[
        tuple[int, ...], list[tuple[float, tuple[float, ...]]]
    ] = {}

    def collect(
        j: int,
        indices: tuple[int, ...],
        composition: tuple[int, ...],
    ) -> None:
        outer: list[int] = []
        scalar = float(_multinomial(order, composition))
        for stage_index, power in zip(indices, composition):
            stage = stages[stage_index - 1]
            scalar *= float(stage.coefficient) ** power
            outer.extend([stage.fragment_index] * power)
        base = [0.0] * 4
        for base_index in range(1, j):
            stage = stages[base_index - 1]
            base[stage.fragment_index] += float(stage.coefficient)
        grouped_terms.setdefault(tuple(outer), []).append(
            (abs(scalar), tuple(base))
        )

    for j in range(2, s + 1):
        indices = tuple(range(s, j - 1, -1))
        for composition in weak_compositions(order, len(indices)):
            if composition[-1]:
                collect(j, indices, composition)
    for j in range(s + 1, count + 1):
        indices = tuple(range(s + 1, j + 1))
        for composition in weak_compositions(order, len(indices)):
            if composition[-1]:
                collect(j, indices, composition)

    # Combining different base fragments requires one coordinate-to-bit
    # registry; otherwise equal physical Pauli strings can receive unrelated
    # bit labels and their cancellations would be destroyed.
    local = evaluator or SymplecticDyadicLocalDensityEvaluator(
        shared_coordinates=True
    )
    denominator = float(1 << (order + 2))
    total = 0.0
    for outer, terms in grouped_terms.items():
        operators = [local.evaluate(outer + (base,)) for base in range(4)]
        paulis = set().union(*(operator.keys() for operator in operators))
        row_for_pauli = {pauli: row for row, pauli in enumerate(paulis)}
        matrix = np.zeros((len(paulis), 4), dtype=np.int32)
        for column, operator in enumerate(operators):
            for pauli, coefficient in operator.items():
                matrix[row_for_pauli[pauli], column] = coefficient
        scalars = np.asarray([term[0] for term in terms], dtype=np.float64)
        base_matrix = np.asarray([term[1] for term in terms], dtype=np.float64).T
        norms = np.abs(matrix @ base_matrix).sum(axis=0) / denominator
        total += float(scalars @ norms)
    return total / factorial(order + 1)


def _pairwise_anticommuting_float_bound(
    paulis: Sequence[tuple[int, int]],
    coefficients: np.ndarray,
) -> float:
    """Greedily pair anticommuting Paulis and apply Euclidean pair norms."""

    order = np.argsort(-np.abs(coefficients), kind="stable")
    used = np.zeros(len(paulis), dtype=np.bool_)
    total = 0.0
    for position, index_value in enumerate(order):
        index = int(index_value)
        if used[index] or coefficients[index] == 0:
            continue
        used[index] = True
        left_x, left_z = paulis[index]
        partner: int | None = None
        for candidate_value in order[position + 1 :]:
            candidate = int(candidate_value)
            if used[candidate] or coefficients[candidate] == 0:
                continue
            right_x, right_z = paulis[candidate]
            parity = (
                (left_x & right_z).bit_count()
                + (left_z & right_x).bit_count()
            ) & 1
            if parity:
                partner = candidate
                break
        if partner is None:
            total += abs(float(coefficients[index]))
        else:
            used[partner] = True
            total += float(
                np.hypot(coefficients[index], coefficients[partner])
            )
    return total


def higher_order_combined_local_pair_density_symplectic(
    stages_left_to_right: Sequence[ScalarStage],
    *,
    order: int = 4,
    center: int | None = None,
    evaluator: SymplecticDyadicLocalDensityEvaluator | None = None,
) -> float:
    """Discovery bound with ``B_j`` cancellation and anticommuting pairs."""

    stages = tuple(reversed(stages_left_to_right))
    count = len(stages)
    s = center if center is not None else (count + 1) // 2
    grouped: dict[
        tuple[int, ...],
        dict[tuple[float, ...], float],
    ] = {}

    def collect(
        j: int,
        indices: tuple[int, ...],
        composition: tuple[int, ...],
    ) -> None:
        outer: list[int] = []
        scalar = float(_multinomial(order, composition))
        for stage_index, power in zip(indices, composition):
            stage = stages[stage_index - 1]
            scalar *= float(stage.coefficient) ** power
            outer.extend([stage.fragment_index] * power)
        base = [0.0] * 4
        for base_index in range(1, j):
            stage = stages[base_index - 1]
            base[stage.fragment_index] += float(stage.coefficient)
        base_key = tuple(base)
        by_base = grouped.setdefault(tuple(outer), {})
        by_base[base_key] = by_base.get(base_key, 0.0) + abs(scalar)

    for j in range(2, s + 1):
        indices = tuple(range(s, j - 1, -1))
        for composition in weak_compositions(order, len(indices)):
            if composition[-1]:
                collect(j, indices, composition)
    for j in range(s + 1, count + 1):
        indices = tuple(range(s + 1, j + 1))
        for composition in weak_compositions(order, len(indices)):
            if composition[-1]:
                collect(j, indices, composition)

    local = evaluator or SymplecticDyadicLocalDensityEvaluator(
        shared_coordinates=True
    )
    denominator = float(1 << (order + 2))
    total = 0.0
    for outer, by_base in grouped.items():
        operators = [local.evaluate(outer + (base,)) for base in range(4)]
        paulis = tuple(set().union(*(operator.keys() for operator in operators)))
        row_for_pauli = {pauli: row for row, pauli in enumerate(paulis)}
        matrix = np.zeros((len(paulis), 4), dtype=np.int32)
        for column, operator in enumerate(operators):
            for pauli, coefficient in operator.items():
                matrix[row_for_pauli[pauli], column] = coefficient
        for base, scalar_weight in by_base.items():
            coefficients = matrix @ np.asarray(base, dtype=np.float64)
            total += scalar_weight * _pairwise_anticommuting_float_bound(
                paulis,
                coefficients,
            ) / denominator
    return total / factorial(order + 1)
