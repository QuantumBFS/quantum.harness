from __future__ import annotations

from fractions import Fraction
from math import factorial
from typing import Mapping, Sequence

from .cubic_field import Cubic, CubicStage
from .local_commutators import (
    CoordinateBond,
    CoordinateRegistry,
    SymplecticPauli,
    _iter_set_bits,
    _symplectic_anticommutes,
    _symplectic_bond_terms,
    _symplectic_product_phase,
    canonical_coordinate_bond,
    matching_partner,
    SymplecticDyadicLocalDensityEvaluator,
)
from .refined_error import canonicalize_symplectic_unit_cell


CubicTerms = dict[SymplecticPauli, Cubic]
CubicWord = tuple[int, ...]
CubicWordSeries = list[dict[CubicWord, Cubic]]


def _add_term(
    target: dict[object, Cubic],
    key: object,
    value: Cubic,
) -> None:
    if value == Cubic.zero():
        return
    updated = target.get(key, Cubic.zero()) + value
    if updated == Cubic.zero():
        target.pop(key, None)
    else:
        target[key] = updated


def _series_identity(order: int) -> CubicWordSeries:
    result: CubicWordSeries = [{} for _ in range(order + 1)]
    result[0][()] = Cubic.one()
    return result


def _series_add(
    left: CubicWordSeries,
    right: CubicWordSeries,
) -> CubicWordSeries:
    result: CubicWordSeries = []
    for left_degree, right_degree in zip(left, right):
        terms = dict(left_degree)
        for word, coefficient in right_degree.items():
            _add_term(terms, word, coefficient)
        result.append(terms)
    return result


def _series_scale(
    series: CubicWordSeries,
    scalar: int | Fraction,
) -> CubicWordSeries:
    return [
        {
            word: scaled
            for word, coefficient in degree.items()
            if (scaled := coefficient * scalar) != Cubic.zero()
        }
        for degree in series
    ]


def _series_multiply(
    left: CubicWordSeries,
    right: CubicWordSeries,
) -> CubicWordSeries:
    order = len(left) - 1
    result: CubicWordSeries = [{} for _ in range(order + 1)]
    for degree in range(order + 1):
        terms = result[degree]
        for left_degree in range(degree + 1):
            for left_word, left_coefficient in left[left_degree].items():
                for right_word, right_coefficient in right[
                    degree - left_degree
                ].items():
                    _add_term(
                        terms,
                        left_word + right_word,
                        left_coefficient * right_coefficient,
                    )
    return result


def _stage_exponential(
    stage: CubicStage,
    order: int,
) -> CubicWordSeries:
    result: CubicWordSeries = [{} for _ in range(order + 1)]
    for degree in range(order + 1):
        result[degree][(stage.fragment_index,) * degree] = (
            stage.coefficient**degree / factorial(degree)
        )
    return result


def cubic_formula_log_series(
    stages: Sequence[CubicStage],
    order: int,
) -> CubicWordSeries:
    if order < 0:
        raise ValueError("series order must be nonnegative")
    product = _series_identity(order)
    for stage in stages:
        product = _series_multiply(
            product,
            _stage_exponential(stage, order),
        )
    delta = _series_add(
        product,
        _series_scale(_series_identity(order), -1),
    )
    logarithm: CubicWordSeries = [{} for _ in range(order + 1)]
    power = _series_identity(order)
    for exponent in range(1, order + 1):
        power = _series_multiply(power, delta)
        logarithm = _series_add(
            logarithm,
            _series_scale(
                power,
                Fraction(1 if exponent % 2 else -1, exponent),
            ),
        )
    return logarithm


def canonicalize_cubic_density(
    registry: CoordinateRegistry,
    operator: Mapping[SymplecticPauli, Cubic],
) -> CubicTerms:
    result: CubicTerms = {}
    for raw_pauli, coefficient in operator.items():
        pauli = canonicalize_symplectic_unit_cell(registry, raw_pauli)
        _add_term(result, pauli, coefficient)
    return result


def exact_log_e5_density(
    stages: Sequence[CubicStage],
) -> tuple[CoordinateRegistry, CubicTerms]:
    """Return the exact fifth-degree logarithm density."""

    logarithm = cubic_formula_log_series(stages, 5)
    evaluator = SymplecticDyadicLocalDensityEvaluator(shared_coordinates=True)
    registry = evaluator.registries[0]
    result: CubicTerms = {}
    denominator = 5 * (1 << evaluator.denominator_exponent((0,) * 5))
    for word, word_coefficient in logarithm[5].items():
        for raw_pauli, numerator in evaluator.evaluate(word).items():
            pauli = canonicalize_symplectic_unit_cell(registry, raw_pauli)
            _add_term(
                result,
                pauli,
                word_coefficient * Fraction(numerator, denominator),
            )
    return registry, result


