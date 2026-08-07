"""Incremental non-overlapping majority-rule RG state.

Blocks start at the microscopic origin ``(0, 0)`` and are ordered row-major.
At every level, sites ``(b*x+i, b*y+j)`` with ``0 <= i,j < b`` form coarse
site ``(x, y)``. Periodicity applies to interactions on every resulting
lattice; the block partition itself is the fixed non-overlapping partition.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .blockspin import block_majority, block_sums
from .ising import validate_spins


@dataclass(frozen=True)
class RGLevelChange:
    level: int
    x: int
    y: int
    old_spin: int
    new_spin: int
    new_sum: int

    @property
    def changed(self) -> bool:
        return self.old_spin != self.new_spin


@dataclass(frozen=True)
class MajorityRGProposal:
    x: int
    y: int
    old_micro_spin: int
    changes: tuple[RGLevelChange, ...]

    @property
    def final_changed(self) -> bool:
        return bool(self.changes and self.changes[-1].changed)

    @property
    def final_site(self) -> tuple[int, int] | None:
        if not self.changes:
            return None
        final = self.changes[-1]
        return final.x, final.y


class MajorityRGState:
    """Cache one or more composed odd-block majority transformations."""

    def __init__(
        self,
        spins: np.ndarray,
        block_size: int = 3,
        levels: int = 1,
    ) -> None:
        values = np.asarray(spins, dtype=np.int8)
        validate_spins(values)
        if block_size <= 0 or block_size % 2 == 0:
            raise ValueError("block_size must be a positive odd integer")
        if levels < 1:
            raise ValueError("levels must be positive")
        divisor = block_size**levels
        if values.shape[0] % divisor != 0:
            raise ValueError("lattice length must be divisible by block_size**levels")
        self.micro_spins = values
        self.block_size = int(block_size)
        self.levels = int(levels)
        self.level_sums: list[np.ndarray] = []
        self.level_spins: list[np.ndarray] = []
        current = self.micro_spins
        for _ in range(self.levels):
            sums = block_sums(current, self.block_size)
            coarse = np.where(sums > 0, 1, -1).astype(np.int8)
            self.level_sums.append(sums)
            self.level_spins.append(coarse)
            current = coarse

    @property
    def coarse_spins(self) -> np.ndarray:
        return self.level_spins[-1]

    def proposal(self, x: int, y: int) -> MajorityRGProposal:
        length = self.micro_spins.shape[0]
        x %= length
        y %= length
        old_micro = int(self.micro_spins[x, y])
        changed_spin = old_micro
        site_x, site_y = x, y
        changes: list[RGLevelChange] = []
        for level in range(self.levels):
            bx = site_x // self.block_size
            by = site_y // self.block_size
            old_coarse = int(self.level_spins[level][bx, by])
            new_sum = int(self.level_sums[level][bx, by] - 2 * changed_spin)
            if new_sum == 0:
                raise AssertionError("odd blocks cannot have a tied majority")
            new_coarse = 1 if new_sum > 0 else -1
            change = RGLevelChange(
                level=level,
                x=bx,
                y=by,
                old_spin=old_coarse,
                new_spin=new_coarse,
                new_sum=new_sum,
            )
            changes.append(change)
            if not change.changed:
                break
            changed_spin = old_coarse
            site_x, site_y = bx, by
        return MajorityRGProposal(x, y, old_micro, tuple(changes))

    def commit(self, proposal: MajorityRGProposal) -> None:
        if int(self.micro_spins[proposal.x, proposal.y]) != proposal.old_micro_spin:
            raise AssertionError("microscopic spin changed before RG proposal commit")
        self.micro_spins[proposal.x, proposal.y] *= -1
        for change in proposal.changes:
            if int(self.level_spins[change.level][change.x, change.y]) != change.old_spin:
                raise AssertionError("coarse spin changed before RG proposal commit")
            self.level_sums[change.level][change.x, change.y] = change.new_sum
            if change.changed:
                self.level_spins[change.level][change.x, change.y] = change.new_spin

    def assert_consistent(self) -> None:
        current = self.micro_spins
        for level in range(self.levels):
            expected_sums = block_sums(current, self.block_size)
            expected_spins = block_majority(current, self.block_size)
            np.testing.assert_array_equal(self.level_sums[level], expected_sums)
            np.testing.assert_array_equal(self.level_spins[level], expected_spins)
            current = expected_spins
