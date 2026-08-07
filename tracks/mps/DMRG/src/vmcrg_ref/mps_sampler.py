"""Local Metropolis sampling for a traditional bias plus patch-MPS residual."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numba import njit

from .ising import IsingLattice
from .operators import OperatorBasis, OperatorShape
from .patch_table import PatchEnergyCache, PatchEnergyProposal, PatchLookupTable
from .rg import MajorityRGProposal, MajorityRGState


@njit(cache=True, nogil=True)
def _compiled_mps_sweeps(
    spins: np.ndarray,
    level1_sums: np.ndarray,
    level1_spins: np.ndarray,
    level2_sums: np.ndarray,
    level2_spins: np.ndarray,
    rg_levels: int,
    micro_values: np.ndarray,
    block_values: np.ndarray,
    couplings: np.ndarray,
    linear_bias: np.ndarray,
    alpha: float,
    micro_offsets: np.ndarray,
    micro_operators: np.ndarray,
    micro_arities: np.ndarray,
    micro_sites: np.ndarray,
    block_offsets: np.ndarray,
    block_operators: np.ndarray,
    block_arities: np.ndarray,
    block_sites: np.ndarray,
    patch_ids: np.ndarray,
    patch_values: np.ndarray,
    lookup_values: np.ndarray,
    reverse_centers: np.ndarray,
    reverse_bits: np.ndarray,
    rng: np.random.Generator,
    block_size: int,
    sweeps: int,
) -> tuple[int, int]:
    length = spins.shape[0]
    final_length = level1_spins.shape[0] if rg_levels == 1 else level2_spins.shape[0]
    n_operators = couplings.shape[0]
    delta_micro = np.zeros(n_operators, dtype=np.int64)
    delta_block = np.zeros(n_operators, dtype=np.int64)
    proposed_ids = np.empty(9, dtype=np.int64)
    proposed_values = np.empty(9, dtype=np.float64)
    attempted = sweeps * length * length
    accepted = 0

    for _ in range(attempted):
        x = rng.integers(0, length)
        y = rng.integers(0, length)
        site = x * length + y
        for operator_index in range(n_operators):
            delta_micro[operator_index] = 0
            delta_block[operator_index] = 0
        for entry in range(micro_offsets[site], micro_offsets[site + 1]):
            product = 1
            for vertex in range(micro_arities[entry]):
                flat_site = micro_sites[entry, vertex]
                sx = flat_site // length
                sy = flat_site - sx * length
                product *= spins[sx, sy]
            delta_micro[micro_operators[entry]] += 2 * product

        old_micro = spins[x, y]
        level1_x = x // block_size
        level1_y = y // block_size
        old_level1 = level1_spins[level1_x, level1_y]
        new_level1_sum = level1_sums[level1_x, level1_y] - 2 * old_micro
        new_level1 = 1 if new_level1_sum > 0 else -1

        final_changed = False
        final_x = level1_x
        final_y = level1_y
        new_level2_sum = 0
        old_level2 = 0
        new_level2 = 0
        if rg_levels == 1:
            final_changed = new_level1 != old_level1
        elif new_level1 != old_level1:
            level2_x = level1_x // block_size
            level2_y = level1_y // block_size
            old_level2 = level2_spins[level2_x, level2_y]
            new_level2_sum = level2_sums[level2_x, level2_y] - 2 * old_level1
            new_level2 = 1 if new_level2_sum > 0 else -1
            final_x = level2_x
            final_y = level2_y
            final_changed = new_level2 != old_level2

        delta_residual = 0.0
        if final_changed:
            final_site = final_x * final_length + final_y
            for entry in range(block_offsets[final_site], block_offsets[final_site + 1]):
                product = 1
                for vertex in range(block_arities[entry]):
                    flat_site = block_sites[entry, vertex]
                    sx = flat_site // final_length
                    sy = flat_site - sx * final_length
                    final_spins = level1_spins if rg_levels == 1 else level2_spins
                    product *= final_spins[sx, sy]
                delta_block[block_operators[entry]] += 2 * product
            for affected in range(9):
                center = reverse_centers[final_site, affected]
                bit = reverse_bits[final_site, affected]
                new_id = patch_ids[center] ^ (1 << bit)
                new_value = lookup_values[new_id]
                proposed_ids[affected] = new_id
                proposed_values[affected] = new_value
                delta_residual += new_value - patch_values[center]

        delta_h = alpha * delta_residual
        for operator_index in range(n_operators):
            delta_h += couplings[operator_index] * delta_micro[operator_index]
            delta_h += linear_bias[operator_index] * delta_block[operator_index]
        draw = rng.random()
        if delta_h > 0.0 and np.log(draw) >= -delta_h:
            continue

        spins[x, y] = -old_micro
        level1_sums[level1_x, level1_y] = new_level1_sum
        if new_level1 != old_level1:
            level1_spins[level1_x, level1_y] = new_level1
            if rg_levels == 2:
                level2_x = final_x
                level2_y = final_y
                level2_sums[level2_x, level2_y] = new_level2_sum
                if new_level2 != old_level2:
                    level2_spins[level2_x, level2_y] = new_level2
        for operator_index in range(n_operators):
            micro_values[operator_index] += delta_micro[operator_index]
            block_values[operator_index] += delta_block[operator_index]
        if final_changed:
            final_site = final_x * final_length + final_y
            for affected in range(9):
                center = reverse_centers[final_site, affected]
                patch_ids[center] = proposed_ids[affected]
                patch_values[center] = proposed_values[affected]
        accepted += 1
    return attempted, accepted


@dataclass(frozen=True)
class MPSProposalDelta:
    delta_micro: np.ndarray
    delta_linear_bias: np.ndarray
    delta_residual: float
    delta_hamiltonian: float
    rg_proposal: MajorityRGProposal
    patch_proposal: PatchEnergyProposal | None


class MPSBiasedMetropolis:
    """Sample ``K.S(sigma) + J.S(mu) + alpha R_MPS(mu)`` exactly locally."""

    def __init__(
        self,
        lattice: IsingLattice,
        couplings: np.ndarray,
        linear_bias: np.ndarray,
        alpha: float,
        lookup: PatchLookupTable,
        rng: np.random.Generator,
        shapes: tuple[OperatorShape, ...],
        block_size: int = 3,
        rg_levels: int = 1,
        compiled: bool = True,
        micro_basis: OperatorBasis | None = None,
        block_basis: OperatorBasis | None = None,
    ) -> None:
        self.lattice = lattice
        self.couplings = np.asarray(couplings, dtype=np.float64).copy()
        self.linear_bias = np.asarray(linear_bias, dtype=np.float64).copy()
        self.alpha = float(alpha)
        self.lookup = lookup
        self.rng = rng
        self.shapes = tuple(shapes)
        self.block_size = int(block_size)
        self.rg_levels = int(rg_levels)
        self.compiled = bool(compiled)
        if self.couplings.shape != (len(self.shapes),):
            raise ValueError("couplings have the wrong shape")
        if self.linear_bias.shape != self.couplings.shape:
            raise ValueError("linear_bias has the wrong shape")
        if not np.isfinite(self.alpha):
            raise ValueError("alpha must be finite")

        self.rg_state = MajorityRGState(
            lattice.spins,
            block_size=self.block_size,
            levels=self.rg_levels,
        )
        coarse_length = self.rg_state.coarse_spins.shape[0]
        self.micro_basis = micro_basis or OperatorBasis(lattice.length, self.shapes)
        self.block_basis = block_basis or OperatorBasis(coarse_length, self.shapes)
        self.micro_incidence = self.micro_basis.packed_incidence()
        self.block_incidence = self.block_basis.packed_incidence()
        self.micro_values = self.micro_basis.values(self.lattice.spins)
        self.block_values = self.block_basis.values(self.rg_state.coarse_spins)
        self.patch_cache = PatchEnergyCache(self.rg_state.coarse_spins, lookup)
        self.attempted = 0
        self.accepted = 0

    @property
    def effective_hamiltonian(self) -> float:
        return float(
            self.couplings @ self.micro_values
            + self.linear_bias @ self.block_values
            + self.alpha * self.patch_cache.energy
        )

    @property
    def acceptance_rate(self) -> float:
        return self.accepted / self.attempted if self.attempted else 0.0

    def proposal_delta(self, x: int, y: int) -> MPSProposalDelta:
        delta_micro = self.micro_basis.delta_for_flip(self.lattice.spins, x, y)
        rg_proposal = self.rg_state.proposal(x, y)
        delta_linear = np.zeros(len(self.shapes), dtype=np.int64)
        patch_proposal = None
        delta_residual = 0.0
        if rg_proposal.final_changed:
            final_site = rg_proposal.final_site
            if final_site is None:
                raise AssertionError("changed RG proposal has no final site")
            final_x, final_y = final_site
            delta_linear = self.block_basis.delta_for_flip(
                self.rg_state.coarse_spins, final_x, final_y
            )
            patch_proposal = self.patch_cache.proposal(final_x, final_y)
            delta_residual = patch_proposal.delta_energy
        delta_h = float(
            self.couplings @ delta_micro
            + self.linear_bias @ delta_linear
            + self.alpha * delta_residual
        )
        return MPSProposalDelta(
            delta_micro=delta_micro,
            delta_linear_bias=delta_linear,
            delta_residual=delta_residual,
            delta_hamiltonian=delta_h,
            rg_proposal=rg_proposal,
            patch_proposal=patch_proposal,
        )

    def attempt_flip(self, x: int, y: int, uniform: float | None = None) -> bool:
        proposal = self.proposal_delta(x, y)
        draw = float(self.rng.random()) if uniform is None else float(uniform)
        self.attempted += 1
        accept = proposal.delta_hamiltonian <= 0.0 or (
            draw > 0.0 and np.log(draw) < -proposal.delta_hamiltonian
        )
        if not accept:
            return False
        if proposal.patch_proposal is not None:
            self.patch_cache.commit(proposal.patch_proposal)
        self.rg_state.commit(proposal.rg_proposal)
        self.micro_values += proposal.delta_micro
        self.block_values += proposal.delta_linear_bias
        self.accepted += 1
        return True

    def sweep(self) -> None:
        length = self.lattice.length
        for _ in range(self.lattice.n_sites):
            self.attempt_flip(
                int(self.rng.integers(length)),
                int(self.rng.integers(length)),
            )

    def run_sweeps(self, sweeps: int) -> None:
        if sweeps <= 0:
            raise ValueError("sweeps must be positive")
        if not self.compiled:
            for _ in range(sweeps):
                self.sweep()
            return
        if self.rg_levels == 1:
            level2_sums = np.zeros((1, 1), dtype=np.int64)
            level2_spins = np.ones((1, 1), dtype=np.int8)
        else:
            level2_sums = self.rg_state.level_sums[1]
            level2_spins = self.rg_state.level_spins[1]
        attempted, accepted = _compiled_mps_sweeps(
            self.lattice.spins,
            self.rg_state.level_sums[0],
            self.rg_state.level_spins[0],
            level2_sums,
            level2_spins,
            self.rg_levels,
            self.micro_values,
            self.block_values,
            self.couplings,
            self.linear_bias,
            self.alpha,
            *self.micro_incidence,
            *self.block_incidence,
            self.patch_cache.pattern_ids.reshape(-1),
            self.patch_cache.values.reshape(-1),
            self.lookup.values,
            self.patch_cache.geometry.reverse_centers,
            self.patch_cache.geometry.reverse_bits,
            self.rng,
            self.block_size,
            sweeps,
        )
        self.patch_cache.histogram[:] = np.bincount(
            self.patch_cache.pattern_ids.reshape(-1), minlength=512
        )
        self.attempted += int(attempted)
        self.accepted += int(accepted)

    def set_bias(
        self,
        linear_bias: np.ndarray,
        alpha: float,
        lookup: PatchLookupTable,
    ) -> None:
        supplied = np.asarray(linear_bias, dtype=np.float64)
        if supplied.shape != self.linear_bias.shape:
            raise ValueError("linear_bias has the wrong shape")
        if not np.isfinite(alpha):
            raise ValueError("alpha must be finite")
        self.linear_bias[:] = supplied
        self.alpha = float(alpha)
        self.lookup = lookup
        self.patch_cache.refresh_lookup(lookup)

    def assert_cache_consistent(self) -> None:
        self.rg_state.assert_consistent()
        np.testing.assert_array_equal(
            self.micro_values, self.micro_basis.values(self.lattice.spins)
        )
        np.testing.assert_array_equal(
            self.block_values, self.block_basis.values(self.rg_state.coarse_spins)
        )
        self.patch_cache.assert_consistent()