def cubic_fragment_adjoint(
    registry: CoordinateRegistry,
    color: int,
    operator: Mapping[SymplecticPauli, Cubic],
) -> CubicTerms:
    """Apply one physical Heisenberg adjoint to an exact cubic map."""

    candidate_bonds: set[CoordinateBond] = set()
    for x_mask, z_mask in operator:
        for site in _iter_set_bits(x_mask | z_mask):
            coordinate = registry.coordinate(site)
            candidate_bonds.add(
                canonical_coordinate_bond(
                    coordinate,
                    matching_partner(coordinate, color),
                )
            )

    result: CubicTerms = {}
    for bond in sorted(candidate_bonds):
        first, second = (registry.site(coordinate) for coordinate in bond)
        for bond_pauli in _symplectic_bond_terms(first, second):
            for pauli, coefficient in operator.items():
                if not _symplectic_anticommutes(bond_pauli, pauli):
                    continue
                phase, product_pauli = _symplectic_product_phase(
                    bond_pauli, pauli
                )
                sign = 1 if phase == 1 else -1
                _add_term(result, product_pauli, sign * coefficient / 2)
    return result


def exact_d5_density(
    registry: CoordinateRegistry,
    e5: Mapping[SymplecticPauli, Cubic],
) -> CubicTerms:
    result: CubicTerms = {}
    for color in range(4):
        image = cubic_fragment_adjoint(registry, color, e5)
        for pauli, coefficient in image.items():
            _add_term(result, pauli, 2 * coefficient)
    return canonicalize_cubic_density(registry, result)


def exact_matching_density(
    color: int,
) -> tuple[CoordinateRegistry, CubicTerms]:
    """Return one exact two-by-two-cell matching Hamiltonian density."""

    if color not in range(4):
        raise ValueError("matching color must be 0, 1, 2 or 3")
    evaluator = SymplecticDyadicLocalDensityEvaluator(shared_coordinates=True)
    registry = evaluator.registries[0]
    key = (color,)
    denominator = 1 << evaluator.denominator_exponent(key)
    return registry, canonicalize_cubic_density(
        registry,
        {
            pauli: Cubic(Fraction(numerator, denominator), 0, 0)
            for pauli, numerator in evaluator.evaluate(key).items()
        },
    )


def _add_cubic_operator(
    target: CubicTerms,
    source: Mapping[SymplecticPauli, Cubic],
    scalar: Cubic | int | Fraction = 1,
) -> None:
    for pauli, coefficient in source.items():
        _add_term(target, pauli, coefficient * scalar)


def conjugate_cubic_series_by_stage(
    registry: CoordinateRegistry,
    series: Sequence[Mapping[SymplecticPauli, Cubic]],
    color: int,
    coefficient: Cubic,
) -> list[CubicTerms]:
    """Conjugate an exact local series by one matching exponential."""

    order = len(series) - 1
    result: list[CubicTerms] = [{} for _ in range(order + 1)]
    for degree, operator in enumerate(series):
        power = dict(operator)
        for nested_degree in range(order - degree + 1):
            _add_cubic_operator(
                result[degree + nested_degree],
                power,
                coefficient**nested_degree / factorial(nested_degree),
            )
            if nested_degree < order - degree:
                power = canonicalize_cubic_density(
                    registry,
                    cubic_fragment_adjoint(registry, color, power),
                )
    return result


def exact_right_generator_stage_contribution(
    stages: Sequence[CubicStage],
    stage_index: int,
    order: int,
) -> tuple[CoordinateRegistry, list[CubicTerms]]:
    """Return one stage's exact contribution to ``i S' S^dagger``.

    The full right generator is the exact sum of this function over every
    stage.  Keeping stage contributions independent makes the expensive local
    recurrence safe to distribute across Slurm array cells.
    """

    if order < 0:
        raise ValueError("series order must be nonnegative")
    if stage_index < 0 or stage_index >= len(stages):
        raise IndexError("stage index is out of range")
    stage = stages[stage_index]
    registry, base = exact_matching_density(stage.fragment_index)
    series: list[CubicTerms] = [{} for _ in range(order + 1)]
    series[0] = {
        pauli: stage.coefficient * coefficient
        for pauli, coefficient in base.items()
    }
    for later in stages[stage_index + 1 :]:
        series = conjugate_cubic_series_by_stage(
            registry,
            series,
            later.fragment_index,
            later.coefficient,
        )
    return registry, [
        canonicalize_cubic_density(registry, degree) for degree in series
    ]
