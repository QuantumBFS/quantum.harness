from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import factorial
from typing import Sequence

from .intervals import RationalInterval, outward_quantize
from .local_commutators import (
    CoordinateRegistry,
    SymplecticDyadicLocalDensityEvaluator,
    SymplecticPauli,
)
from .rigorous_fourth import (
    IntervalStage,
    fourth_order_suzuki_interval_stages,
)


IntervalWord = tuple[int, ...]
IntervalWordSeries = list[dict[IntervalWord, RationalInterval]]

# For h=(XX+YY+ZZ)/4 and any phase-free Pauli string P, either zero or
# exactly two of XX, YY, ZZ anticommute with P.  Each nonzero commutator
# contributes l1 weight 2/4, hence ||[h,P]||_{P,1} <= 1.
HEISENBERG_BOND_PAULI_L1_GROWTH = Fraction(1)


def symplectic_pauli_from_coordinates(
    registry: CoordinateRegistry,
    coordinates: Sequence[tuple[int, int, str]],
) -> SymplecticPauli:
    x_mask = z_mask = 0
    for x, y, op in coordinates:
        if op not in {"X", "Y", "Z"}:
            raise ValueError(f"unsupported Pauli axis {op!r}")
        bit = 1 << registry.site((x, y))
        if op in {"X", "Y"}:
            x_mask |= bit
        if op in {"Z", "Y"}:
            z_mask |= bit
    return x_mask, z_mask


def canonicalize_symplectic_unit_cell(
    registry: CoordinateRegistry,
    pauli: SymplecticPauli,
    unit_cell: tuple[int, int] = (2, 2),
) -> SymplecticPauli:
    step_x, step_y = unit_cell
    if step_x < 1 or step_y < 1:
        raise ValueError("unit-cell dimensions must be positive")
    x_mask, z_mask = pauli
    sites = x_mask | z_mask
    coordinates: list[tuple[int, int, str]] = []
    while sites:
        bit = sites & -sites
        site = bit.bit_length() - 1
        x = bool(x_mask & bit)
        z = bool(z_mask & bit)
        op = "Y" if x and z else ("X" if x else "Z")
        coordinate_x, coordinate_y = registry.coordinate(site)
        coordinates.append((coordinate_x, coordinate_y, op))
        sites ^= bit
    if not coordinates:
        return 0, 0
    min_x = min(x for x, _, _ in coordinates)
    min_y = min(y for _, y, _ in coordinates)
    shift_x = -(min_x - min_x % step_x)
    shift_y = -(min_y - min_y % step_y)
    return symplectic_pauli_from_coordinates(
        registry,
        tuple(
            (x + shift_x, y + shift_y, op)
            for x, y, op in coordinates
        ),
    )


def _interval_series_identity(order: int) -> IntervalWordSeries:
    result = [{} for _ in range(order + 1)]
    result[0][()] = RationalInterval.point(1)
    return result


def _interval_series_add(
    left: IntervalWordSeries,
    right: IntervalWordSeries,
) -> IntervalWordSeries:
    result: IntervalWordSeries = []
    zero = RationalInterval.point(0)
    for left_degree, right_degree in zip(left, right):
        terms = dict(left_degree)
        for word, coefficient in right_degree.items():
            terms[word] = terms.get(word, zero) + coefficient
        result.append(terms)
    return result


def _interval_series_scale(
    series: IntervalWordSeries,
    scalar: Fraction,
) -> IntervalWordSeries:
    return [
        {word: coefficient * scalar for word, coefficient in degree.items()}
        for degree in series
    ]


def _interval_series_multiply(
    left: IntervalWordSeries,
    right: IntervalWordSeries,
) -> IntervalWordSeries:
    order = len(left) - 1
    result: IntervalWordSeries = [{} for _ in range(order + 1)]
    zero = RationalInterval.point(0)
    for degree in range(order + 1):
        terms = result[degree]
        for left_degree in range(degree + 1):
            for left_word, left_coefficient in left[left_degree].items():
                for right_word, right_coefficient in right[degree - left_degree].items():
                    word = left_word + right_word
                    terms[word] = terms.get(word, zero) + (
                        left_coefficient * right_coefficient
                    )
    return result


def _interval_exponential(
    fragment_index: int,
    coefficient: RationalInterval,
    order: int,
) -> IntervalWordSeries:
    result: IntervalWordSeries = [{} for _ in range(order + 1)]
    for degree in range(order + 1):
        result[degree][(fragment_index,) * degree] = (
            coefficient**degree / factorial(degree)
        )
    return result


