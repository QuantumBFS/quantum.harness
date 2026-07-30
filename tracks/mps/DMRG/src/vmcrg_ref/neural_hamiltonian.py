"""Neural-to-neural microscopic Hamiltonian and dual-cache sampler."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numba import njit

from .blockspin import block_majority, block_sums
from .neural_energy import (
    D4EvenLocalMLP,
    LocalEnergyCache,
    LocalEnergyProposal,
)


@njit(cache=True, nogil=True, inline="always")
def _compiled_density(
    features: np.ndarray,
    feature_permutations: np.ndarray,
    weight_in: np.ndarray,
    bias_hidden: np.ndarray,
    weight_out: np.ndarray,
) -> float:
    value = 0.0
    for symmetry in range(feature_permutations.shape[0]):
        for hidden in range(weight_out.shape[0]):
            plus = bias_hidden[hidden]
            minus = bias_hidden[hidden]
            for feature in range(features.shape[0]):
                source = feature_permutations[symmetry, feature]
                contribution = weight_in[hidden, feature] * features[source]
                plus += contribution
                minus -= contribution
            value += 0.5 * (np.tanh(plus) + np.tanh(minus)) * weight_out[hidden]
    return value / feature_permutations.shape[0]


@njit(cache=True, nogil=True)
def _compiled_neural_to_neural_proposals(
    spins: np.ndarray,
    cached_block_sums: np.ndarray,
    cached_block_spins: np.ndarray,
    micro_features: np.ndarray,
    micro_density: np.ndarray,
    micro_z_plus: np.ndarray,
    micro_z_minus: np.ndarray,
    micro_dx: np.ndarray,
    micro_dy: np.ndarray,
    micro_feature: np.ndarray,
    micro_counts: np.ndarray,
    micro_permutations: np.ndarray,
    micro_weight_in: np.ndarray,
    micro_bias_hidden: np.ndarray,
    micro_weight_out: np.ndarray,
    bias_features: np.ndarray,
    bias_density: np.ndarray,
    bias_z_plus: np.ndarray,
    bias_z_minus: np.ndarray,
    bias_dx: np.ndarray,
    bias_dy: np.ndarray,
    bias_feature: np.ndarray,
    bias_counts: np.ndarray,
    bias_permutations: np.ndarray,
    bias_weight_in: np.ndarray,
    bias_bias_hidden: np.ndarray,
    bias_weight_out: np.ndarray,
    sites: np.ndarray,
    uniforms: np.ndarray,
    block_size: int,
) -> int:
    length = spins.shape[0]
    coarse = cached_block_spins.shape[0]
    micro_proposed = np.empty(micro_dx.size, dtype=np.float64)
    bias_proposed = np.empty(bias_dx.size, dtype=np.float64)
    micro_workspace = np.empty(micro_features.shape[2], dtype=np.float64)
    bias_workspace = np.empty(bias_features.shape[2], dtype=np.float64)
    accepted = 0
    for attempt in range(sites.shape[0]):
        x = sites[attempt, 0]
        y = sites[attempt, 1]
        old_spin = spins[x, y]
        delta_total = 0.0

        for affected in range(micro_dx.size):
            cx = (x - micro_dx[affected]) % length
            cy = (y - micro_dy[affected]) % length
            changed_feature = micro_feature[affected]
            for feature in range(micro_workspace.size):
                micro_workspace[feature] = micro_features[cx, cy, feature]
            micro_workspace[changed_feature] += (
                -2.0 * old_spin / micro_counts[changed_feature]
            )
            new_value = _compiled_density(
                micro_workspace,
                micro_permutations,
                micro_weight_in,
                micro_bias_hidden,
                micro_weight_out,
            )
            micro_proposed[affected] = new_value
            delta_total -= new_value - micro_density[cx, cy]

        bx = x // block_size
        by = y // block_size
        old_block_spin = cached_block_spins[bx, by]
        new_block_sum = cached_block_sums[bx, by] - 2 * old_spin
        new_block_spin = 1 if new_block_sum > 0 else -1
        block_changed = new_block_spin != old_block_spin
        if block_changed:
            for affected in range(bias_dx.size):
                cx = (bx - bias_dx[affected]) % coarse
                cy = (by - bias_dy[affected]) % coarse
                changed_feature = bias_feature[affected]
                for feature in range(bias_workspace.size):
                    bias_workspace[feature] = bias_features[cx, cy, feature]
                bias_workspace[changed_feature] += (
                    -2.0 * old_block_spin / bias_counts[changed_feature]
                )
                new_value = _compiled_density(
                    bias_workspace,
                    bias_permutations,
                    bias_weight_in,
                    bias_bias_hidden,
                    bias_weight_out,
                )
                bias_proposed[affected] = new_value
                delta_total += new_value - bias_density[cx, cy]

        if delta_total > 0.0 and uniforms[attempt] >= np.exp(-delta_total):
            continue

        for affected in range(micro_dx.size):
            cx = (x - micro_dx[affected]) % length
            cy = (y - micro_dy[affected]) % length
            feature = micro_feature[affected]
            delta = -2.0 * old_spin / micro_counts[feature]
            micro_features[cx, cy, feature] += delta
            for hidden in range(micro_weight_out.size):
                micro_z_plus[cx, cy, hidden] += micro_weight_in[hidden, feature] * delta
                micro_z_minus[cx, cy, hidden] -= micro_weight_in[hidden, feature] * delta
            micro_density[cx, cy] = micro_proposed[affected]
        spins[x, y] = -old_spin
        cached_block_sums[bx, by] = new_block_sum
        if block_changed:
            for affected in range(bias_dx.size):
                cx = (bx - bias_dx[affected]) % coarse
                cy = (by - bias_dy[affected]) % coarse
                feature = bias_feature[affected]
                delta = -2.0 * old_block_spin / bias_counts[feature]
                bias_features[cx, cy, feature] += delta
                for hidden in range(bias_weight_out.size):
                    bias_z_plus[cx, cy, hidden] += bias_weight_in[hidden, feature] * delta
                    bias_z_minus[cx, cy, hidden] -= bias_weight_in[hidden, feature] * delta
                bias_density[cx, cy] = bias_proposed[affected]
            cached_block_spins[bx, by] = new_block_spin
        accepted += 1
    return accepted


@dataclass(frozen=True)
class NeuralHamiltonianProposal:
    local: LocalEnergyProposal
    delta_energy: float


class NeuralHamiltonian:
    """Frozen microscopic Hamiltonian ``U_next = -V_frozen``."""

    def __init__(self, model: D4EvenLocalMLP, spins: np.ndarray) -> None:
        self.model = model.copy()
        self.spins = np.asarray(spins, dtype=np.int8)
        if self.spins.ndim != 2 or self.spins.shape[0] != self.spins.shape[1]:
            raise ValueError("neural microscopic spins must be a square array")
        if not np.all((self.spins == -1) | (self.spins == 1)):
            raise ValueError("neural microscopic spins must contain only -1 and +1")
        self.cache = LocalEnergyCache(self.model, self.spins)
        self.cache.force_direct_evaluation()

    @property
    def energy(self) -> float:
        return -self.cache.energy

    def full_energy(self, spins: np.ndarray) -> float:
        return -self.model.energy(spins)

    def proposal(self, x: int, y: int) -> NeuralHamiltonianProposal:
        local = self.cache.proposal(x, y)
        return NeuralHamiltonianProposal(local=local, delta_energy=-local.delta_energy)

    def commit(self, proposal: NeuralHamiltonianProposal) -> None:
        self.cache.commit(proposal.local)
        self.spins[proposal.local.x, proposal.local.y] *= -1

    def assert_consistent(self, atol: float = 1e-10) -> None:
        self.cache.assert_consistent()
        if abs(self.energy - self.full_energy(self.spins)) > atol:
            raise AssertionError("neural microscopic cache energy drifted")


@dataclass(frozen=True)
class NeuralToNeuralProposal:
    x: int
    y: int
    old_spin: int
    microscopic: NeuralHamiltonianProposal
    coarse: LocalEnergyProposal | None
    new_block_sum: int
    new_block_spin: int
    delta_microscopic: float
    delta_bias: float
    delta_total: float


class NeuralToNeuralBiasedMetropolis:
    """Metropolis sampler for ``-V_prev(sigma) + V_current(tau(sigma))``."""

    def __init__(
        self,
        spins: np.ndarray,
        microscopic_model: D4EvenLocalMLP,
        bias_model: D4EvenLocalMLP,
        rng: np.random.Generator,
        block_size: int = 3,
        compiled: bool = True,
    ) -> None:
        values = np.asarray(spins, dtype=np.int8)
        if values.ndim != 2 or values.shape[0] != values.shape[1]:
            raise ValueError("neural-to-neural spins must be a square array")
        if values.shape[0] % block_size:
            raise ValueError("lattice length must be divisible by block_size")
        if block_size <= 0 or block_size % 2 == 0:
            raise ValueError("block_size must be a positive odd integer")
        self.spins = values.copy()
        self.rng = rng
        self.block_size = int(block_size)
        self.compiled = bool(compiled)
        self.microscopic = NeuralHamiltonian(microscopic_model, self.spins)
        self.bias_model = bias_model.copy()
        self.block_sums = block_sums(self.spins, self.block_size)
        self.block_spins = block_majority(self.spins, self.block_size)
        self.bias_cache = LocalEnergyCache(self.bias_model, self.block_spins)
        self.bias_cache.force_direct_evaluation()
        self.fixed_linear_bias = np.zeros(13, dtype=np.float64)
        self.fixed_linear_bias.setflags(write=False)
        self.attempted = 0
        self.accepted = 0
        self._micro_patch = self._patch_arrays(self.microscopic.cache)
        self._bias_patch = self._patch_arrays(self.bias_cache)

    @staticmethod
    def _patch_arrays(
        cache: LocalEnergyCache,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        return (
            np.asarray([item[0] for item in cache.patch_offsets], dtype=np.int32),
            np.asarray([item[1] for item in cache.patch_offsets], dtype=np.int32),
            np.asarray([item[2] for item in cache.patch_offsets], dtype=np.int32),
        )

    @property
    def length(self) -> int:
        return int(self.spins.shape[0])

    @property
    def effective_energy(self) -> float:
        return self.microscopic.energy + self.bias_cache.energy

    @property
    def acceptance_rate(self) -> float:
        return self.accepted / self.attempted if self.attempted else 0.0

    def full_effective_energy(self, spins: np.ndarray) -> float:
        values = np.asarray(spins, dtype=np.int8)
        coarse = block_majority(values, self.block_size)
        return self.microscopic.full_energy(values) + self.bias_model.energy(coarse)

    def proposal_delta(self, x: int, y: int) -> NeuralToNeuralProposal:
        x %= self.length
        y %= self.length
        microscopic = self.microscopic.proposal(x, y)
        old_spin = int(self.spins[x, y])
        bx, by = x // self.block_size, y // self.block_size
        old_block_spin = int(self.block_spins[bx, by])
        new_block_sum = int(self.block_sums[bx, by] - 2 * old_spin)
        if new_block_sum == 0:
            raise AssertionError("odd majority blocks cannot tie")
        new_block_spin = 1 if new_block_sum > 0 else -1
        coarse = None
        delta_bias = 0.0
        if new_block_spin != old_block_spin:
            coarse = self.bias_cache.proposal(bx, by)
            delta_bias = coarse.delta_energy
        delta_total = microscopic.delta_energy + delta_bias
        return NeuralToNeuralProposal(
            x=x,
            y=y,
            old_spin=old_spin,
            microscopic=microscopic,
            coarse=coarse,
            new_block_sum=new_block_sum,
            new_block_spin=new_block_spin,
            delta_microscopic=microscopic.delta_energy,
            delta_bias=delta_bias,
            delta_total=delta_total,
        )

    def _commit(self, proposal: NeuralToNeuralProposal) -> None:
        if int(self.spins[proposal.x, proposal.y]) != proposal.old_spin:
            raise AssertionError("microscopic spin changed before proposal commit")
        self.microscopic.commit(proposal.microscopic)
        bx, by = proposal.x // self.block_size, proposal.y // self.block_size
        self.block_sums[bx, by] = proposal.new_block_sum
        if proposal.coarse is not None:
            self.bias_cache.commit(proposal.coarse)
            self.block_spins[bx, by] = proposal.new_block_spin

    def attempt_flip(self, x: int, y: int, uniform: float | None = None) -> bool:
        proposal = self.proposal_delta(x, y)
        draw = float(self.rng.random()) if uniform is None else float(uniform)
        if not 0.0 <= draw < 1.0:
            raise ValueError("Metropolis uniform draw must lie in [0, 1)")
        self.attempted += 1
        if proposal.delta_total > 0.0 and draw >= np.exp(-proposal.delta_total):
            return False
        self._commit(proposal)
        self.accepted += 1
        return True

    def run_proposals_with_stream(
        self,
        sites: np.ndarray,
        uniforms: np.ndarray,
    ) -> None:
        site_values = np.asarray(sites, dtype=np.int64)
        draw_values = np.asarray(uniforms, dtype=np.float64)
        if site_values.ndim != 2 or site_values.shape[1] != 2:
            raise ValueError("proposal sites must have shape (count, 2)")
        if draw_values.shape != (site_values.shape[0],):
            raise ValueError("proposal uniforms have the wrong shape")
        if np.any(site_values < 0) or np.any(site_values >= self.length):
            raise ValueError("proposal site lies outside the lattice")
        if np.any(draw_values < 0.0) or np.any(draw_values >= 1.0) or not np.all(
            np.isfinite(draw_values)
        ):
            raise ValueError("proposal uniforms must be finite values in [0, 1)")
        if self.compiled:
            accepted = _compiled_neural_to_neural_proposals(
                self.spins,
                self.block_sums,
                self.block_spins,
                self.microscopic.cache.features,
                self.microscopic.cache.density,
                self.microscopic.cache.z_plus,
                self.microscopic.cache.z_minus,
                *self._micro_patch,
                self.microscopic.model.shell_counts,
                self.microscopic.model.feature_permutations,
                self.microscopic.model.weight_in,
                self.microscopic.model.bias_hidden,
                self.microscopic.model.weight_out,
                self.bias_cache.features,
                self.bias_cache.density,
                self.bias_cache.z_plus,
                self.bias_cache.z_minus,
                *self._bias_patch,
                self.bias_model.shell_counts,
                self.bias_model.feature_permutations,
                self.bias_model.weight_in,
                self.bias_model.bias_hidden,
                self.bias_model.weight_out,
                site_values,
                draw_values,
                self.block_size,
            )
            self.attempted += int(site_values.shape[0])
            self.accepted += int(accepted)
            return
        for (x, y), draw in zip(site_values, draw_values):
            self.attempt_flip(int(x), int(y), float(draw))

    def run_proposals(self, proposals: int) -> None:
        if proposals <= 0:
            raise ValueError("proposal count must be positive")
        sites = self.rng.integers(0, self.length, size=(proposals, 2), dtype=np.int64)
        uniforms = self.rng.random(proposals)
        self.run_proposals_with_stream(sites, uniforms)

    def run_sweeps(self, sweeps: int) -> None:
        if sweeps <= 0:
            raise ValueError("sweeps must be positive")
        self.run_proposals(sweeps * self.length * self.length)

    def refresh_bias_model(self, model: D4EvenLocalMLP) -> None:
        """Install updated bias parameters without changing the Markov state."""
        self.bias_model = model.copy()
        self.bias_cache = LocalEnergyCache(self.bias_model, self.block_spins)
        self.bias_cache.force_direct_evaluation()
        self._bias_patch = self._patch_arrays(self.bias_cache)

    def assert_cache_consistent(self, atol: float = 1e-10) -> None:
        np.testing.assert_array_equal(
            self.block_sums,
            block_sums(self.spins, self.block_size),
        )
        np.testing.assert_array_equal(
            self.block_spins,
            block_majority(self.spins, self.block_size),
        )
        self.microscopic.assert_consistent(atol=atol)
        self.bias_cache.assert_consistent()
        residual = abs(self.effective_energy - self.full_effective_energy(self.spins))
        if residual > atol:
            raise AssertionError(
                f"neural-to-neural effective energy cache drifted by {residual}"
            )
