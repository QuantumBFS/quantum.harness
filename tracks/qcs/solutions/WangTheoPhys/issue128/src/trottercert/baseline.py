from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Callable, Sequence

from .algebra import PauliSum, commutator


@dataclass(frozen=True)
class StrangCommutatorBlock:
    fragment_index: int
    repeated_fragment: PauliSum
    repeated_tail: PauliSum


def _sum_ops(operators: Sequence[PauliSum]) -> PauliSum:
    result = PauliSum.zero()
    for operator in operators:
        result += operator
    return result


def strang_commutator_operators(
    fragments: Sequence[PauliSum],
) -> tuple[StrangCommutatorBlock, ...]:
    if len(fragments) < 2:
        raise ValueError("Strang formula requires at least two fragments")
    blocks: list[StrangCommutatorBlock] = []
    for index in range(len(fragments) - 1):
        current = fragments[index]
        tail = _sum_ops(fragments[index + 1 :])
        blocks.append(
            StrangCommutatorBlock(
                fragment_index=index,
                repeated_fragment=commutator(current, commutator(current, tail)),
                repeated_tail=commutator(tail, commutator(tail, current)),
            )
        )
    return tuple(blocks)


def pauli_l1_second_order_constant(fragments: Sequence[PauliSum]) -> Fraction:
    total = Fraction()
    for block in strang_commutator_operators(fragments):
        total += Fraction(1, 24) * block.repeated_fragment.exact_real_l1()
        total += Fraction(1, 12) * block.repeated_tail.exact_real_l1()
    return total
