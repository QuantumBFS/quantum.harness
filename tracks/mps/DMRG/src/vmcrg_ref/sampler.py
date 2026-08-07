from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .blockspin import block_majority, block_sums
from .ising import IsingLattice, nearest_neighbor_operator


@dataclass(frozen=True)
class ProposalDelta:
    delta_s_micro: int
    delta_s_block: int
    new_block_sum: int
    new_block_spin: int


class BiasedMetropolis:
    """Metropolis sampler for H = K S_micro + J S_block."""

    def __init__(
        self,
        lattice: IsingLattice,
        coupling: float,
        bias: float,
        rng: np.random.Generator,
        block_size: int = 3,
    ) -> None:
        if lattice.length % block_size != 0:
            raise ValueError("lattice length must be divisible by block_size")
        self.lattice = lattice
        self.coupling = float(coupling)
        self.bias = float(bias)
        self.rng = rng
        self.block_size = int(block_size)
        self.block_sums = block_sums(lattice.spins, block_size)
        self.block_spins = block_majority(lattice.spins, block_size)
        self.attempted = 0
        self.accepted = 0

    @property
    def s_micro(self) -> int:
        return self.lattice.s_nn

    @property
    def s_block(self) -> int:
        return nearest_neighbor_operator(self.block_spins)

    @property
    def effective_hamiltonian(self) -> float:
        return self.coupling * self.s_micro + self.bias * self.s_block

    @property
    def acceptance_rate(self) -> float:
        return self.accepted / self.attempted if self.attempted else 0.0

    def proposal_delta(self, x: int, y: int) -> ProposalDelta:
        delta_s_micro = self.lattice.delta_s_nn(x, y)
        bx, by = x // self.block_size, y // self.block_size
        old_spin = int(self.lattice.spins[x, y])
        old_block_spin = int(self.block_spins[bx, by])
        new_sum = int(self.block_sums[bx, by] - 2 * old_spin)
        if new_sum == 0:
            raise AssertionError("odd blocks cannot have a tied majority")
        new_block_spin = 1 if new_sum > 0 else -1

        delta_s_block = 0
        if new_block_spin != old_block_spin:
            coarse = self.block_spins.shape[0]
            neighbor_sum = int(
                self.block_spins[(bx - 1) % coarse, by]
                + self.block_spins[(bx + 1) % coarse, by]
                + self.block_spins[bx, (by - 1) % coarse]
                + self.block_spins[bx, (by + 1) % coarse]
            )
            delta_s_block = 2 * old_block_spin * neighbor_sum

        return ProposalDelta(
            delta_s_micro=delta_s_micro,
            delta_s_block=delta_s_block,
            new_block_sum=new_sum,
            new_block_spin=new_block_spin,
        )

    def attempt_flip(self, x: int, y: int, uniform: float | None = None) -> bool:
        proposal = self.proposal_delta(x, y)
        delta_h = self.coupling * proposal.delta_s_micro + self.bias * proposal.delta_s_block
        draw = float(self.rng.random()) if uniform is None else float(uniform)
        accept = delta_h <= 0.0 or draw < np.exp(-delta_h)
        self.attempted += 1
        if not accept:
            return False

        bx, by = x // self.block_size, y // self.block_size
        self.lattice.flip(x, y)
        self.block_sums[bx, by] = proposal.new_block_sum
        self.block_spins[bx, by] = proposal.new_block_spin
        self.accepted += 1
        return True

    def sweep(self) -> None:
        length = self.lattice.length
        for _ in range(self.lattice.n_sites):
            x = int(self.rng.integers(length))
            y = int(self.rng.integers(length))
            self.attempt_flip(x, y)

    def assert_cache_consistent(self) -> None:
        expected_sums = block_sums(self.lattice.spins, self.block_size)
        expected_spins = block_majority(self.lattice.spins, self.block_size)
        if not np.array_equal(self.block_sums, expected_sums):
            raise AssertionError("cached block sums are inconsistent")
        if not np.array_equal(self.block_spins, expected_spins):
            raise AssertionError("cached block spins are inconsistent")
