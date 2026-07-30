from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def periodic_neighbors(x: int, y: int, length: int) -> tuple[tuple[int, int], ...]:
    """Return up, down, left, and right neighbors on a periodic square lattice."""
    if length < 2:
        raise ValueError("length must be at least 2")
    x %= length
    y %= length
    return (
        ((x - 1) % length, y),
        ((x + 1) % length, y),
        (x, (y - 1) % length),
        (x, (y + 1) % length),
    )


def validate_spins(spins: np.ndarray) -> None:
    if spins.ndim != 2 or spins.shape[0] != spins.shape[1]:
        raise ValueError("spins must be a square 2D array")
    if not np.all((spins == 1) | (spins == -1)):
        raise ValueError("all spins must be +1 or -1")


def nearest_neighbor_operator(spins: np.ndarray) -> int:
    """Return S_nn = -sum_<ij> s_i s_j, counting each bond once."""
    validate_spins(spins)
    right = np.roll(spins, shift=-1, axis=1)
    down = np.roll(spins, shift=-1, axis=0)
    return -int(np.sum(spins * (right + down), dtype=np.int64))


def delta_nearest_neighbor_operator(spins: np.ndarray, x: int, y: int) -> int:
    """Exact change in S_nn caused by flipping spins[x, y]."""
    validate_spins(spins)
    length = spins.shape[0]
    spin = int(spins[x, y])
    neighbor_sum = int(
        spins[(x - 1) % length, y]
        + spins[(x + 1) % length, y]
        + spins[x, (y - 1) % length]
        + spins[x, (y + 1) % length]
    )
    return 2 * spin * neighbor_sum


def ising_hamiltonian(spins: np.ndarray, coupling: float) -> float:
    """Return H = -K sum_<ij> s_i s_j with each periodic bond counted once."""
    return float(coupling) * nearest_neighbor_operator(spins)


def delta_hamiltonian(
    spins: np.ndarray,
    x: int,
    y: int,
    coupling: float,
) -> float:
    """Return the exact Hamiltonian change for one proposed spin flip."""
    return float(coupling) * delta_nearest_neighbor_operator(spins, x, y)


@dataclass
class IsingLattice:
    spins: np.ndarray

    def __post_init__(self) -> None:
        self.spins = np.asarray(self.spins, dtype=np.int8)
        validate_spins(self.spins)

    @classmethod
    def random(cls, length: int, rng: np.random.Generator) -> "IsingLattice":
        if length < 2:
            raise ValueError("length must be at least 2")
        spins = rng.choice(np.array([-1, 1], dtype=np.int8), size=(length, length))
        return cls(spins)

    @property
    def length(self) -> int:
        return int(self.spins.shape[0])

    @property
    def n_sites(self) -> int:
        return self.length * self.length

    @property
    def s_nn(self) -> int:
        return nearest_neighbor_operator(self.spins)

    @property
    def magnetization(self) -> int:
        return int(np.sum(self.spins, dtype=np.int64))

    def delta_s_nn(self, x: int, y: int) -> int:
        return delta_nearest_neighbor_operator(self.spins, x, y)

    def flip(self, x: int, y: int) -> None:
        self.spins[x, y] *= -1
