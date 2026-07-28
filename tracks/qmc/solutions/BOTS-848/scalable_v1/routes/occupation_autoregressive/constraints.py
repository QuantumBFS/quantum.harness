from __future__ import annotations

from collections.abc import Mapping
from dataclasses import InitVar, dataclass
from numbers import Integral
from types import MappingProxyType

import numpy as np


MAX_ENUMERATED_SUPPORT = 100_000
_CONSTRUCTION_TOKEN = object()


def _integer(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(f"{name} must be an integer")
    return int(value)


def _randbelow(rng: np.random.Generator, upper: int) -> int:
    """Draw uniformly from ``range(upper)`` for an arbitrary-size integer."""

    bound = _integer("upper", upper)
    if bound <= 0:
        raise ValueError("upper must be positive")
    bit_count = (bound - 1).bit_length()
    if bit_count == 0:
        return 0
    byte_count = (bit_count + 7) // 8
    mask = (1 << bit_count) - 1
    while True:
        candidate = int.from_bytes(rng.bytes(byte_count), "little") & mask
        if candidate < bound:
            return candidate


def occupation_m2(bitset: int, two_q: int) -> int:
    """Return twice the total magnetic quantum number of an occupation bitset."""

    state = _integer("bitset", bitset)
    orbital_limit = _integer("two_q", two_q)
    if state < 0:
        raise ValueError("bitset must be non-negative")
    if orbital_limit < 0:
        raise ValueError("two_q must be non-negative")
    if state >= 1 << (orbital_limit + 1):
        raise ValueError("bitset has an occupation outside the orbital range")
    return sum(
        -orbital_limit + 2 * orbital
        for orbital in range(orbital_limit + 1)
        if state & (1 << orbital)
    )


@dataclass(frozen=True)
class FeasibilityTable:
    """Completion counts for exact fixed-particle, fixed-M sampling."""

    n_electrons: int
    two_q: int
    target_m2: int
    counts: Mapping[tuple[int, int, int], int]
    _construction_token: InitVar[object | None] = None

    def __post_init__(self, _construction_token: object | None) -> None:
        if _construction_token is not _CONSTRUCTION_TOKEN:
            raise TypeError("FeasibilityTable instances must be created with build()")
        object.__setattr__(self, "counts", MappingProxyType(dict(self.counts)))

    @classmethod
    def _from_counts(
        cls,
        n_electrons: int,
        two_q: int,
        target_m2: int,
        counts: Mapping[tuple[int, int, int], int],
    ) -> FeasibilityTable:
        return cls(
            n_electrons,
            two_q,
            target_m2,
            counts,
            _construction_token=_CONSTRUCTION_TOKEN,
        )

    @classmethod
    def build(
        cls,
        n_electrons: int,
        two_q: int,
        target_m2: int,
    ) -> FeasibilityTable:
        particles = _integer("n_electrons", n_electrons)
        orbital_limit = _integer("two_q", two_q)
        target = _integer("target_m2", target_m2)
        if particles < 0:
            raise ValueError("n_electrons must be non-negative")
        if orbital_limit < 0:
            raise ValueError("two_q must be non-negative")
        if particles > orbital_limit + 1:
            raise ValueError("n_electrons exceeds the orbital count")
        target_limit = particles * orbital_limit
        if not -target_limit <= target <= target_limit:
            raise ValueError("target_m2 is outside the possible range")

        counts: dict[tuple[int, int, int], int] = {
            (orbital_limit + 1, 0, 0): 1,
        }
        for orbital in range(orbital_limit, -1, -1):
            m2 = -orbital_limit + 2 * orbital
            for remaining in range(particles + 1):
                for remaining_m2 in range(-target_limit, target_limit + 1):
                    total = counts.get(
                        (orbital + 1, remaining, remaining_m2),
                        0,
                    )
                    if remaining:
                        total += counts.get(
                            (orbital + 1, remaining - 1, remaining_m2 - m2),
                            0,
                        )
                    if total:
                        counts[(orbital, remaining, remaining_m2)] = total

        if counts.get((0, particles, target), 0) == 0:
            raise ValueError("empty fixed-N fixed-M sector")
        return cls._from_counts(particles, orbital_limit, target, counts)

    def allowed(
        self,
        orbital: int,
        remaining: int,
        target_m2: int,
    ) -> tuple[bool, bool]:
        orbital_index = _integer("orbital", orbital)
        particles_left = _integer("remaining", remaining)
        target_left = _integer("target_m2", target_m2)
        if not 0 <= orbital_index <= self.two_q:
            raise ValueError(f"orbital must be in [0, {self.two_q}]")
        if not 0 <= particles_left <= self.n_electrons:
            raise ValueError(
                f"remaining must be in [0, {self.n_electrons}]"
            )
        target_limit = particles_left * self.two_q
        if not -target_limit <= target_left <= target_limit:
            raise ValueError("target_m2 is outside the remaining occupation range")

        m2 = -self.two_q + 2 * orbital_index
        zero = self.counts.get(
            (orbital_index + 1, particles_left, target_left),
            0,
        ) > 0
        one = particles_left > 0 and self.counts.get(
            (orbital_index + 1, particles_left - 1, target_left - m2),
            0,
        ) > 0
        return zero, one

    def sample_uniform(self, size: int, *, seed: int) -> np.ndarray:
        """Draw configurations uniformly without leaving the constrained sector."""

        sample_count = _integer("size", size)
        random_seed = _integer("seed", seed)
        if sample_count < 0:
            raise ValueError("size must be non-negative")
        if random_seed < 0:
            raise ValueError("seed must be non-negative")

        rng = np.random.default_rng(random_seed)
        draws = np.empty(sample_count, dtype=object)
        for draw_index in range(sample_count):
            state = 0
            remaining = self.n_electrons
            target_left = self.target_m2
            for orbital in range(self.two_q + 1):
                m2 = -self.two_q + 2 * orbital
                zero_count = self.counts.get(
                    (orbital + 1, remaining, target_left),
                    0,
                )
                one_count = (
                    self.counts.get(
                        (orbital + 1, remaining - 1, target_left - m2),
                        0,
                    )
                    if remaining
                    else 0
                )
                total = zero_count + one_count
                if total == 0:
                    raise RuntimeError("feasibility table has no valid continuation")
                choose_one = zero_count == 0 or (
                    one_count > 0 and _randbelow(rng, total) >= zero_count
                )
                if choose_one:
                    state |= 1 << orbital
                    remaining -= 1
                    target_left -= m2
            if remaining != 0 or target_left != 0:
                raise RuntimeError("feasibility table produced an invalid draw")
            draws[draw_index] = state
        return draws

    def enumerate_support(self) -> tuple[int, ...]:
        """Enumerate tiny supports for tests without allocating physical sectors."""

        if self.n_electrons > 4:
            raise ValueError("enumerate_support supports at most 4 electrons")
        support_count = self.counts[(0, self.n_electrons, self.target_m2)]
        if support_count > MAX_ENUMERATED_SUPPORT:
            raise ValueError(
                f"support size {support_count} exceeds enumerate_support limit "
                f"{MAX_ENUMERATED_SUPPORT}"
            )

        support: list[int] = []
        stack = [(0, self.n_electrons, self.target_m2, 0)]
        while stack:
            orbital, remaining, target_left, state = stack.pop()
            if orbital == self.two_q + 1:
                if remaining == 0 and target_left == 0:
                    support.append(state)
                continue
            zero, one = self.allowed(orbital, remaining, target_left)
            if one:
                m2 = -self.two_q + 2 * orbital
                stack.append(
                    (
                        orbital + 1,
                        remaining - 1,
                        target_left - m2,
                        state | (1 << orbital),
                    )
                )
            if zero:
                stack.append((orbital + 1, remaining, target_left, state))
        return tuple(support)
