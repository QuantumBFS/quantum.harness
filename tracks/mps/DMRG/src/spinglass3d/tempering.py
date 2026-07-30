"""Detailed-balance-correct reference parallel tempering kernels."""

from __future__ import annotations

import math
from collections.abc import Callable

import numpy as np

from .exact import enumerate_l2
from .model import EABonds, delta_energy, energy, three_color_sites
from .overlap import ReplicaPair


class TemperatureGrid:
    def __init__(self, values: np.ndarray) -> None:
        betas = np.asarray(values, dtype=np.float64)
        if (
            betas.ndim != 1
            or betas.size < 2
            or not np.all(np.isfinite(betas))
            or np.any(betas <= 0.0)
            or np.any(np.diff(betas) <= 0.0)
        ):
            raise ValueError("beta values must be positive, finite, and strictly increasing")
        self.betas = betas.copy()
        self.betas.setflags(write=False)
        self.temperatures = 1.0 / self.betas
        self.temperatures.setflags(write=False)
        self.labels = tuple(f"T={temperature:.12g}" for temperature in self.temperatures)

    def __len__(self) -> int:
        return int(self.betas.size)


def swap_delta(
    *,
    beta_m: float,
    beta_n: float,
    energy_m: float,
    energy_n: float,
    bias_m_xm: float,
    bias_m_xn: float,
    bias_n_xm: float,
    bias_n_xn: float,
) -> float:
    values = (
        beta_m,
        beta_n,
        energy_m,
        energy_n,
        bias_m_xm,
        bias_m_xn,
        bias_n_xm,
        bias_n_xn,
    )
    if not all(math.isfinite(float(value)) for value in values):
        raise ValueError("swap action components must be finite")
    before = beta_m * energy_m + bias_m_xm + beta_n * energy_n + bias_n_xn
    after = beta_m * energy_n + bias_m_xn + beta_n * energy_m + bias_n_xm
    return float(after - before)


def _accept(delta_action: float, rng: np.random.Generator) -> bool:
    if not math.isfinite(delta_action):
        raise FloatingPointError("Metropolis action difference is not finite")
    return math.log(float(rng.random())) < min(0.0, -delta_action)


def enumerate_l2_pt_transition(
    beta: float,
    bonds: EABonds,
) -> tuple[np.ndarray, np.ndarray]:
    """Enumerate the random-site Metropolis kernel used inside the PT ladder."""
    record = enumerate_l2(beta, bonds)
    count = record.states.shape[0]
    n_sites = record.states.shape[1] ** 3
    transition = np.zeros((count, count), dtype=np.float64)
    for source, source_energy in enumerate(record.energies):
        for flat_site in range(n_sites):
            target = source ^ (1 << flat_site)
            difference = int(record.energies[target] - source_energy)
            probability = (
                1.0 if difference <= 0 else math.exp(-beta * difference)
            ) / n_sites
            transition[source, target] += probability
        transition[source, source] = 1.0 - float(np.sum(transition[source]))
    return transition, record.probabilities.copy()


