from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Sequence

from .algebra import PauliSum, QComplex, commutator
from .series import exponential_series, logarithm_series, product_series


@dataclass(frozen=True)
class FormulaStage:
    fragment: PauliSum
    coefficient: Fraction
    fragment_index: int


def strang_stages(
    fragments: Sequence[PauliSum],
    ordering: Sequence[int] | None = None,
) -> tuple[FormulaStage, ...]:
    if len(fragments) < 2:
        raise ValueError("Strang formula requires at least two fragments")
    selected = tuple(ordering) if ordering is not None else tuple(range(len(fragments)))
    if sorted(selected) != list(range(len(fragments))):
        raise ValueError("ordering must be a permutation of fragment indices")
    stages: list[FormulaStage] = []
    for index in selected[:-1]:
        stages.append(FormulaStage(fragments[index], Fraction(1, 2), index))
    center = selected[-1]
    stages.append(FormulaStage(fragments[center], Fraction(1), center))
    for index in reversed(selected[:-1]):
        stages.append(FormulaStage(fragments[index], Fraction(1, 2), index))
    return tuple(stages)


def formula_log_series(
    stages: Sequence[FormulaStage],
    order: int = 3,
) -> list[PauliSum]:
    exponentials = [
        exponential_series(
            stage.fragment,
            QComplex(0, -stage.coefficient),
            order,
        )
        for stage in stages
    ]
    return logarithm_series(product_series(exponentials, order)).coefficients


def formula_log_through_degree_three(
    stages: Sequence[FormulaStage],
) -> tuple[PauliSum, PauliSum, PauliSum]:
    """Compute log of the stage product by a graded BCH recurrence.

    This avoids expanding ordinary fragment products. If ``X`` is the
    accumulated logarithm and ``Y`` is the next degree-one stage generator,
    BCH through degree three is

    ``X + Y + [X,Y]/2 + ([X,[X,Y]] + [Y,[Y,X]])/12``.
    """

    degree_one = PauliSum.zero()
    degree_two = PauliSum.zero()
    degree_three = PauliSum.zero()
    for stage in stages:
        next_one = stage.fragment.scale(QComplex(0, -stage.coefficient))
        comm_one = commutator(degree_one, next_one)
        new_three = (
            degree_three
            + commutator(degree_two, next_one).scale(Fraction(1, 2))
            + commutator(degree_one, comm_one).scale(Fraction(1, 12))
            + commutator(next_one, commutator(next_one, degree_one)).scale(
                Fraction(1, 12)
            )
        )
        new_two = degree_two + comm_one.scale(Fraction(1, 2))
        degree_one = degree_one + next_one
        degree_two = new_two
        degree_three = new_three
    return degree_one, degree_two, degree_three


def leading_effective_error(stages: Sequence[FormulaStage]) -> PauliSum:
    """Return Hermitian E3 where log(S(t)) = -itH - it^3 E3 + O(t^5)."""

    _, degree_two, degree_three = formula_log_through_degree_three(stages)
    if degree_two:
        raise ArithmeticError("formula is not second order")
    error = degree_three.scale(QComplex(0, 1))
    if not error.is_hermitian():
        raise ArithmeticError("leading effective error is not Hermitian")
    return error
