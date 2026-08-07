"""混合神经 VMCRG 的 Metropolis 采样器和变分优化器。

实现声明
--------
采样器严格使用

    Delta H_eff = K.Delta S_micro + J.Delta S_block + Delta V_theta
    p_accept = min(1, exp(-Delta H_eff)).

只有所属 3x3 块的多数自旋改变时，才更新块算符和神经局域能量。
优化器使用论文变分目标对应的梯度

    grad Omega = <dV/dtheta>_target - <dV/dtheta>_biased,

并由多个独立 walker 估计 biased 项、由均匀块自旋参考分布估计 target 项。
均匀参考分布是 VMCRG 的采样参考，不是微观 Ising 模型的物理温度。
这里没有事后拟合或结果修补；轨迹平均是在运行前固定的后半段执行。
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from typing import Callable, Protocol

import numpy as np
from numba import njit

from .blockspin import block_majority, block_sums
from .ising import IsingLattice, nearest_neighbor_operator
from .local_execution import resolve_worker_limit
from .neural_energy import D4EvenLocalMLP, LocalEnergyCache, LocalEnergyProposal, MLPGradient
from .operators import OperatorBasis, OperatorShape
from .training_protocol import (
    PolyakAverager,
    TrainingProtocol,
    TrainingStopState,
    TrainingWindow,
    clip_mlp_gradient,
    model_parameters_finite,
)


__all__ = [
    "Adam",
    "HybridNeuralVMCRGOptimizer",
    "HybridProposalDelta",
    "LinearNeuralBiasedMetropolis",
    "NeuralOptimizationRecord",
    "ReferenceDistribution2D",
    "RobbinsMonroSGD",
    "UniformIsingReference2D",
]


def _gradient_difference(target: MLPGradient, biased: MLPGradient) -> MLPGradient:
    return MLPGradient(
        target.weight_in - biased.weight_in,
        target.bias_hidden - biased.bias_hidden,
        target.weight_out - biased.weight_out,
    )


def _zero_gradient(model: D4EvenLocalMLP) -> MLPGradient:
    return MLPGradient(
        np.zeros_like(model.weight_in),
        np.zeros_like(model.bias_hidden),
        np.zeros_like(model.weight_out),
    )


def _add_gradient(total: MLPGradient, value: MLPGradient) -> None:
    total.weight_in += value.weight_in
    total.bias_hidden += value.bias_hidden
    total.weight_out += value.weight_out


def _scale_gradient(value: MLPGradient, scale: float) -> MLPGradient:
    return MLPGradient(
        value.weight_in * scale,
        value.bias_hidden * scale,
        value.weight_out * scale,
    )


@dataclass(frozen=True)
class NeuralOptimizationRecord:
    step: int
    gradient_norm: float
    learning_rate: float
    biased_energy_per_site: float
    target_energy_per_site: float
    biased_nn_per_site: float
    target_nn_per_site: float
    acceptance_rate: float
    unclipped_gradient_norm: float = 0.0
    clipped_gradient_norm: float = 0.0
    stop_reason: str = ""


class ReferenceDistribution2D(Protocol):
    """Normalized 2D block-spin reference used by the variational objective.

    A sampler alone is insufficient for a non-uniform reference: reconstructing
    the renormalized Hamiltonian requires

        H'(mu) = -V_min(mu) - log p_ref(mu) + constant.

    Requiring ``log_probability`` prevents an arbitrary data generator from
    silently being treated as the paper's uniform reference distribution.
    """

    name: str

    def sample(
        self, rng: np.random.Generator, samples: int, length: int
    ) -> np.ndarray: ...

    def log_probability(self, spins: np.ndarray) -> np.ndarray: ...


@dataclass(frozen=True)
class UniformIsingReference2D:
    """Independent uniform Ising spins, the reference used in the paper."""

    name: str = "uniform_independent_ising_2d"

    def sample(
        self, rng: np.random.Generator, samples: int, length: int
    ) -> np.ndarray:
        if samples <= 0 or length <= 0:
            raise ValueError("samples and length must be positive")
        values = rng.integers(0, 2, size=(samples, length, length), dtype=np.int8)
        return 2 * values - 1

    def log_probability(self, spins: np.ndarray) -> np.ndarray:
        values = np.asarray(spins)
        if values.ndim != 3:
            raise ValueError("reference spins must have shape (samples, L, L)")
        if values.shape[1] != values.shape[2] or values.shape[1] <= 0:
            raise ValueError("reference spins must lie on nonempty square lattices")
        if not np.all((values == -1) | (values == 1)):
            raise ValueError("reference spins must contain only -1 and +1")
        log_weight = -(values.shape[1] * values.shape[2]) * np.log(2.0)
        return np.full(values.shape[0], log_weight, dtype=np.float64)


class Adam:
    def __init__(
        self,
        model: D4EvenLocalMLP,
        learning_rate: float,
        beta1: float = 0.9,
        beta2: float = 0.999,
        epsilon: float = 1e-8,
    ) -> None:
        if learning_rate <= 0.0:
            raise ValueError("learning_rate must be positive")
        self.learning_rate = float(learning_rate)
        self.beta1 = float(beta1)
        self.beta2 = float(beta2)
        self.epsilon = float(epsilon)
        self.step_index = 0
        self.m = MLPGradient(
            np.zeros_like(model.weight_in),
            np.zeros_like(model.bias_hidden),
            np.zeros_like(model.weight_out),
        )
        self.v = self.m.copy()

    def update(self, model: D4EvenLocalMLP, gradient: MLPGradient) -> float:
        self.step_index += 1
        correction1 = 1.0 - self.beta1**self.step_index
        correction2 = 1.0 - self.beta2**self.step_index
        fields = (
            (model.weight_in, gradient.weight_in, self.m.weight_in, self.v.weight_in),
            (
                model.bias_hidden,
                gradient.bias_hidden,
                self.m.bias_hidden,
                self.v.bias_hidden,
            ),
            (
                model.weight_out,
                gradient.weight_out,
                self.m.weight_out,
                self.v.weight_out,
            ),
        )
        for parameter, grad, first, second in fields:
            first *= self.beta1
            first += (1.0 - self.beta1) * grad
            second *= self.beta2
            second += (1.0 - self.beta2) * grad**2
            parameter -= self.learning_rate * (first / correction1) / (
                np.sqrt(second / correction2) + self.epsilon
            )
        return self.learning_rate


class RobbinsMonroSGD:
    """Plain SGD with a stochastic-approximation learning-rate schedule.

    The exponent is restricted to ``0.5 < power <= 1``.  Consequently,
    ``sum_t eta_t`` diverges while ``sum_t eta_t**2`` converges, which prevents
    a fixed-size random walk when the gradient estimate reaches its noise
    floor.  No coordinate-wise division by the estimated gradient variance is
    performed.
    """

    def __init__(
        self,
        initial_learning_rate: float,
        decay_scale: float,
        decay_power: float,
    ) -> None:
        if initial_learning_rate <= 0.0:
            raise ValueError("initial_learning_rate must be positive")
        if decay_scale <= 0.0:
            raise ValueError("decay_scale must be positive")
        if not 0.5 < decay_power <= 1.0:
            raise ValueError("decay_power must lie in (0.5, 1]")
        self.initial_learning_rate = float(initial_learning_rate)
        self.decay_scale = float(decay_scale)
        self.decay_power = float(decay_power)
        self.step_index = 0

    @property
    def learning_rate(self) -> float:
        return self.initial_learning_rate / (
            1.0 + self.step_index / self.decay_scale
        ) ** self.decay_power

    def update(self, model: D4EvenLocalMLP, gradient: MLPGradient) -> float:
        learning_rate = self.learning_rate
        model.weight_in -= learning_rate * gradient.weight_in
        model.bias_hidden -= learning_rate * gradient.bias_hidden
        model.weight_out -= learning_rate * gradient.weight_out
        self.step_index += 1
        return learning_rate


@njit(cache=True, nogil=True, inline="always")
def _d4_even_density(
    features: np.ndarray,
    feature_permutations: np.ndarray,
    weight_in: np.ndarray,
    bias_hidden: np.ndarray,
    weight_out: np.ndarray,
) -> float:
    """D4- and Z2-even local MLP density for one feature vector."""

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
def _compiled_hybrid_sweeps_direct(
    spins: np.ndarray,
    cached_block_sums: np.ndarray,
    cached_block_spins: np.ndarray,
    micro_values: np.ndarray,
    block_values: np.ndarray,
    couplings: np.ndarray,
    linear_bias: np.ndarray,
    micro_offsets: np.ndarray,
    micro_operators: np.ndarray,
    micro_arities: np.ndarray,
    micro_sites: np.ndarray,
    block_offsets: np.ndarray,
    block_operators: np.ndarray,
    block_arities: np.ndarray,
    block_sites: np.ndarray,
    neural_features: np.ndarray,
    neural_density: np.ndarray,
    patch_dx: np.ndarray,
    patch_dy: np.ndarray,
    patch_feature: np.ndarray,
    shell_counts: np.ndarray,
    feature_permutations: np.ndarray,
    weight_in: np.ndarray,
    bias_hidden: np.ndarray,
    weight_out: np.ndarray,
    rng: np.random.Generator,
    block_size: int,
    sweeps: int,
) -> tuple[int, int]:
    """Compiled exact sampler for a direct-evaluation D4-even MLP."""

    length = spins.shape[0]
    coarse = cached_block_spins.shape[0]
    n_operators = couplings.shape[0]
    n_affected = patch_dx.shape[0]
    n_features = neural_features.shape[2]
    delta_micro = np.zeros(n_operators, dtype=np.int64)
    delta_block = np.zeros(n_operators, dtype=np.int64)
    proposed_density = np.empty(n_affected, dtype=np.float64)
    proposed_features = np.empty(n_features, dtype=np.float64)
    accepted = 0
    attempted = sweeps * length * length

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

        old_spin = spins[x, y]
        bx = x // block_size
        by = y // block_size
        block_site = bx * coarse + by
        old_block_spin = cached_block_spins[bx, by]
        new_block_sum = cached_block_sums[bx, by] - 2 * old_spin
        new_block_spin = 1 if new_block_sum > 0 else -1
        delta_neural = 0.0

        if new_block_spin != old_block_spin:
            for entry in range(block_offsets[block_site], block_offsets[block_site + 1]):
                product = 1
                for vertex in range(block_arities[entry]):
                    flat_site = block_sites[entry, vertex]
                    sx = flat_site // coarse
                    sy = flat_site - sx * coarse
                    product *= cached_block_spins[sx, sy]
                delta_block[block_operators[entry]] += 2 * product

            for affected in range(n_affected):
                cx = (bx - patch_dx[affected]) % coarse
                cy = (by - patch_dy[affected]) % coarse
                changed_feature = patch_feature[affected]
                for feature in range(n_features):
                    proposed_features[feature] = neural_features[cx, cy, feature]
                proposed_features[changed_feature] += (
                    -2.0 * old_block_spin / shell_counts[changed_feature]
                )
                new_value = _d4_even_density(
                    proposed_features,
                    feature_permutations,
                    weight_in,
                    bias_hidden,
                    weight_out,
                )
                proposed_density[affected] = new_value
                delta_neural += new_value - neural_density[cx, cy]

        delta_h = delta_neural
        for operator_index in range(n_operators):
            delta_h += couplings[operator_index] * delta_micro[operator_index]
            delta_h += linear_bias[operator_index] * delta_block[operator_index]
        draw = rng.random()
        if delta_h > 0.0 and draw >= np.exp(-delta_h):
            continue

        spins[x, y] = -old_spin
        cached_block_sums[bx, by] = new_block_sum
        for operator_index in range(n_operators):
            micro_values[operator_index] += delta_micro[operator_index]
            block_values[operator_index] += delta_block[operator_index]
        if new_block_spin != old_block_spin:
            for affected in range(n_affected):
                cx = (bx - patch_dx[affected]) % coarse
                cy = (by - patch_dy[affected]) % coarse
                feature = patch_feature[affected]
                neural_features[cx, cy, feature] += (
                    -2.0 * old_block_spin / shell_counts[feature]
                )
                neural_density[cx, cy] = proposed_density[affected]
            cached_block_spins[bx, by] = new_block_spin
        accepted += 1
    return attempted, accepted


@njit(cache=True, nogil=True)
def _compiled_hybrid_sweeps(
    spins: np.ndarray,
    cached_block_sums: np.ndarray,
    cached_block_spins: np.ndarray,
    micro_values: np.ndarray,
    block_values: np.ndarray,
    couplings: np.ndarray,
    linear_bias: np.ndarray,
    micro_offsets: np.ndarray,
    micro_operators: np.ndarray,
    micro_arities: np.ndarray,
    micro_sites: np.ndarray,
    block_offsets: np.ndarray,
    block_operators: np.ndarray,
    block_arities: np.ndarray,
    block_sites: np.ndarray,
    neural_features: np.ndarray,
    neural_state_index: np.ndarray,
    neural_density: np.ndarray,
    neural_lookup: np.ndarray,
    neural_strides: np.ndarray,
    patch_dx: np.ndarray,
    patch_dy: np.ndarray,
    patch_feature: np.ndarray,
    shell_counts: np.ndarray,
    rng: np.random.Generator,
    block_size: int,
    sweeps: int,
) -> tuple[int, int]:
    """Sample K.S(sigma)+J.S(tau(sigma))+V_theta(tau(sigma))."""
    length = spins.shape[0]
    coarse = cached_block_spins.shape[0]
    n_operators = couplings.shape[0]
    n_affected = patch_dx.shape[0]
    delta_micro = np.zeros(n_operators, dtype=np.int64)
    delta_block = np.zeros(n_operators, dtype=np.int64)
    proposed_density = np.empty(n_affected, dtype=np.float64)
    accepted = 0
    attempted = sweeps * length * length

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

        old_spin = spins[x, y]
        bx = x // block_size
        by = y // block_size
        block_site = bx * coarse + by
        old_block_spin = cached_block_spins[bx, by]
        new_block_sum = cached_block_sums[bx, by] - 2 * old_spin
        new_block_spin = 1 if new_block_sum > 0 else -1
        delta_neural = 0.0

        if new_block_spin != old_block_spin:
            for entry in range(block_offsets[block_site], block_offsets[block_site + 1]):
                product = 1
                for vertex in range(block_arities[entry]):
                    flat_site = block_sites[entry, vertex]
                    sx = flat_site // coarse
                    sy = flat_site - sx * coarse
                    product *= cached_block_spins[sx, sy]
                delta_block[block_operators[entry]] += 2 * product

            for affected in range(n_affected):
                cx = (bx - patch_dx[affected]) % coarse
                cy = (by - patch_dy[affected]) % coarse
                feature = patch_feature[affected]
                new_index = (
                    neural_state_index[cx, cy]
                    - old_block_spin * neural_strides[feature]
                )
                new_value = neural_lookup[new_index]
                proposed_density[affected] = new_value
                delta_neural += new_value - neural_density[cx, cy]

        delta_h = delta_neural
        for operator_index in range(n_operators):
            delta_h += couplings[operator_index] * delta_micro[operator_index]
            delta_h += linear_bias[operator_index] * delta_block[operator_index]
        draw = rng.random()
        if delta_h > 0.0 and draw >= np.exp(-delta_h):
            continue

        spins[x, y] = -old_spin
        cached_block_sums[bx, by] = new_block_sum
        for operator_index in range(n_operators):
            micro_values[operator_index] += delta_micro[operator_index]
            block_values[operator_index] += delta_block[operator_index]
        if new_block_spin != old_block_spin:
            for affected in range(n_affected):
                cx = (bx - patch_dx[affected]) % coarse
                cy = (by - patch_dy[affected]) % coarse
                feature = patch_feature[affected]
                neural_features[cx, cy, feature] += (
                    -2.0 * old_block_spin / shell_counts[feature]
                )
                neural_state_index[cx, cy] -= (
                    old_block_spin * neural_strides[feature]
                )
                neural_density[cx, cy] = proposed_density[affected]
            cached_block_spins[bx, by] = new_block_spin
        accepted += 1
    return attempted, accepted


@dataclass(frozen=True)
class HybridProposalDelta:
    delta_micro: np.ndarray
    delta_linear_bias: np.ndarray
    delta_neural_bias: float
    new_block_sum: int
    new_block_spin: int
    local_proposal: LocalEnergyProposal | None


class LinearNeuralBiasedMetropolis:
    """Exact local sampler for a 13-operator Hamiltonian plus neural bias.

    The microscopic Hamiltonian is ``K.S(sigma)``.  The block-spin bias is
    ``J.S(mu)+V_theta(mu)``.  Keeping the verified long-range linear branch
    prevents a small local neural receptive field from silently deleting the
    distance-2 and distance-3 couplings.
    """

    def __init__(
        self,
        lattice: IsingLattice,
        couplings: np.ndarray,
        linear_bias: np.ndarray,
        neural_bias: D4EvenLocalMLP,
        rng: np.random.Generator,
        shapes: tuple[OperatorShape, ...],
        block_size: int = 3,
        compiled: bool = True,
        micro_basis: OperatorBasis | None = None,
        block_basis: OperatorBasis | None = None,
    ) -> None:
        if lattice.length % block_size != 0:
            raise ValueError("lattice length must be divisible by block_size")
        self.lattice = lattice
        self.couplings = np.asarray(couplings, dtype=np.float64).copy()
        self.linear_bias = np.asarray(linear_bias, dtype=np.float64).copy()
        self.neural_bias = neural_bias
        self.rng = rng
        self.shapes = tuple(shapes)
        self.block_size = int(block_size)
        self.compiled = bool(compiled)
        if self.couplings.shape != (len(self.shapes),):
            raise ValueError("couplings have the wrong shape")
        if self.linear_bias.shape != self.couplings.shape:
            raise ValueError("linear_bias has the wrong shape")

        coarse = lattice.length // block_size
        if coarse < 2 * neural_bias.radius + 1:
            raise ValueError("coarse lattice is smaller than the neural receptive field")
        self.micro_basis = micro_basis or OperatorBasis(lattice.length, self.shapes)
        self.block_basis = block_basis or OperatorBasis(coarse, self.shapes)
        self.micro_incidence = self.micro_basis.packed_incidence()
        self.block_incidence = self.block_basis.packed_incidence()
        self.block_sums = block_sums(lattice.spins, block_size)
        self.block_spins = block_majority(lattice.spins, block_size)
        self.micro_values = self.micro_basis.values(lattice.spins)
        self.block_values = self.block_basis.values(self.block_spins)
        self.bias_cache = LocalEnergyCache(neural_bias, self.block_spins)
        patch = self.bias_cache.patch_offsets
        self.patch_dx = np.asarray([item[0] for item in patch], dtype=np.int32)
        self.patch_dy = np.asarray([item[1] for item in patch], dtype=np.int32)
        self.patch_feature = np.asarray([item[2] for item in patch], dtype=np.int32)
        self.attempted = 0
        self.accepted = 0

    @property
    def effective_hamiltonian(self) -> float:
        return float(
            np.dot(self.couplings, self.micro_values)
            + np.dot(self.linear_bias, self.block_values)
            + self.bias_cache.energy
        )

    @property
    def acceptance_rate(self) -> float:
        return self.accepted / self.attempted if self.attempted else 0.0

    def refresh_bias_model(self) -> None:
        self.bias_cache.refresh_model()

    def proposal_delta(self, x: int, y: int) -> HybridProposalDelta:
        delta_micro = self.micro_basis.delta_for_flip(self.lattice.spins, x, y)
        bx, by = x // self.block_size, y // self.block_size
        old_spin = int(self.lattice.spins[x, y])
        old_block_spin = int(self.block_spins[bx, by])
        new_block_sum = int(self.block_sums[bx, by] - 2 * old_spin)
        if new_block_sum == 0:
            raise AssertionError("odd blocks cannot have a tied majority")
        new_block_spin = 1 if new_block_sum > 0 else -1
        delta_linear = np.zeros_like(self.block_values)
        local_proposal = None
        delta_neural = 0.0
        if new_block_spin != old_block_spin:
            delta_linear = self.block_basis.delta_for_flip(self.block_spins, bx, by)
            local_proposal = self.bias_cache.proposal(bx, by)
            delta_neural = local_proposal.delta_energy
        return HybridProposalDelta(
            delta_micro,
            delta_linear,
            delta_neural,
            new_block_sum,
            new_block_spin,
            local_proposal,
        )

    def attempt_flip(self, x: int, y: int, uniform: float | None = None) -> bool:
        proposal = self.proposal_delta(x, y)
        delta_h = float(
            np.dot(self.couplings, proposal.delta_micro)
            + np.dot(self.linear_bias, proposal.delta_linear_bias)
            + proposal.delta_neural_bias
        )
        draw = float(self.rng.random()) if uniform is None else float(uniform)
        self.attempted += 1
        if delta_h > 0.0 and draw >= np.exp(-delta_h):
            return False

        bx, by = x // self.block_size, y // self.block_size
        self.lattice.flip(x, y)
        self.micro_values += proposal.delta_micro
        self.block_sums[bx, by] = proposal.new_block_sum
        if proposal.local_proposal is not None:
            self.bias_cache.commit(proposal.local_proposal)
            self.block_spins[bx, by] = proposal.new_block_spin
            self.block_values += proposal.delta_linear_bias
        self.accepted += 1
        return True

    def sweep(self) -> None:
        length = self.lattice.length
        for _ in range(self.lattice.n_sites):
            self.attempt_flip(int(self.rng.integers(length)), int(self.rng.integers(length)))

    def run_sweeps(self, sweeps: int) -> None:
        if sweeps <= 0:
            raise ValueError("sweeps must be positive")
        if not self.compiled:
            for _ in range(sweeps):
                self.sweep()
            return
        if self.bias_cache.lookup_table is None:
            attempted, accepted = _compiled_hybrid_sweeps_direct(
                self.lattice.spins,
                self.block_sums,
                self.block_spins,
                self.micro_values,
                self.block_values,
                self.couplings,
                self.linear_bias,
                *self.micro_incidence,
                *self.block_incidence,
                self.bias_cache.features,
                self.bias_cache.density,
                self.patch_dx,
                self.patch_dy,
                self.patch_feature,
                self.neural_bias.shell_counts,
                self.neural_bias.feature_permutations,
                self.neural_bias.weight_in,
                self.neural_bias.bias_hidden,
                self.neural_bias.weight_out,
                self.rng,
                self.block_size,
                sweeps,
            )
        else:
            if self.bias_cache.state_index is None:
                raise AssertionError("lookup cache is missing state indices")
            attempted, accepted = _compiled_hybrid_sweeps(
                self.lattice.spins,
                self.block_sums,
                self.block_spins,
                self.micro_values,
                self.block_values,
                self.couplings,
                self.linear_bias,
                *self.micro_incidence,
                *self.block_incidence,
                self.bias_cache.features,
                self.bias_cache.state_index,
                self.bias_cache.density,
                self.bias_cache.lookup_table,
                self.neural_bias.lookup_strides,
                self.patch_dx,
                self.patch_dy,
                self.patch_feature,
                self.neural_bias.shell_counts,
                self.rng,
                self.block_size,
                sweeps,
            )
        self.attempted += int(attempted)
        self.accepted += int(accepted)

    def assert_cache_consistent(self) -> None:
        np.testing.assert_array_equal(
            self.block_sums, block_sums(self.lattice.spins, self.block_size)
        )
        np.testing.assert_array_equal(
            self.block_spins, block_majority(self.lattice.spins, self.block_size)
        )
        np.testing.assert_array_equal(
            self.micro_values, self.micro_basis.values(self.lattice.spins)
        )
        np.testing.assert_array_equal(
            self.block_values, self.block_basis.values(self.block_spins)
        )
        self.bias_cache.assert_consistent()


class HybridNeuralVMCRGOptimizer:
    """Optimize a 2D neural residual on top of a fixed linear bias."""

    def __init__(
        self,
        length: int,
        couplings: np.ndarray,
        linear_bias: np.ndarray,
        model: D4EvenLocalMLP,
        shapes: tuple[OperatorShape, ...],
        walkers: int = 16,
        seed: int = 20260715,
        block_size: int = 3,
        compiled: bool = True,
        parallel_walkers: bool = True,
        max_workers: int | None = None,
        reference_distribution: ReferenceDistribution2D | None = None,
        initial_spins: np.ndarray | None = None,
    ) -> None:
        if walkers < 2:
            raise ValueError("at least two independent walkers are required")
        if length % block_size != 0:
            raise ValueError("length must be divisible by block_size")
        self.length = int(length)
        self.couplings = np.asarray(couplings, dtype=np.float64).copy()
        self.linear_bias = np.asarray(linear_bias, dtype=np.float64).copy()
        self.model = model
        self.shapes = tuple(shapes)
        self.walker_count = int(walkers)
        self.block_size = int(block_size)
        self.parallel_walkers = bool(parallel_walkers)
        self.max_workers = resolve_worker_limit(max_workers, walkers)
        self.reference_distribution = (
            UniformIsingReference2D()
            if reference_distribution is None
            else reference_distribution
        )
        sequences = np.random.SeedSequence(seed).spawn(walkers + 1)
        initial_values: np.ndarray | None = None
        if initial_spins is not None:
            initial_values = np.asarray(initial_spins, dtype=np.int8)
            if initial_values.shape != (walkers, length, length):
                raise ValueError(
                    "initial spins must have shape (walkers, length, length)"
                )
            if not np.all((initial_values == -1) | (initial_values == 1)):
                raise ValueError("initial spins must contain only -1 and +1")
        self.reference_rng = np.random.default_rng(sequences[-1])
        self.training_stop_reason: str | None = None
        self.training_stop_state: TrainingStopState | None = None
        self.polyak_averager: PolyakAverager | None = None
        micro_basis = OperatorBasis(length, self.shapes)
        block_basis = OperatorBasis(length // block_size, self.shapes)
        self.samplers: list[LinearNeuralBiasedMetropolis] = []
        for walker, sequence in enumerate(sequences[:-1]):
            rng = np.random.default_rng(sequence)
            lattice = (
                IsingLattice.random(length, rng)
                if initial_values is None
                else IsingLattice(initial_values[walker].copy())
            )
            self.samplers.append(
                LinearNeuralBiasedMetropolis(
                    lattice,
                    self.couplings,
                    self.linear_bias,
                    model,
                    rng,
                    self.shapes,
                    block_size=block_size,
                    compiled=compiled,
                    micro_basis=micro_basis,
                    block_basis=block_basis,
                )
            )

    def _reference_samples(self, samples: int, length: int) -> np.ndarray:
        spins = np.asarray(
            self.reference_distribution.sample(self.reference_rng, samples, length)
        )
        expected_shape = (samples, length, length)
        if spins.shape != expected_shape:
            raise ValueError(
                f"reference distribution returned {spins.shape}, expected {expected_shape}"
            )
        if not np.all((spins == -1) | (spins == 1)):
            raise ValueError("reference distribution must return only -1 and +1 spins")
        spins = spins.astype(np.int8, copy=False)
        log_probability = np.asarray(
            self.reference_distribution.log_probability(spins), dtype=np.float64
        )
        if log_probability.shape != (samples,):
            raise ValueError("reference log_probability must return one value per sample")
        if not np.all(np.isfinite(log_probability)):
            raise ValueError("reference log_probability returned a non-finite value")
        return spins

    def run_protocol(
        self,
        protocol: TrainingProtocol,
        *,
        monitor_callback: Callable[
            [int, D4EvenLocalMLP, NeuralOptimizationRecord, float],
            TrainingWindow,
        ],
        callback: Callable[[NeuralOptimizationRecord], None] | None = None,
    ) -> list[NeuralOptimizationRecord]:
        return self.run(
            steps=protocol.maximum_updates,
            sweeps_per_step=protocol.sweeps_per_gradient_batch,
            learning_rate=protocol.schedule.rate(0),
            target_samples=protocol.target_samples_per_batch,
            averaging_start=None,
            callback=callback,
            optimizer_name="literal_robbins_monro",
            gradient_accumulation_steps=protocol.gradient_accumulation_batches,
            training_protocol=protocol,
            monitor_callback=monitor_callback,
        )

    def run(
        self,
        steps: int,
        sweeps_per_step: int,
        learning_rate: float,
        target_samples: int | None = None,
        averaging_start: int | None = None,
        callback: Callable[[NeuralOptimizationRecord], None] | None = None,
        optimizer_name: str = "adam",
        gradient_accumulation_steps: int = 1,
        decay_scale: float = 300.0,
        decay_power: float = 0.75,
        training_protocol: TrainingProtocol | None = None,
        monitor_callback: Callable[
            [int, D4EvenLocalMLP, NeuralOptimizationRecord, float],
            TrainingWindow,
        ]
        | None = None,
    ) -> list[NeuralOptimizationRecord]:
        if steps <= 0 or sweeps_per_step <= 0:
            raise ValueError("steps and sweeps_per_step must be positive")
        if gradient_accumulation_steps <= 0:
            raise ValueError("gradient_accumulation_steps must be positive")
        target_samples = self.walker_count if target_samples is None else target_samples
        if target_samples <= 0:
            raise ValueError("target_samples must be positive")
        if averaging_start is not None and not 0 <= averaging_start < steps:
            raise ValueError("averaging_start must lie in [0, steps)")
        literal_protocol = training_protocol is not None
        if literal_protocol:
            if optimizer_name != "literal_robbins_monro":
                raise ValueError(
                    "explicit training protocol requires literal_robbins_monro"
                )
            if monitor_callback is None:
                raise ValueError("explicit training protocol requires held-out monitoring")
            if (
                steps != training_protocol.maximum_updates
                or sweeps_per_step != training_protocol.sweeps_per_gradient_batch
                or target_samples != training_protocol.target_samples_per_batch
                or gradient_accumulation_steps
                != training_protocol.gradient_accumulation_batches
            ):
                raise ValueError("run arguments do not match the explicit training protocol")
            optimizer: Adam | RobbinsMonroSGD | None = None
            stop_state = TrainingStopState(training_protocol.stop)
            polyak = PolyakAverager(training_protocol.polyak_start_update)
            self.training_stop_state = stop_state
            self.polyak_averager = polyak
            self.training_stop_reason = None
        elif optimizer_name == "adam":
            optimizer = Adam(self.model, learning_rate)
        elif optimizer_name == "robbins_monro_sgd":
            optimizer = RobbinsMonroSGD(
                learning_rate,
                decay_scale=decay_scale,
                decay_power=decay_power,
            )
        else:
            raise ValueError(
                "optimizer_name must be 'adam', 'robbins_monro_sgd', or "
                "'literal_robbins_monro'"
            )
        coarse = self.length // self.block_size
        n_sites = coarse * coarse
        records: list[NeuralOptimizationRecord] = []
        average_weight_in = np.zeros_like(self.model.weight_in)
        average_bias_hidden = np.zeros_like(self.model.bias_hidden)
        average_weight_out = np.zeros_like(self.model.weight_out)
        average_count = 0
        executor = (
            ThreadPoolExecutor(max_workers=self.max_workers)
            if self.parallel_walkers and len(self.samplers) > 1
            else None
        )
        try:
            for step in range(steps):
                attempted_before = sum(sampler.attempted for sampler in self.samplers)
                accepted_before = sum(sampler.accepted for sampler in self.samplers)
                accumulated_gradient = _zero_gradient(self.model)
                biased_energy = 0.0
                target_energy = 0.0
                biased_nn = 0.0
                target_nn = 0.0
                for _ in range(gradient_accumulation_steps):
                    if executor is None:
                        for sampler in self.samplers:
                            sampler.run_sweeps(sweeps_per_step)
                    else:
                        list(
                            executor.map(
                                lambda sampler: sampler.run_sweeps(sweeps_per_step),
                                self.samplers,
                            )
                        )
                    biased_features = np.stack(
                        [sampler.bias_cache.features for sampler in self.samplers]
                    )
                    target_spins = self._reference_samples(target_samples, coarse)
                    target_features = np.stack(
                        [self.model.feature_grid(spins) for spins in target_spins]
                    )
                    biased_gradient = _scale_gradient(
                        self.model.gradient_from_features(biased_features),
                        1.0 / (self.walker_count * n_sites),
                    )
                    target_gradient = _scale_gradient(
                        self.model.gradient_from_features(target_features),
                        1.0 / (target_samples * n_sites),
                    )
                    _add_gradient(
                        accumulated_gradient,
                        _gradient_difference(target_gradient, biased_gradient),
                    )

                    biased_energy += float(
                        np.mean(
                            [sampler.bias_cache.energy for sampler in self.samplers]
                        )
                        / n_sites
                    )
                    target_energy += float(
                        self.model.density_from_features(target_features).sum()
                        / (target_samples * n_sites)
                    )
                    biased_nn += float(
                        np.mean(
                            [
                                nearest_neighbor_operator(sampler.block_spins) / n_sites
                                for sampler in self.samplers
                            ]
                        )
                    )
                    target_nn += float(
                        np.mean(
                            [
                                nearest_neighbor_operator(spins) / n_sites
                                for spins in target_spins
                            ]
                        )
                    )
                inverse_accumulation = 1.0 / gradient_accumulation_steps
                gradient = _scale_gradient(
                    accumulated_gradient, inverse_accumulation
                )
                biased_energy *= inverse_accumulation
                target_energy *= inverse_accumulation
                biased_nn *= inverse_accumulation
                target_nn *= inverse_accumulation
                attempted_step = (
                    sum(sampler.attempted for sampler in self.samplers) - attempted_before
                )
                accepted_step = (
                    sum(sampler.accepted for sampler in self.samplers) - accepted_before
                )
                acceptance = accepted_step / attempted_step

                unclipped_gradient_norm = gradient.norm()
                if literal_protocol:
                    if training_protocol is None:
                        raise AssertionError("literal protocol disappeared")
                    gradient, unclipped_gradient_norm, clipped_gradient_norm = (
                        clip_mlp_gradient(
                            gradient,
                            training_protocol.gradient_clip_l2,
                        )
                    )
                    effective_learning_rate = training_protocol.schedule.rate(step)
                    self.model.weight_in -= effective_learning_rate * gradient.weight_in
                    self.model.bias_hidden -= (
                        effective_learning_rate * gradient.bias_hidden
                    )
                    self.model.weight_out -= effective_learning_rate * gradient.weight_out
                    if not model_parameters_finite(self.model):
                        self.training_stop_reason = "CORRECTNESS_FAILURE"
                        raise FloatingPointError("non-finite neural parameters after update")
                    if self.polyak_averager is None:
                        raise AssertionError("Polyak averager was not initialized")
                    self.polyak_averager.observe(step + 1, self.model)
                else:
                    if optimizer is None:
                        raise AssertionError("legacy optimizer was not initialized")
                    effective_learning_rate = optimizer.update(self.model, gradient)
                    clipped_gradient_norm = unclipped_gradient_norm
                if not literal_protocol and averaging_start is not None and step >= averaging_start:
                    average_weight_in += self.model.weight_in
                    average_bias_hidden += self.model.bias_hidden
                    average_weight_out += self.model.weight_out
                    average_count += 1
                for sampler in self.samplers:
                    sampler.refresh_bias_model()
                record = NeuralOptimizationRecord(
                    step=step,
                    gradient_norm=clipped_gradient_norm,
                    learning_rate=effective_learning_rate,
                    biased_energy_per_site=biased_energy,
                    target_energy_per_site=target_energy,
                    biased_nn_per_site=biased_nn,
                    target_nn_per_site=target_nn,
                    acceptance_rate=float(acceptance),
                    unclipped_gradient_norm=unclipped_gradient_norm,
                    clipped_gradient_norm=clipped_gradient_norm,
                )
                stop_reason: str | None = None
                if (
                    literal_protocol
                    and training_protocol is not None
                    and (
                        (step + 1) % training_protocol.stop.monitor_every == 0
                        or step + 1 == training_protocol.maximum_updates
                    )
                ):
                    if monitor_callback is None or self.polyak_averager is None:
                        raise AssertionError("held-out monitor was not initialized")
                    monitored = monitor_callback(
                        step + 1,
                        self.model,
                        record,
                        self.polyak_averager.fraction(step + 1),
                    )
                    if not isinstance(monitored, TrainingWindow):
                        raise TypeError("monitor callback must return TrainingWindow")
                    monitored = replace(
                        monitored,
                        update=step + 1,
                        gradient_norm=clipped_gradient_norm,
                        polyak_fraction=self.polyak_averager.fraction(step + 1),
                        parameters_finite=model_parameters_finite(self.model),
                        gradient_finite=np.isfinite(unclipped_gradient_norm),
                    )
                    if self.training_stop_state is None:
                        raise AssertionError("training stop state was not initialized")
                    stop_reason = self.training_stop_state.observe(monitored)
                    self.training_stop_reason = stop_reason
                    if stop_reason is not None:
                        record = replace(record, stop_reason=stop_reason)
                records.append(record)
                if callback is not None:
                    callback(record)
                if stop_reason is not None:
                    break
        finally:
            if executor is not None:
                executor.shutdown(wait=True)
        if literal_protocol:
            if self.polyak_averager is None:
                raise AssertionError("Polyak averager was not initialized")
            if self.training_stop_reason is None:
                self.training_stop_reason = "NOT_CONVERGED"
            if (
                self.training_stop_reason != "CORRECTNESS_FAILURE"
                and self.polyak_averager.sample_count > 0
            ):
                self.polyak_averager.assign_to(self.model)
                for sampler in self.samplers:
                    sampler.refresh_bias_model()
        elif averaging_start is not None:
            if average_count == 0:
                raise AssertionError("parameter averaging collected no samples")
            self.model.weight_in[:] = average_weight_in / average_count
            self.model.bias_hidden[:] = average_bias_hidden / average_count
            self.model.weight_out[:] = average_weight_out / average_count
            for sampler in self.samplers:
                sampler.refresh_bias_model()
        return records
