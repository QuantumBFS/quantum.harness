from __future__ import annotations

from math import factorial
from typing import Sequence

import mpmath as mp

from .higher_order import ScalarStage
from .local_commutators import SymplecticDyadicLocalDensityEvaluator


Word = tuple[int, ...]
WordPolynomial = dict[Word, mp.mpf]
WordSeries = list[WordPolynomial]


def _series_identity(order: int) -> WordSeries:
    result: WordSeries = [{} for _ in range(order + 1)]
    result[0][()] = mp.mpf(1)
    return result


def _series_add(left: WordSeries, right: WordSeries) -> WordSeries:
    result: WordSeries = []
    for left_degree, right_degree in zip(left, right):
        terms = dict(left_degree)
        for word, coefficient in right_degree.items():
            updated = terms.get(word, mp.mpf(0)) + coefficient
            if updated:
                terms[word] = updated
            else:
                terms.pop(word, None)
        result.append(terms)
    return result


def _series_scale(series: WordSeries, scalar: mp.mpf) -> WordSeries:
    return [
        {word: scalar * coefficient for word, coefficient in degree.items()}
        for degree in series
    ]


def _series_multiply(left: WordSeries, right: WordSeries) -> WordSeries:
    order = len(left) - 1
    result: WordSeries = [{} for _ in range(order + 1)]
    for degree in range(order + 1):
        terms = result[degree]
        for left_degree in range(degree + 1):
            for left_word, left_coefficient in left[left_degree].items():
                for right_word, right_coefficient in right[degree - left_degree].items():
                    word = left_word + right_word
                    terms[word] = terms.get(word, mp.mpf(0)) + (
                        left_coefficient * right_coefficient
                    )
    return result


def abstract_exponential_series(
    fragment_index: int,
    coefficient: mp.mpf,
    order: int,
) -> WordSeries:
    result: WordSeries = [{} for _ in range(order + 1)]
    for degree in range(order + 1):
        result[degree][(fragment_index,) * degree] = (
            coefficient**degree / factorial(degree)
        )
    return result


def abstract_formula_log_series(
    stages: Sequence[ScalarStage],
    order: int,
) -> WordSeries:
    product = _series_identity(order)
    for stage in stages:
        product = _series_multiply(
            product,
            abstract_exponential_series(
                stage.fragment_index,
                stage.coefficient,
                order,
            ),
        )
    delta = _series_add(product, _series_scale(_series_identity(order), mp.mpf(-1)))
    logarithm: WordSeries = [{} for _ in range(order + 1)]
    power = _series_identity(order)
    for exponent in range(1, order + 1):
        power = _series_multiply(power, delta)
        logarithm = _series_add(
            logarithm,
            _series_scale(power, mp.mpf(1 if exponent % 2 else -1) / exponent),
        )
    return logarithm


def leading_lie_local_coefficients(
    stages: Sequence[ScalarStage],
    degree: int,
) -> dict[tuple[int, int], mp.mpf]:
    """Map a homogeneous log coefficient to its local Pauli density.

    The Dynkin--Specht--Wever projection maps every word to its right-nested
    commutator and divides by the homogeneous degree.
    """

    logarithm = abstract_formula_log_series(stages, degree)
    evaluator = SymplecticDyadicLocalDensityEvaluator(shared_coordinates=True)
    scale = mp.mpf(1) / (degree * (1 << (degree + 1)))
    coefficients: dict[tuple[int, int], mp.mpf] = {}
    for word, word_coefficient in logarithm[degree].items():
        if not word_coefficient:
            continue
        operator = evaluator.evaluate(word)
        for pauli, numerator in operator.items():
            updated = coefficients.get(pauli, mp.mpf(0)) + (
                word_coefficient * numerator * scale
            )
            if updated:
                coefficients[pauli] = updated
            else:
                coefficients.pop(pauli, None)
    return coefficients