class SingleReplicaLadder:
    """One unbiased PT ladder with persistent physical-replica identities."""

    def __init__(
        self,
        bonds: EABonds,
        grid: TemperatureGrid,
        spins: np.ndarray,
        *,
        local_rng: np.random.Generator,
        swap_rng: np.random.Generator,
    ) -> None:
        if not isinstance(bonds, EABonds) or not isinstance(grid, TemperatureGrid):
            raise TypeError("bonds and grid have incompatible types")
        values = np.asarray(spins)
        expected = (len(grid), bonds.length, bonds.length, bonds.length)
        if values.shape != expected or not np.all((values == -1) | (values == 1)):
            raise ValueError(f"spins must be binary with shape {expected}")
        if local_rng is swap_rng:
            raise ValueError("local and swap RNG streams must be independent")
        self.bonds = bonds
        self.grid = grid
        self.spins = values.astype(np.int8, copy=True)
        self.local_rng = local_rng
        self.swap_rng = swap_rng
        self.energies = np.asarray(
            [energy(state, bonds) for state in self.spins],
            dtype=np.int64,
        )
        self.replica_ids = np.arange(len(grid), dtype=np.int64)
        self.swap_attempts = np.zeros(len(grid) - 1, dtype=np.int64)
        self.swap_accepts = np.zeros(len(grid) - 1, dtype=np.int64)
        self.local_attempts = 0
        self.local_accepts = 0
        self._sweep_count = 0
        self.position_history: list[np.ndarray] = []
        self._record_positions()
        self._colors = three_color_sites(bonds.length)

    @classmethod
    def random(
        cls,
        bonds: EABonds,
        grid: TemperatureGrid,
        seed: int,
    ) -> "SingleReplicaLadder":
        seed_sequence = np.random.SeedSequence(seed)
        state_seed, local_seed, swap_seed = seed_sequence.spawn(3)
        state_rng = np.random.default_rng(state_seed)
        spins = state_rng.choice(
            np.array([-1, 1], dtype=np.int8),
            size=(len(grid), bonds.length, bonds.length, bonds.length),
        )
        return cls(
            bonds,
            grid,
            spins,
            local_rng=np.random.default_rng(local_seed),
            swap_rng=np.random.default_rng(swap_seed),
        )

    def _record_positions(self) -> None:
        positions = np.empty(len(self.grid), dtype=np.int64)
        positions[self.replica_ids] = np.arange(len(self.grid), dtype=np.int64)
        self.position_history.append(positions)

    def attempt_local(self) -> tuple[int, int]:
        attempts = 0
        accepts = 0
        for temperature_index, beta in enumerate(self.grid.betas):
            state = self.spins[temperature_index]
            for color in self._colors:
                for coordinates in color:
                    site = tuple(int(value) for value in coordinates)
                    difference = delta_energy(state, self.bonds, site)
                    attempts += 1
                    if _accept(float(beta * difference), self.local_rng):
                        state[site] *= -1
                        self.energies[temperature_index] += difference
                        accepts += 1
        self.local_attempts += attempts
        self.local_accepts += accepts
        return attempts, accepts

    def attempt_swaps(self, parity: int) -> tuple[int, int]:
        attempts = 0
        accepts = 0
        for lower in range(int(parity) % 2, len(self.grid) - 1, 2):
            upper = lower + 1
            delta = swap_delta(
                beta_m=float(self.grid.betas[lower]),
                beta_n=float(self.grid.betas[upper]),
                energy_m=float(self.energies[lower]),
                energy_n=float(self.energies[upper]),
                bias_m_xm=0.0,
                bias_m_xn=0.0,
                bias_n_xm=0.0,
                bias_n_xn=0.0,
            )
            self.swap_attempts[lower] += 1
            attempts += 1
            if _accept(delta, self.swap_rng):
                temporary = self.spins[lower].copy()
                self.spins[lower] = self.spins[upper]
                self.spins[upper] = temporary
                self.energies[lower], self.energies[upper] = (
                    self.energies[upper],
                    self.energies[lower],
                )
                self.replica_ids[lower], self.replica_ids[upper] = (
                    self.replica_ids[upper],
                    self.replica_ids[lower],
                )
                self.swap_accepts[lower] += 1
                accepts += 1
        return attempts, accepts

    def run_sweeps(self, sweeps: int, progress_every: int | None = None) -> None:
        if sweeps < 0:
            raise ValueError("sweeps must be nonnegative")
        for completed in range(1, sweeps + 1):
            self.attempt_local()
            self.attempt_swaps(self._sweep_count % 2)
            self._sweep_count += 1
            self._record_positions()
            if progress_every and completed % progress_every == 0:
                print(f"unbiased PT sweep={completed}/{sweeps}", flush=True)


class UnbiasedOverlapPT:
    def __init__(
        self,
        ladder_a: SingleReplicaLadder,
        ladder_b: SingleReplicaLadder,
    ) -> None:
        if not isinstance(ladder_a, SingleReplicaLadder) or not isinstance(
            ladder_b, SingleReplicaLadder
        ):
            raise TypeError("both inputs must be SingleReplicaLadder")
        if not np.array_equal(ladder_a.bonds.values, ladder_b.bonds.values):
            raise ValueError("unbiased ladders must share the same quenched J")
        if not np.array_equal(ladder_a.grid.betas, ladder_b.grid.betas):
            raise ValueError("unbiased ladders must share the temperature grid")
        if np.shares_memory(ladder_a.spins, ladder_b.spins):
            raise ValueError("unbiased ladders must not share spin memory")
        rngs = (ladder_a.local_rng, ladder_a.swap_rng, ladder_b.local_rng, ladder_b.swap_rng)
        if len({id(rng) for rng in rngs}) != len(rngs):
            raise ValueError("unbiased ladders must use independent RNG streams")
        self.ladder_a = ladder_a
        self.ladder_b = ladder_b

    def run_sweeps(self, sweeps: int, progress_every: int | None = None) -> None:
        for completed in range(1, sweeps + 1):
            self.ladder_a.run_sweeps(1)
            self.ladder_b.run_sweeps(1)
            if progress_every and completed % progress_every == 0:
                print(f"overlap PT sweep={completed}/{sweeps}", flush=True)

    def measure_pairs(self) -> tuple[ReplicaPair, ...]:
        return tuple(
            ReplicaPair(self.ladder_a.spins[index], self.ladder_b.spins[index])
            for index in range(len(self.ladder_a.grid))
        )


