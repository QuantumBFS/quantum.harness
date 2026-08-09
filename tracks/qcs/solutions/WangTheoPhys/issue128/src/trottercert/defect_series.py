from __future__ import annotations

from math import factorial
from typing import Sequence

from .higher_order import ScalarStage
from .local_commutators import (
    CoordinateRegistry,
    SymplecticDyadicLocalDensityEvaluator,
    SymplecticPauli,
    symplectic_local_fragment_adjoint,
)


FloatOperator = dict[SymplecticPauli, float]


def _pauli_coordinates(
    registry: CoordinateRegistry,
    pauli: SymplecticPauli,
) -> list[tuple[int, int, str]]:
    x_mask, z_mask = pauli
    sites = x_mask | z_mask
    result: list[tuple[int, int, str]] = []
    while sites:
        bit = sites & -sites
        site = bit.bit_length() - 1
        x = bool(x_mask & bit)
        z = bool(z_mask & bit)
        op = "Y" if x and z else ("X" if x else "Z")
        coordinate = registry.coordinate(site)
        result.append((coordinate[0], coordinate[1], op))
        sites ^= bit
    return result


def canonicalize_unit_cell_operator(
    registry: CoordinateRegistry,
    operator: FloatOperator,
    unit_cell: tuple[int, int] = (2, 2),
    *,
    tolerance: float = 1e-18,
) -> FloatOperator:
    result: FloatOperator = {}
    step_x, step_y = unit_cell
    for pauli, coefficient in operator.items():
        coordinates = _pauli_coordinates(registry, pauli)
        if not coordinates:
            key = (0, 0)
        else:
            min_x = min(x for x, _, _ in coordinates)
            min_y = min(y for _, y, _ in coordinates)
            shift_x = -(min_x - (min_x % step_x))
            shift_y = -(min_y - (min_y % step_y))
            x_mask = z_mask = 0
            for x, y, op in coordinates:
                site = registry.site((x + shift_x, y + shift_y))
                bit = 1 << site
                if op in {"X", "Y"}:
                    x_mask |= bit
                if op in {"Z", "Y"}:
                    z_mask |= bit
            key = (x_mask, z_mask)
        updated = result.get(key, 0.0) + coefficient
        if abs(updated) > tolerance:
            result[key] = updated
        else:
            result.pop(key, None)
    return result


def _add_scaled(
    target: FloatOperator,
    source: FloatOperator,
    scalar: float,
    *,
    tolerance: float = 1e-18,
) -> None:
    if not scalar:
        return
    for pauli, coefficient in source.items():
        updated = target.get(pauli, 0.0) + scalar * coefficient
        if abs(updated) > tolerance:
            target[pauli] = updated
        else:
            target.pop(pauli, None)


def normalized_local_adjoint(
    registry: CoordinateRegistry,
    color: int,
    operator: FloatOperator,
) -> FloatOperator:
    raw = symplectic_local_fragment_adjoint(registry, color, operator)
    return canonicalize_unit_cell_operator(
        registry,
        {pauli: coefficient / 2 for pauli, coefficient in raw.items()},
    )


def conjugate_series_by_stage(
    registry: CoordinateRegistry,
    series: Sequence[FloatOperator],
    color: int,
    coefficient: float,
) -> list[FloatOperator]:
    order = len(series) - 1
    result: list[FloatOperator] = [{} for _ in range(order + 1)]
    for degree, operator in enumerate(series):
        power = operator
        for nested_degree in range(order - degree + 1):
            scalar = coefficient**nested_degree / factorial(nested_degree)
            _add_scaled(result[degree + nested_degree], power, scalar)
            if nested_degree < order - degree:
                power = normalized_local_adjoint(registry, color, power)
    return result


def right_generator_local_series(
    stages_left_to_right: Sequence[ScalarStage],
    order: int,
) -> list[FloatOperator]:
    """Return coefficients of ``i S'(t) S(t)^dagger`` as cell densities."""

    evaluator = SymplecticDyadicLocalDensityEvaluator(shared_coordinates=True)
    registry = evaluator.registries[0]
    base_operators = []
    for color in range(4):
        base = {
            pauli: numerator / 4
            for pauli, numerator in evaluator.evaluate((color,)).items()
        }
        base_operators.append(
            canonicalize_unit_cell_operator(registry, base)
        )

    # Build S recursively by left multiplication: S_new = V S_old.
    # Then i S_new' S_new^dagger = a H_color + Ad_V(G_old).
    # This avoids replaying every prefix separately.
    generator: list[FloatOperator] = [{} for _ in range(order + 1)]
    for stage in stages_left_to_right:
        generator = conjugate_series_by_stage(
            registry,
            generator,
            stage.fragment_index,
            float(stage.coefficient),
        )
        _add_scaled(
            generator[0],
            base_operators[stage.fragment_index],
            float(stage.coefficient),
        )
    return generator
