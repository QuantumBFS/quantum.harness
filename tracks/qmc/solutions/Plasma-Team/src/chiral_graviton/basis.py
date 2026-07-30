"""Lowest-Landau-level Fock bases on the Haldane sphere."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations


@dataclass(frozen=True)
class SphereSystem:
    """Spin-polarized electrons in one monopole-harmonic shell."""

    n_electrons: int
    two_q: int

    def __post_init__(self) -> None:
        if self.n_electrons < 1:
            raise ValueError("CG001: n_electrons must be positive")
        if self.two_q < 0:
            raise ValueError("CG001: two_q must be non-negative")
        if self.n_electrons > self.n_orbitals:
            raise ValueError("CG001: more electrons than LLL orbitals")

    @classmethod
    def from_electron_count(cls, n_electrons: int) -> SphereSystem:
        """Construct the nu=1/3 Laughlin-shift system, 2Q=3(N-1)."""

        return cls(n_electrons=n_electrons, two_q=3 * (n_electrons - 1))

    @property
    def n_orbitals(self) -> int:
        return self.two_q + 1

    @property
    def radius_over_lb(self) -> float:
        return (self.two_q / 2.0) ** 0.5

    @property
    def two_m_values(self) -> tuple[int, ...]:
        return tuple(range(-self.two_q, self.two_q + 1, 2))


@dataclass(frozen=True)
class FockBasis:
    """Fixed-particle-number and fixed-Lz fermion basis.

    Determinants are non-negative integers whose set bits label occupied
    monopole orbitals ordered by increasing m.
    """

    system: SphereSystem
    two_lz: int
    states: tuple[int, ...]

    def __init__(self, system: SphereSystem, two_lz: int):
        if (two_lz - system.n_electrons * system.two_q) % 2:
            # Sum of N labels, each congruent to 2Q modulo two.
            raise ValueError("CG002: two_lz has incompatible parity")

        states: list[int] = []
        two_m = system.two_m_values
        for occupied in combinations(range(system.n_orbitals), system.n_electrons):
            if sum(two_m[i] for i in occupied) == two_lz:
                state = 0
                for orbital in occupied:
                    state |= 1 << orbital
                states.append(state)

        object.__setattr__(self, "system", system)
        object.__setattr__(self, "two_lz", int(two_lz))
        object.__setattr__(self, "states", tuple(states))

    @property
    def dimension(self) -> int:
        return len(self.states)

    @property
    def index(self) -> dict[int, int]:
        return {state: i for i, state in enumerate(self.states)}

    def occupied(self, state: int) -> tuple[int, ...]:
        return tuple(i for i in range(self.system.n_orbitals) if state & (1 << i))

    def occupancy_matrix(self):
        """Return a float64 matrix of zero/one occupation features."""

        import numpy as np

        out = np.zeros((self.dimension, self.system.n_orbitals), dtype=np.float64)
        for row, state in enumerate(self.states):
            out[row, list(self.occupied(state))] = 1.0
        return out


def _parity_below(state: int, orbital: int) -> int:
    return -1 if (state & ((1 << orbital) - 1)).bit_count() % 2 else 1


def apply_annihilation(state: int, orbital: int) -> tuple[int, int] | None:
    """Apply c_orbital and return ``(new_state, fermionic_sign)``."""

    if orbital < 0 or not state & (1 << orbital):
        return None
    return state ^ (1 << orbital), _parity_below(state, orbital)


def apply_creation(state: int, orbital: int) -> tuple[int, int] | None:
    """Apply c_orbital^dagger and return ``(new_state, fermionic_sign)``."""

    if orbital < 0 or state & (1 << orbital):
        return None
    return state | (1 << orbital), _parity_below(state, orbital)


def apply_one_body(state: int, create: int, annihilate: int) -> tuple[int, int] | None:
    """Apply c_create^dagger c_annihilate."""

    first = apply_annihilation(state, annihilate)
    if first is None:
        return None
    state1, sign1 = first
    second = apply_creation(state1, create)
    if second is None:
        return None
    state2, sign2 = second
    return state2, sign1 * sign2


def apply_two_body(
    state: int, create_a: int, create_b: int, annihilate_c: int, annihilate_d: int
) -> tuple[int, int] | None:
    """Apply c_a^dagger c_b^dagger c_d c_c in right-to-left order."""

    current = state
    sign = 1
    for operation, orbital in (
        (apply_annihilation, annihilate_c),
        (apply_annihilation, annihilate_d),
        (apply_creation, create_b),
        (apply_creation, create_a),
    ):
        result = operation(current, orbital)
        if result is None:
            return None
        current, local_sign = result
        sign *= local_sign
    return current, sign
