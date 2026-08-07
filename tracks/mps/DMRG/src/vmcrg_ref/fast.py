from __future__ import annotations

import numpy as np
from numba import njit

from .blockspin import block_majority, block_sums
from .ising import IsingLattice
from .operators import OperatorBasis, OperatorShape


@njit(cache=True, nogil=True)
def _compiled_sweeps(
    spins: np.ndarray,
    cached_block_sums: np.ndarray,
    cached_block_spins: np.ndarray,
    micro_values: np.ndarray,
    block_values: np.ndarray,
    couplings: np.ndarray,
    bias: np.ndarray,
    micro_offsets: np.ndarray,
    micro_operators: np.ndarray,
    micro_arities: np.ndarray,
    micro_sites: np.ndarray,
    block_offsets: np.ndarray,
    block_operators: np.ndarray,
    block_arities: np.ndarray,
    block_sites: np.ndarray,
    rng: np.random.Generator,
    block_size: int,
    sweeps: int,
) -> tuple[int, int]:
    length = spins.shape[0]
    coarse = cached_block_spins.shape[0]
    n_operators = couplings.shape[0]
    delta_micro = np.zeros(n_operators, dtype=np.int64)
    delta_block = np.zeros(n_operators, dtype=np.int64)
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

        bx = x // block_size
        by = y // block_size
        block_site = bx * coarse + by
        old_spin = spins[x, y]
        old_block_spin = cached_block_spins[bx, by]
        new_block_sum = cached_block_sums[bx, by] - 2 * old_spin
        new_block_spin = 1 if new_block_sum > 0 else -1

        if new_block_spin != old_block_spin:
            for entry in range(block_offsets[block_site], block_offsets[block_site + 1]):
                product = 1
                for vertex in range(block_arities[entry]):
                    flat_site = block_sites[entry, vertex]
                    sx = flat_site // coarse
                    sy = flat_site - sx * coarse
                    product *= cached_block_spins[sx, sy]
                delta_block[block_operators[entry]] += 2 * product

        delta_h = 0.0
        for operator_index in range(n_operators):
            delta_h += couplings[operator_index] * delta_micro[operator_index]
            delta_h += bias[operator_index] * delta_block[operator_index]
        draw = rng.random()
        if delta_h > 0.0 and draw >= np.exp(-delta_h):
            continue

        spins[x, y] = -old_spin
        cached_block_sums[bx, by] = new_block_sum
        cached_block_spins[bx, by] = new_block_spin
        for operator_index in range(n_operators):
            micro_values[operator_index] += delta_micro[operator_index]
            block_values[operator_index] += delta_block[operator_index]
        accepted += 1
    return attempted, accepted