class BiasedPairLadder:
    """A PT ladder whose state is a jointly biased pair at each temperature."""

    update_mode = "random_sequential"

    def __init__(
        self,
        bonds: EABonds,
        grid: TemperatureGrid,
        spins_a: np.ndarray,
        spins_b: np.ndarray,
        *,
        bias_energy: Callable[[np.ndarray, np.ndarray], float],
        local_rng: np.random.Generator,
        swap_rng: np.random.Generator,
        global_rng: np.random.Generator,
    ) -> None:
        expected = (len(grid), bonds.length, bonds.length, bonds.length)
        left, right = np.asarray(spins_a), np.asarray(spins_b)
        if left.shape != expected or right.shape != expected:
            raise ValueError("paired spin arrays have the wrong shape")
        if np.shares_memory(left, right) or not np.all((left == -1) | (left == 1)) or not np.all((right == -1) | (right == 1)):
            raise ValueError("paired spin arrays must be independent and binary")
        if len({id(local_rng), id(swap_rng), id(global_rng)}) != 3:
            raise ValueError("biased move types require independent RNG streams")
        self.bonds, self.grid = bonds, grid
        self.spins_a = left.astype(np.int8, copy=True)
        self.spins_b = right.astype(np.int8, copy=True)
        self.bias_energy = bias_energy
        self.local_rng, self.swap_rng, self.global_rng = local_rng, swap_rng, global_rng
        self.energies = np.asarray(
            [
                energy(self.spins_a[index], bonds) + energy(self.spins_b[index], bonds)
                for index in range(len(grid))
            ],
            dtype=np.int64,
        )
        self.bias_values = np.asarray(
            [float(bias_energy(self.spins_a[index], self.spins_b[index])) for index in range(len(grid))],
            dtype=np.float64,
        )
        if not np.all(np.isfinite(self.bias_values)):
            raise ValueError("bias values must be finite")
        self.replica_ids = np.arange(len(grid), dtype=np.int64)
        self.swap_attempts = np.zeros(len(grid) - 1, dtype=np.int64)
        self.swap_accepts = np.zeros(len(grid) - 1, dtype=np.int64)
        self.local_attempts = 0
        self.local_accepts = 0
        self.global_flip_attempts = 0
        self._sweep_count = 0
        self.position_history: list[np.ndarray] = []
        self._record_positions()

    def _record_positions(self) -> None:
        positions = np.empty(len(self.grid), dtype=np.int64)
        positions[self.replica_ids] = np.arange(len(self.grid), dtype=np.int64)
        self.position_history.append(positions)

    @classmethod
    def random(
        cls,
        bonds: EABonds,
        grid: TemperatureGrid,
        *,
        bias_energy: Callable[[np.ndarray, np.ndarray], float],
        seed: int,
    ) -> "BiasedPairLadder":
        seeds = np.random.SeedSequence(seed).spawn(6)
        state_a, state_b = np.random.default_rng(seeds[0]), np.random.default_rng(seeds[1])
        shape = (len(grid), bonds.length, bonds.length, bonds.length)
        spins_a = state_a.choice(np.array([-1, 1], dtype=np.int8), size=shape)
        spins_b = state_b.choice(np.array([-1, 1], dtype=np.int8), size=shape)
        return cls(
            bonds,
            grid,
            spins_a,
            spins_b,
            bias_energy=bias_energy,
            local_rng=np.random.default_rng(seeds[2]),
            swap_rng=np.random.default_rng(seeds[3]),
            global_rng=np.random.default_rng(seeds[4]),
        )

    def attempt_local(self) -> tuple[int, int]:
        attempts = accepts = 0
        n_sites = self.bonds.length**3
        for temperature_index, beta in enumerate(self.grid.betas):
            order = self.local_rng.permutation(2 * n_sites)
            for encoded in order:
                replica = self.spins_a if encoded < n_sites else self.spins_b
                flat_site = int(encoded % n_sites)
                site = tuple(int(value) for value in np.unravel_index(flat_site, (self.bonds.length,) * 3))
                state = replica[temperature_index]
                difference = delta_energy(state, self.bonds, site)
                old_bias = float(self.bias_values[temperature_index])
                state[site] *= -1
                new_bias = float(
                    self.bias_energy(
                        self.spins_a[temperature_index],
                        self.spins_b[temperature_index],
                    )
                )
                delta_action = float(beta * difference + new_bias - old_bias)
                attempts += 1
                if _accept(delta_action, self.local_rng):
                    self.energies[temperature_index] += difference
                    self.bias_values[temperature_index] = new_bias
                    accepts += 1
                else:
                    state[site] *= -1
        self.local_attempts += attempts
        self.local_accepts += accepts
        return attempts, accepts

    def attempt_swaps(self, parity: int) -> tuple[int, int]:
        attempts = accepts = 0
        for lower in range(int(parity) % 2, len(self.grid) - 1, 2):
            upper = lower + 1
            delta = swap_delta(
                beta_m=float(self.grid.betas[lower]),
                beta_n=float(self.grid.betas[upper]),
                energy_m=float(self.energies[lower]),
                energy_n=float(self.energies[upper]),
                bias_m_xm=float(self.bias_values[lower]),
                bias_m_xn=float(self.bias_values[upper]),
                bias_n_xm=float(self.bias_values[lower]),
                bias_n_xn=float(self.bias_values[upper]),
            )
            attempts += 1
            self.swap_attempts[lower] += 1
            if _accept(delta, self.swap_rng):
                for states in (self.spins_a, self.spins_b):
                    temporary = states[lower].copy()
                    states[lower] = states[upper]
                    states[upper] = temporary
                self.energies[lower], self.energies[upper] = self.energies[upper], self.energies[lower]
                self.bias_values[lower], self.bias_values[upper] = self.bias_values[upper], self.bias_values[lower]
                self.replica_ids[lower], self.replica_ids[upper] = self.replica_ids[upper], self.replica_ids[lower]
                self.swap_accepts[lower] += 1
                accepts += 1
        return attempts, accepts

    def attempt_global_q_flip(self, temperature_index: int, *, replica: str) -> bool:
        if replica not in {"a", "b"}:
            raise ValueError("replica must be 'a' or 'b'")
        states = self.spins_a if replica == "a" else self.spins_b
        before_bias = float(self.bias_values[temperature_index])
        before_energy = int(self.energies[temperature_index])
        states[temperature_index] *= -1
        after_bias = float(
            self.bias_energy(
                self.spins_a[temperature_index],
                self.spins_b[temperature_index],
            )
        )
        after_energy = energy(self.spins_a[temperature_index], self.bonds) + energy(
            self.spins_b[temperature_index], self.bonds
        )
        if after_energy != before_energy or not math.isclose(after_bias, before_bias, rel_tol=0.0, abs_tol=2e-12):
            states[temperature_index] *= -1
            raise ValueError("global q flip is not an exact symmetry of the action")
        self.global_rng.random()
        self.global_flip_attempts += 1
        self.bias_values[temperature_index] = after_bias
        return True

    def run_sweeps(self, sweeps: int, progress_every: int | None = None) -> None:
        if sweeps < 0:
            raise ValueError("sweeps must be nonnegative")
        for completed in range(1, sweeps + 1):
            self.attempt_local()
            self.attempt_swaps(self._sweep_count % 2)
            temperature_index = int(self.global_rng.integers(len(self.grid)))
            replica = "a" if int(self.global_rng.integers(2)) == 0 else "b"
            self.attempt_global_q_flip(temperature_index, replica=replica)
            self._sweep_count += 1
            self._record_positions()
            if progress_every and completed % progress_every == 0:
                print(f"biased PT sweep={completed}/{sweeps}", flush=True)
