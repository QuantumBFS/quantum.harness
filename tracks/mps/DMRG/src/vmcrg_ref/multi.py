from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .blockspin import block_majority, block_sums
from .ising import IsingLattice
from .operators import OperatorBasis, OperatorShape


@dataclass(frozen=True)
class MultiProposalDelta:
    delta_micro: np.ndarray
    delta_block: np.ndarray
    new_block_sum: int
    new_block_spin: int


class MultiOperatorBiasedMetropolis:
    """Metropolis sampler for vector microscopic couplings and vector block bias."""

    @classmethod
    def random(
        cls,
        length: int,
        couplings: np.ndarray,
        bias: np.ndarray,
        shapes: tuple[OperatorShape, ...],
        seed: int,
        block_size: int = 3,
        micro_basis: OperatorBasis | None = None,
        block_basis: OperatorBasis | None = None,
    ) -> "MultiOperatorBiasedMetropolis":
        rng = np.random.default_rng(seed)
        return cls(
            lattice=IsingLattice.random(length, rng),
            couplings=couplings,
            bias=bias,
            rng=rng,
            shapes=shapes,
            block_size=block_size,
            micro_basis=micro_basis,
            block_basis=block_basis,
        )

    def __init__(
        self,
        lattice: IsingLattice,
        couplings: np.ndarray,
        bias: np.ndarray,
        rng: np.random.Generator,
        shapes: tuple[OperatorShape, ...],
        block_size: int = 3,
        micro_basis: OperatorBasis | None = None,
        block_basis: OperatorBasis | None = None,
    ) -> None:
        if lattice.length % block_size != 0:
            raise ValueError("lattice length must be divisible by block_size")
        self.lattice = lattice
        self.rng = rng
        self.shapes = tuple(shapes)
        self.block_size = int(block_size)
        self.couplings = np.asarray(couplings, dtype=float).copy()
        self.bias = np.asarray(bias, dtype=float).copy()
        if self.couplings.shape != (len(self.shapes),):
            raise ValueError("couplings have the wrong shape")
        if self.bias.shape != (len(self.shapes),):
            raise ValueError("bias has the wrong shape")

        coarse = lattice.length // block_size
        self.micro_basis = micro_basis or OperatorBasis(lattice.length, self.shapes)
        self.block_basis = block_basis or OperatorBasis(coarse, self.shapes)
        self.block_sums = block_sums(lattice.spins, block_size)
        self.block_spins = block_majority(lattice.spins, block_size)
        self.micro_values = self.micro_basis.values(lattice.spins)
        self.block_values = self.block_basis.values(self.block_spins)
        self.attempted = 0
        self.accepted = 0

    @property
    def effective_hamiltonian(self) -> float:
        return float(
            np.dot(self.couplings, self.micro_values)
            + np.dot(self.bias, self.block_values)
        )

    @property
    def acceptance_rate(self) -> float:
        return self.accepted / self.attempted if self.attempted else 0.0

    def proposal_delta(self, x: int, y: int) -> MultiProposalDelta:
        delta_micro = self.micro_basis.delta_for_flip(self.lattice.spins, x, y)
        bx, by = x // self.block_size, y // self.block_size
        old_spin = int(self.lattice.spins[x, y])
        old_block_spin = int(self.block_spins[bx, by])
        new_sum = int(self.block_sums[bx, by] - 2 * old_spin)
        if new_sum == 0:
            raise AssertionError("odd blocks cannot have a tied majority")
        new_block_spin = 1 if new_sum > 0 else -1
        delta_block = np.zeros(len(self.shapes), dtype=np.int64)
        if new_block_spin != old_block_spin:
            delta_block = self.block_basis.delta_for_flip(self.block_spins, bx, by)
        return MultiProposalDelta(
            delta_micro=delta_micro,
            delta_block=delta_block,
            new_block_sum=new_sum,
            new_block_spin=new_block_spin,
        )

    def attempt_flip(self, x: int, y: int, uniform: float | None = None) -> bool:
        proposal = self.proposal_delta(x, y)
        delta_h = float(
            np.dot(self.couplings, proposal.delta_micro)
            + np.dot(self.bias, proposal.delta_block)
        )
        draw = float(self.rng.random()) if uniform is None else float(uniform)
        accept = delta_h <= 0.0 or draw < np.exp(-delta_h)
        self.attempted += 1
        if not accept:
            return False

        bx, by = x // self.block_size, y // self.block_size
        self.lattice.flip(x, y)
        self.block_sums[bx, by] = proposal.new_block_sum
        self.block_spins[bx, by] = proposal.new_block_spin
        self.micro_values += proposal.delta_micro
        self.block_values += proposal.delta_block
        self.accepted += 1
        return True

    def sweep(self) -> None:
        length = self.lattice.length
        for _ in range(self.lattice.n_sites):
            x = int(self.rng.integers(length))
            y = int(self.rng.integers(length))
            self.attempt_flip(x, y)

    def run_sweeps(self, sweeps: int) -> None:
        if sweeps <= 0:
            raise ValueError("sweeps must be positive")
        for _ in range(sweeps):
            self.sweep()

    def assert_cache_consistent(self) -> None:
        expected_sums = block_sums(self.lattice.spins, self.block_size)
        expected_spins = block_majority(self.lattice.spins, self.block_size)
        np.testing.assert_array_equal(self.block_sums, expected_sums)
        np.testing.assert_array_equal(self.block_spins, expected_spins)
        np.testing.assert_array_equal(
            self.micro_values, self.micro_basis.values(self.lattice.spins)
        )
        np.testing.assert_array_equal(
            self.block_values, self.block_basis.values(self.block_spins)
        )