def interval_formula_log_series(
    stages: Sequence[IntervalStage],
    order: int,
) -> IntervalWordSeries:
    product = _interval_series_identity(order)
    for stage in stages:
        product = _interval_series_multiply(
            product,
            _interval_exponential(
                stage.fragment_index,
                stage.coefficient,
                order,
            ),
        )
    delta = _interval_series_add(
        product,
        _interval_series_scale(_interval_series_identity(order), Fraction(-1)),
    )
    logarithm: IntervalWordSeries = [{} for _ in range(order + 1)]
    power = _interval_series_identity(order)
    for exponent in range(1, order + 1):
        power = _interval_series_multiply(power, delta)
        logarithm = _interval_series_add(
            logarithm,
            _interval_series_scale(
                power,
                Fraction(1 if exponent % 2 else -1, exponent),
            ),
        )
    return logarithm


def _leading_e5_cell_interval_coefficients(
    stages: Sequence[IntervalStage],
    *,
    quantization_digits: int,
    canonicalize: bool,
) -> dict[SymplecticPauli, RationalInterval]:
    logarithm = interval_formula_log_series(stages, 5)
    grid = 10**quantization_digits
    word_endpoints: dict[IntervalWord, tuple[int, int]] = {}
    for word, coefficient in logarithm[5].items():
        rounded = outward_quantize(coefficient, grid)
        word_endpoints[word] = (
            rounded.lower.numerator * (grid // rounded.lower.denominator),
            rounded.upper.numerator * (grid // rounded.upper.denominator),
        )

    evaluator = SymplecticDyadicLocalDensityEvaluator(shared_coordinates=True)
    registry = evaluator.registries[0]
    coefficients: dict[SymplecticPauli, tuple[int, int]] = {}
    for word, (word_lower, word_upper) in word_endpoints.items():
        for raw_pauli, numerator in evaluator.evaluate(word).items():
            pauli = (
                canonicalize_symplectic_unit_cell(registry, raw_pauli)
                if canonicalize
                else raw_pauli
            )
            lower, upper = coefficients.get(pauli, (0, 0))
            if numerator >= 0:
                lower += numerator * word_lower
                upper += numerator * word_upper
            else:
                lower += numerator * word_upper
                upper += numerator * word_lower
            if lower or upper:
                coefficients[pauli] = (lower, upper)
            else:
                coefficients.pop(pauli, None)
    # Dynkin projection divides by degree five; local depth-five coefficients
    # have common dyadic denominator 2**6.
    denominator = grid * 5 * (1 << 6)
    return {
        pauli: RationalInterval(
            Fraction(lower, denominator),
            Fraction(upper, denominator),
        )
        for pauli, (lower, upper) in coefficients.items()
    }


def certified_leading_e5_cell_l1(
    stages: Sequence[IntervalStage],
    *,
    quantization_digits: int = 24,
) -> Fraction:
    coefficients = _leading_e5_cell_interval_coefficients(
        stages,
        quantization_digits=quantization_digits,
        canonicalize=False,
    )
    return sum(
        (coefficient.abs_upper() for coefficient in coefficients.values()),
        Fraction(),
    )


def certified_d4_cell_coefficients(
    stages: Sequence[IntervalStage],
    *,
    quantization_digits: int = 18,
) -> dict[SymplecticPauli, RationalInterval]:
    return {
        pauli: coefficient * 5
        for pauli, coefficient in _leading_e5_cell_interval_coefficients(
            stages,
            quantization_digits=quantization_digits,
            canonicalize=True,
        ).items()
    }


def certified_e7_cell_l1_majorant(
    stages: Sequence[IntervalStage],
) -> Fraction:
    logarithm = interval_formula_log_series(stages, 7)
    word_l1 = sum(
        (coefficient.abs_upper() for coefficient in logarithm[7].values()),
        Fraction(),
    )
    # A length-seven right-nested commutator starts from the 3/2 l1 cell
    # density and gains at most s at support size s=2,...,7.  A matching
    # contains at most one overlapping bond per support site, and one bond
    # has exact Pauli-l1 growth constant one.
    nested_max = Fraction(3, 2)
    for support_size in range(2, 8):
        nested_max *= (
            HEISENBERG_BOND_PAULI_L1_GROWTH * support_size
        )
    return word_l1 * nested_max / 7


def _abs_upper(interval: RationalInterval) -> Fraction:
    return interval.abs_upper()


def defect_tail_site_bound(
    stages: Sequence[IntervalStage],
    steps: int,
    *,
    first_omitted_degree: int = 8,
) -> Fraction:
    """Total-time, per-site tail bound for right-generator degrees >= q.

    A cell starts with Pauli-l1 density 3/2.  After ``q`` local adjoints,
    support counting gives at most

        (3/2) * (q+1)!

    per cell.  The conjugation Taylor coefficient contributes ``1/q!``;
    the Duhamel time integral contributes ``1/(q+1)``.  Those factorial
    factors cancel, leaving the geometric series summed below.  Dividing
    the four-site cell density by four produces the prefactor 3/8.
    """

    prefix = Fraction()
    total = Fraction()
    for stage in stages:
        coefficient = _abs_upper(stage.coefficient)
        ratio = (
            HEISENBERG_BOND_PAULI_L1_GROWTH * prefix / steps
        )
        if ratio >= 1:
            raise ValueError("step count is outside the convergence region")
        total += coefficient * ratio**first_omitted_degree / (1 - ratio)
        prefix += coefficient
    # Cell base density is 3/2; divide by four sites per cell.
    return Fraction(3, 8) * total


@dataclass(frozen=True)
class RefinedFourthOrderBound:
    steps: int
    e5_site_l1: Fraction
    e7_site_majorant: Fraction
    degree_four_contribution: Fraction
    degree_five_contribution: Fraction
    degree_six_contribution: Fraction
    degree_seven_contribution: Fraction
    tail_contribution: Fraction
    global_error_bound: Fraction


@dataclass(frozen=True)
class RefinedFourthOrderConstants:
    stages: tuple[IntervalStage, ...]
    e5_site_l1: Fraction
    e7_site_majorant: Fraction
    d4_site: Fraction
    d5_site: Fraction
    d6_site: Fraction
    d7_site: Fraction


def build_refined_fourth_order_constants(
    *,
    decimal_digits: int = 12,
    quantization_digits: int = 18,
) -> RefinedFourthOrderConstants:
    stages, _ = fourth_order_suzuki_interval_stages(
        4,
        decimal_digits=decimal_digits,
    )
    e5_site = certified_leading_e5_cell_l1(
        stages,
        quantization_digits=quantization_digits,
    ) / 4
    e7_site = certified_e7_cell_l1_majorant(stages) / 4

    # ad_H on an s-site Pauli term has at most 4s overlapping square-lattice
    # bonds.  The exact single-bond Pauli-l1 growth constant is one.
    h_e5 = 24 * e5_site
    hh_e5 = 28 * h_e5
    hhh_e5 = 32 * hh_e5
    h_e7 = 32 * e7_site

    return RefinedFourthOrderConstants(
        stages=tuple(stages),
        e5_site_l1=e5_site,
        e7_site_majorant=e7_site,
        d4_site=5 * e5_site,
        d5_site=2 * h_e5,
        d6_site=7 * e7_site + Fraction(2, 3) * hh_e5,
        d7_site=3 * h_e7 + Fraction(1, 6) * hhh_e5,
    )


def evaluate_refined_fourth_order_bound(
    constants: RefinedFourthOrderConstants,
    n_sites: int,
    steps: int,
) -> RefinedFourthOrderBound:

    def contribution(degree: int, density: Fraction) -> Fraction:
        return Fraction(n_sites) * density / (
            (degree + 1) * steps**degree
        )

    c4 = contribution(4, constants.d4_site)
    c5 = contribution(5, constants.d5_site)
    c6 = contribution(6, constants.d6_site)
    c7 = contribution(7, constants.d7_site)
    tail = Fraction(n_sites) * defect_tail_site_bound(constants.stages, steps)
    return RefinedFourthOrderBound(
        steps=steps,
        e5_site_l1=constants.e5_site_l1,
        e7_site_majorant=constants.e7_site_majorant,
        degree_four_contribution=c4,
        degree_five_contribution=c5,
        degree_six_contribution=c6,
        degree_seven_contribution=c7,
        tail_contribution=tail,
        global_error_bound=c4 + c5 + c6 + c7 + tail,
    )


def refined_fourth_order_bound(
    n_sites: int,
    steps: int,
    *,
    decimal_digits: int = 12,
    quantization_digits: int = 18,
) -> RefinedFourthOrderBound:
    constants = build_refined_fourth_order_constants(
        decimal_digits=decimal_digits,
        quantization_digits=quantization_digits,
    )
    return evaluate_refined_fourth_order_bound(constants, n_sites, steps)
