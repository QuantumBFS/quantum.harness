"""Random-bond Ising transfer evolution on the Nishimori line."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


NISHIMORI_P_CRITICAL = 0.1092212


def nishimori_coupling(p_antiferromagnetic: float) -> float:
    r"""Return \(K\) satisfying \(p/(1-p)=\exp(-2K)\)."""

    p = float(p_antiferromagnetic)
    if not 0.0 < p < 0.5:
        raise ValueError("antiferromagnetic probability must lie in (0, 1/2)")
    return float(0.5 * np.log((1.0 - p) / p))


@dataclass(frozen=True, slots=True)
class NishimoriEstimate:
    """Block estimate of the quenched free-energy rate."""

    length: int
    p_antiferromagnetic: float
    coupling: float
    rows: int
    burn_in: int
    block_size: int
    blocks: NDArray[np.float64]

    @property
    def mean(self) -> float:
        return float(np.mean(self.blocks))

    @property
    def standard_error(self) -> float:
        if self.blocks.size < 2:
            return float("nan")
        return float(np.std(self.blocks, ddof=1) / np.sqrt(self.blocks.size))


@dataclass(frozen=True, slots=True)
class CoupledNishimoriEstimate:
    """Block free energies for several widths under nested common disorder."""

    lengths: NDArray[np.int64]
    p_antiferromagnetic: float
    coupling: float
    rows: int
    burn_in: int
    block_size: int
    blocks: NDArray[np.float64]

    @property
    def means(self) -> NDArray[np.float64]:
        return np.mean(self.blocks, axis=0)

    @property
    def covariance_of_mean(self) -> NDArray[np.float64]:
        return np.cov(self.blocks, rowvar=False, ddof=1) / self.blocks.shape[0]


class RandomBondIsingCylinder:
    r"""Matrix-free row transfer operator for the periodic \(\pm J\) RBIM."""

    def __init__(self, length: int, coupling: float):
        if length < 3:
            raise ValueError("periodic RBIM cylinder requires length >= 3")
        if coupling <= 0.0:
            raise ValueError("coupling must be positive")
        self.length = int(length)
        self.coupling = float(coupling)
        states = np.arange(1 << self.length, dtype=np.uint64)
        bits = (
            (states[:, None] >> np.arange(self.length, dtype=np.uint64)) & 1
        )
        spins = 2.0 * bits.astype(float) - 1.0
        self._horizontal_products = spins * np.roll(spins, -1, axis=1)

    def horizontal_weight(
        self, horizontal_bonds: NDArray[np.int8]
    ) -> NDArray[np.float64]:
        bonds = np.asarray(horizontal_bonds, dtype=np.int8)
        if bonds.shape != (self.length,) or not np.all(np.abs(bonds) == 1):
            raise ValueError("horizontal bonds must be a length-L ±1 vector")
        return np.exp(self.coupling * (self._horizontal_products @ bonds))

    def apply_vertical(
        self,
        vector: NDArray[np.float64],
        vertical_bonds: NDArray[np.int8],
    ) -> NDArray[np.float64]:
        bonds = np.asarray(vertical_bonds, dtype=np.int8)
        if bonds.shape != (self.length,) or not np.all(np.abs(bonds) == 1):
            raise ValueError("vertical bonds must be a length-L ±1 vector")
        output = np.asarray(vector, dtype=float)
        if output.shape != (1 << self.length,):
            raise ValueError("state vector has the wrong size")
        tensor = output.reshape((2,) * self.length)
        spin = np.array([-1.0, 1.0])
        products = spin[:, None] * spin[None, :]
        for site, bond in enumerate(bonds):
            axis = self.length - 1 - site
            local = np.exp(self.coupling * bond * products)
            tensor = np.tensordot(local, tensor, axes=(1, axis))
            tensor = np.moveaxis(tensor, 0, axis)
        return tensor.reshape(-1)

    def apply_row(
        self,
        vector: NDArray[np.float64],
        vertical_bonds: NDArray[np.int8],
        horizontal_bonds: NDArray[np.int8],
    ) -> NDArray[np.float64]:
        output = self.apply_vertical(vector, vertical_bonds)
        output *= self.horizontal_weight(horizontal_bonds)
        return output

    def dense_row(
        self,
        vertical_bonds: NDArray[np.int8],
        horizontal_bonds: NDArray[np.int8],
    ) -> NDArray[np.float64]:
        dimension = 1 << self.length
        basis = np.eye(dimension)
        return np.column_stack(
            [
                self.apply_row(
                    basis[:, column], vertical_bonds, horizontal_bonds
                )
                for column in range(dimension)
            ]
        )


def _random_bonds(
    rng: np.random.Generator, length: int, p_antiferromagnetic: float
) -> NDArray[np.int8]:
    return np.where(
        rng.random(length) < p_antiferromagnetic, -1, 1
    ).astype(np.int8)


def estimate_nishimori_free_energy(
    length: int,
    *,
    p_antiferromagnetic: float = NISHIMORI_P_CRITICAL,
    rows: int = 20_000,
    burn_in: int = 1_000,
    block_size: int = 200,
    seed: int = 0,
) -> NishimoriEstimate:
    r"""Estimate \(-\lambda_1\) with stabilized positive-vector iteration."""

    if rows < block_size or rows % block_size:
        raise ValueError("rows must be a positive multiple of block_size")
    if burn_in < 0:
        raise ValueError("burn_in must be nonnegative")
    coupling = nishimori_coupling(p_antiferromagnetic)
    cylinder = RandomBondIsingCylinder(length, coupling)
    rng = np.random.default_rng(seed)
    vector = np.full(1 << length, 1.0 / (1 << length))

    def step(current: NDArray[np.float64]) -> tuple[NDArray[np.float64], float]:
        vertical = _random_bonds(rng, length, p_antiferromagnetic)
        horizontal = _random_bonds(rng, length, p_antiferromagnetic)
        updated = cylinder.apply_row(current, vertical, horizontal)
        norm = float(np.sum(updated))
        if not np.isfinite(norm) or norm <= 0.0:
            raise FloatingPointError("non-finite transfer-vector norm")
        return updated / norm, float(np.log(norm))

    for _ in range(burn_in):
        vector, _ = step(vector)
    blocks = np.empty(rows // block_size)
    for block in range(blocks.size):
        log_growth = 0.0
        for _ in range(block_size):
            vector, increment = step(vector)
            log_growth += increment
        blocks[block] = -log_growth / block_size
    return NishimoriEstimate(
        length=length,
        p_antiferromagnetic=float(p_antiferromagnetic),
        coupling=coupling,
        rows=rows,
        burn_in=burn_in,
        block_size=block_size,
        blocks=blocks,
    )


def estimate_coupled_nishimori_free_energies(
    lengths: list[int] | NDArray[np.int64],
    *,
    p_antiferromagnetic: float = NISHIMORI_P_CRITICAL,
    rows: int = 20_000,
    burn_in: int = 1_000,
    block_size: int = 200,
    seed: int = 0,
) -> CoupledNishimoriEstimate:
    """Evolve widths with nested common random bonds."""

    size_array = np.asarray(lengths, dtype=int)
    if (
        size_array.ndim != 1
        or size_array.size < 3
        or np.unique(size_array).size != size_array.size
    ):
        raise ValueError("lengths must contain at least three unique widths")
    if np.any(size_array < 3):
        raise ValueError("all periodic widths must be at least three")
    if rows < block_size or rows % block_size:
        raise ValueError("rows must be a positive multiple of block_size")
    if burn_in < 0:
        raise ValueError("burn_in must be nonnegative")
    size_array = np.sort(size_array)
    coupling = nishimori_coupling(p_antiferromagnetic)
    cylinders = [
        RandomBondIsingCylinder(int(length), coupling)
        for length in size_array
    ]
    vectors = [
        np.full(1 << int(length), 1.0 / (1 << int(length)))
        for length in size_array
    ]
    rng = np.random.default_rng(seed)
    maximum_length = int(size_array[-1])

    def coupled_step() -> NDArray[np.float64]:
        vertical = _random_bonds(rng, maximum_length, p_antiferromagnetic)
        horizontal = _random_bonds(rng, maximum_length, p_antiferromagnetic)
        increments = np.empty(size_array.size)
        for index, (length, cylinder) in enumerate(
            zip(size_array, cylinders, strict=True)
        ):
            width = int(length)
            updated = cylinder.apply_row(
                vectors[index], vertical[:width], horizontal[:width]
            )
            norm = float(np.sum(updated))
            if not np.isfinite(norm) or norm <= 0.0:
                raise FloatingPointError("non-finite transfer-vector norm")
            vectors[index] = updated / norm
            increments[index] = np.log(norm)
        return increments

    for _ in range(burn_in):
        coupled_step()
    blocks = np.empty((rows // block_size, size_array.size))
    for block in range(blocks.shape[0]):
        log_growth = np.zeros(size_array.size)
        for _ in range(block_size):
            log_growth += coupled_step()
        blocks[block] = -log_growth / block_size
    return CoupledNishimoriEstimate(
        lengths=size_array.astype(np.int64),
        p_antiferromagnetic=float(p_antiferromagnetic),
        coupling=coupling,
        rows=rows,
        burn_in=burn_in,
        block_size=block_size,
        blocks=blocks,
    )