@njit(cache=True, nogil=True)
def _compiled_moment_measurements(
    spins: np.ndarray,
    cached_block_sums: np.ndarray,
    cached_block_spins: np.ndarray,
    micro_values: np.ndarray,
    block_values: np.ndarray,
    couplings: np.ndarray,
    bias: np.ndarray,
    micro_offsets: np.ndarray,
    micro_operators: np.ndarray,
    micro_arities: np.ndarray,
    micro_sites: np.ndarray,
    block_offsets: np.ndarray,
    block_operators: np.ndarray,
    block_arities: np.ndarray,
    block_sites: np.ndarray,
    rng: np.random.Generator,
    block_size: int,
    measurements: int,
    sweeps_between: int,
) -> tuple[int, int, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Measure covariance sufficient statistics without Python-loop overhead."""
    n_operators = micro_values.shape[0]
    micro_sum = np.zeros(n_operators, dtype=np.float64)
    block_sum = np.zeros(n_operators, dtype=np.float64)
    micro_block_sum = np.zeros((n_operators, n_operators), dtype=np.float64)
    block_outer_sum = np.zeros((n_operators, n_operators), dtype=np.float64)
    attempted = 0
    accepted = 0

    for _ in range(measurements):
        step_attempted, step_accepted = _compiled_sweeps(
            spins,
            cached_block_sums,
            cached_block_spins,
            micro_values,
            block_values,
            couplings,
            bias,
            micro_offsets,
            micro_operators,
            micro_arities,
            micro_sites,
            block_offsets,
            block_operators,
            block_arities,
            block_sites,
            rng,
            block_size,
            sweeps_between,
        )
        attempted += step_attempted
        accepted += step_accepted
        for beta in range(n_operators):
            micro_value = micro_values[beta]
            block_value = block_values[beta]
            micro_sum[beta] += micro_value
            block_sum[beta] += block_value
            for gamma in range(n_operators):
                micro_block_sum[beta, gamma] += micro_value * block_values[gamma]
                block_outer_sum[beta, gamma] += block_value * block_values[gamma]

    return (
        attempted,
        accepted,
        micro_sum,
        block_sum,
        micro_block_sum,
        block_outer_sum,
    )


@njit(cache=True, nogil=True)
def _compiled_nearest_neighbor_product_series(
    spins: np.ndarray,
    cached_block_sums: np.ndarray,
    cached_block_spins: np.ndarray,
    micro_values: np.ndarray,
    block_values: np.ndarray,
    couplings: np.ndarray,
    bias: np.ndarray,
    micro_offsets: np.ndarray,
    micro_operators: np.ndarray,
    micro_arities: np.ndarray,
    micro_sites: np.ndarray,
    block_offsets: np.ndarray,
    block_operators: np.ndarray,
    block_arities: np.ndarray,
    block_sites: np.ndarray,
    rng: np.random.Generator,
    block_size: int,
    measurements: int,
    sweeps_between: int,
    micro_normalizer: float,
    block_normalizer: float,
) -> tuple[int, int, np.ndarray]:
    series = np.empty(measurements, dtype=np.float64)
    attempted = 0
    accepted = 0
    for measurement in range(measurements):
        step_attempted, step_accepted = _compiled_sweeps(
            spins,
            cached_block_sums,
            cached_block_spins,
            micro_values,
            block_values,
            couplings,
            bias,
            micro_offsets,
            micro_operators,
            micro_arities,
            micro_sites,
            block_offsets,
            block_operators,
            block_arities,
            block_sites,
            rng,
            block_size,
            sweeps_between,
        )
        attempted += step_attempted
        accepted += step_accepted
        series[measurement] = (
            (micro_values[0] / micro_normalizer)
            * (block_values[0] / block_normalizer)
        )
    return attempted, accepted, series


@njit(cache=True, nogil=True)
def _compiled_odd_magnetization_moment_series(
    spins: np.ndarray,
    cached_block_sums: np.ndarray,
    cached_block_spins: np.ndarray,
    micro_values: np.ndarray,
    block_values: np.ndarray,
    couplings: np.ndarray,
    bias: np.ndarray,
    micro_offsets: np.ndarray,
    micro_operators: np.ndarray,
    micro_arities: np.ndarray,
    micro_sites: np.ndarray,
    block_offsets: np.ndarray,
    block_operators: np.ndarray,
    block_arities: np.ndarray,
    block_sites: np.ndarray,
    rng: np.random.Generator,
    block_size: int,
    measurements: int,
    sweeps_between: int,
    operator_index: int,
    micro_normalizer: float,
    block_normalizer: float,
) -> tuple[int, int, np.ndarray, np.ndarray]:
    cross_series = np.empty(measurements, dtype=np.float64)
    block_square_series = np.empty(measurements, dtype=np.float64)
    attempted = 0
    accepted = 0
    for measurement in range(measurements):
        step_attempted, step_accepted = _compiled_sweeps(
            spins,
            cached_block_sums,
            cached_block_spins,
            micro_values,
            block_values,
            couplings,
            bias,
            micro_offsets,
            micro_operators,
            micro_arities,
            micro_sites,
            block_offsets,
            block_operators,
            block_arities,
            block_sites,
            rng,
            block_size,
            sweeps_between,
        )
        attempted += step_attempted
        accepted += step_accepted
        micro_value = micro_values[operator_index] / micro_normalizer
        block_value = block_values[operator_index] / block_normalizer
        cross_series[measurement] = micro_value * block_value
        block_square_series[measurement] = block_value * block_value
    return attempted, accepted, cross_series, block_square_series


class FastMultiOperatorBiasedMetropolis:
    """Numba-compiled equivalent of MultiOperatorBiasedMetropolis."""

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
        self.couplings = np.asarray(couplings, dtype=np.float64).copy()
        self.bias = np.asarray(bias, dtype=np.float64).copy()
        self.rng = rng
        self.shapes = tuple(shapes)
        self.block_size = int(block_size)
        if self.couplings.shape != (len(self.shapes),):
            raise ValueError("couplings have the wrong shape")
        if self.bias.shape != self.couplings.shape:
            raise ValueError("bias has the wrong shape")

        coarse = lattice.length // block_size
        self.micro_basis = micro_basis or OperatorBasis(lattice.length, self.shapes)
        self.block_basis = block_basis or OperatorBasis(coarse, self.shapes)
        self.micro_incidence = self.micro_basis.packed_incidence()
        self.block_incidence = self.block_basis.packed_incidence()
        self.block_sums = block_sums(lattice.spins, block_size)
        self.block_spins = block_majority(lattice.spins, block_size)
        self.micro_values = self.micro_basis.values(lattice.spins)
        self.block_values = self.block_basis.values(self.block_spins)
        self.attempted = 0
        self.accepted = 0

    @property
    def acceptance_rate(self) -> float:
        return self.accepted / self.attempted if self.attempted else 0.0

    def run_sweeps(self, sweeps: int) -> None:
        if sweeps <= 0:
            raise ValueError("sweeps must be positive")
        attempted, accepted = _compiled_sweeps(
            self.lattice.spins,
            self.block_sums,
            self.block_spins,
            self.micro_values,
            self.block_values,
            self.couplings,
            self.bias,
            *self.micro_incidence,
            *self.block_incidence,
            self.rng,
            self.block_size,
            sweeps,
        )
        self.attempted += int(attempted)
        self.accepted += int(accepted)

    def sweep(self) -> None:
        self.run_sweeps(1)

    def measure_moments(
        self, measurements: int, sweeps_between: int = 1
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Return sums needed for Eqs. 16-17 over a stationary frozen chain."""
        if measurements <= 0 or sweeps_between <= 0:
            raise ValueError("measurements and sweeps_between must be positive")
        result = _compiled_moment_measurements(
            self.lattice.spins,
            self.block_sums,
            self.block_spins,
            self.micro_values,
            self.block_values,
            self.couplings,
            self.bias,
            *self.micro_incidence,
            *self.block_incidence,
            self.rng,
            self.block_size,
            measurements,
            sweeps_between,
        )
        attempted, accepted, micro_sum, block_sum, cross_sum, block_outer_sum = result
        self.attempted += int(attempted)
        self.accepted += int(accepted)
        return micro_sum, block_sum, cross_sum, block_outer_sum

    def nearest_neighbor_product_series(
        self, measurements: int, sweeps_between: int = 1
    ) -> np.ndarray:
        """Measure normalized S0(sigma)S0(sigma') for the paper's Fig. 2."""
        if measurements <= 0 or sweeps_between <= 0:
            raise ValueError("measurements and sweeps_between must be positive")
        attempted, accepted, series = _compiled_nearest_neighbor_product_series(
            self.lattice.spins,
            self.block_sums,
            self.block_spins,
            self.micro_values,
            self.block_values,
            self.couplings,
            self.bias,
            *self.micro_incidence,
            *self.block_incidence,
            self.rng,
            self.block_size,
            measurements,
            sweeps_between,
            float(self.micro_basis.instance_counts[0]),
            float(self.block_basis.instance_counts[0]),
        )
        self.attempted += int(attempted)
        self.accepted += int(accepted)
        return series

    def odd_magnetization_moment_series(
        self,
        operator_index: int,
        measurements: int,
        sweeps_between: int = 1,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Return normalized odd cross and block-square moment series."""
        if measurements <= 0 or sweeps_between <= 0:
            raise ValueError("measurements and sweeps_between must be positive")
        if operator_index < 0 or operator_index >= len(self.shapes):
            raise IndexError("operator_index is outside the configured basis")
        if self.shapes[operator_index].parity != "odd":
            raise ValueError("operator_index must identify an odd operator")
        result = _compiled_odd_magnetization_moment_series(
            self.lattice.spins,
            self.block_sums,
            self.block_spins,
            self.micro_values,
            self.block_values,
            self.couplings,
            self.bias,
            *self.micro_incidence,
            *self.block_incidence,
            self.rng,
            self.block_size,
            measurements,
            sweeps_between,
            operator_index,
            float(self.micro_basis.instance_counts[operator_index]),
            float(self.block_basis.instance_counts[operator_index]),
        )
        attempted, accepted, cross_series, block_square_series = result
        self.attempted += int(attempted)
        self.accepted += int(accepted)
        return cross_series, block_square_series

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
