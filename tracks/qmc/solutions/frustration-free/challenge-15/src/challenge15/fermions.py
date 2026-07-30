from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations

import numpy as np

from challenge15.spec import SphereSpec


@dataclass(frozen=True, slots=True)
class FermionAction:
    state: int
    sign: float


@dataclass(frozen=True, slots=True)
class DeterminantBasis:
    spec: SphereSpec
    states: tuple[int, ...]
    state_index: dict[int, int]
    total_two_m: int | None = None

    def __post_init__(self) -> None:
        if tuple(sorted(self.states)) != self.states:
            raise ValueError("states must be sorted numerically")
        if len(self.state_index) != len(self.states):
            raise ValueError("state_index must match the basis states")
        for index, state in enumerate(self.states):
            _validate_state(state)
            if state.bit_count() != self.spec.particles:
                raise ValueError("each state must occupy exactly spec.particles orbitals")
            if state >= (1 << self.spec.orbital_count):
                raise ValueError("state exceeds the available orbital count")
            if self.state_index.get(state) != index:
                raise ValueError("state_index must map every state to its sorted index")
            if self.total_two_m is not None and _state_two_m(self.spec, state) != self.total_two_m:
                raise ValueError("state does not belong to the requested two_m sector")

    @property
    def dimension(self) -> int:
        return len(self.states)

    @classmethod
    def full(cls, spec: SphereSpec) -> DeterminantBasis:
        states = _full_states(spec.particles)
        return cls(spec=spec, states=states, state_index=_state_index(states))

    @classmethod
    def with_two_m(cls, spec: SphereSpec, two_m: int) -> DeterminantBasis:
        _validate_two_m(spec, two_m)
        states = _sector_states(spec.particles, two_m)
        return cls(
            spec=spec,
            states=states,
            state_index=_state_index(states),
            total_two_m=two_m,
        )


@dataclass(frozen=True, slots=True)
class OrderedDeterminantBlock:
    """One fixed-width slice of the canonical determinant order."""

    start: int
    states: np.ndarray
    indices: np.ndarray
    valid: np.ndarray

    def __post_init__(self) -> None:
        states = np.asarray(self.states, dtype=np.int64)
        indices = np.asarray(self.indices, dtype=np.int64)
        valid = np.asarray(self.valid, dtype=np.bool_)
        if (
            states.ndim != 1
            or indices.shape != states.shape
            or valid.shape != states.shape
            or states.size == 0
        ):
            raise ValueError("ordered determinant block arrays must have one fixed width")
        if self.start < 0 or not np.array_equal(
            indices[valid], np.arange(self.start, self.start + int(valid.sum()))
        ):
            raise ValueError("ordered determinant block indices are not contiguous")
        for name, value in (
            ("states", states),
            ("indices", indices),
            ("valid", valid),
        ):
            sealed = np.frombuffer(value.tobytes(), dtype=value.dtype).reshape(value.shape)
            object.__setattr__(self, name, sealed)


def iter_ordered_determinant_blocks(
    basis: DeterminantBasis, block_size: int
):
    """Yield canonical fixed-width determinant blocks with explicit padding masks."""

    if not isinstance(basis, DeterminantBasis):
        raise TypeError("basis must be a DeterminantBasis")
    if (
        not isinstance(block_size, int)
        or isinstance(block_size, bool)
        or block_size <= 0
    ):
        raise ValueError("block_size must be a positive Python integer")
    yield from _cached_ordered_determinant_blocks(basis.states, block_size)


@lru_cache(maxsize=64)
def _cached_ordered_determinant_blocks(
    ordered_states: tuple[int, ...], block_size: int
) -> tuple[OrderedDeterminantBlock, ...]:
    blocks = []
    for start in range(0, len(ordered_states), block_size):
        stop = min(start + block_size, len(ordered_states))
        width = stop - start
        block_states = np.zeros(block_size, dtype=np.int64)
        indices = np.full(block_size, -1, dtype=np.int64)
        valid = np.zeros(block_size, dtype=np.bool_)
        block_states[:width] = ordered_states[start:stop]
        indices[:width] = np.arange(start, stop, dtype=np.int64)
        valid[:width] = True
        blocks.append(
            OrderedDeterminantBlock(
                start=start,
                states=block_states,
                indices=indices,
                valid=valid,
            )
        )
    return tuple(blocks)


def apply_creation(state: int, orbital: int) -> FermionAction | None:
    _validate_orbital(state, orbital)
    if state & (1 << orbital):
        return None
    sign = _fermion_sign(state, orbital)
    return FermionAction(state=state | (1 << orbital), sign=sign)


def apply_annihilation(state: int, orbital: int) -> FermionAction | None:
    _validate_orbital(state, orbital)
    if not state & (1 << orbital):
        return None
    sign = _fermion_sign(state, orbital)
    return FermionAction(state=state ^ (1 << orbital), sign=sign)


def apply_one_body(state: int, source: int, target: int) -> FermionAction | None:
    _validate_orbital(state, source)
    _validate_orbital(state, target)
    removed = apply_annihilation(state, source)
    if removed is None:
        return None
    created = apply_creation(removed.state, target)
    if created is None:
        return None
    return FermionAction(state=created.state, sign=removed.sign * created.sign)


def basis_vector(basis: DeterminantBasis, state: int) -> int:
    return basis.state_index[state]


def state_two_m(spec: SphereSpec, state: int) -> int:
    return _state_two_m(spec, state)


def _build_states(spec: SphereSpec) -> tuple[int, ...]:
    states = []
    for occupied in combinations(range(spec.orbital_count), spec.particles):
        state = 0
        for orbital in occupied:
            state |= 1 << orbital
        states.append(state)
    return tuple(states)


def _state_index(states: tuple[int, ...]) -> dict[int, int]:
    return {state: index for index, state in enumerate(states)}


@lru_cache(maxsize=None)
def _full_states(particles: int) -> tuple[int, ...]:
    return tuple(sorted(_build_states(SphereSpec(particles))))


@lru_cache(maxsize=None)
def _sector_states(particles: int, two_m: int) -> tuple[int, ...]:
    spec = SphereSpec(particles)
    return tuple(state for state in _full_states(particles) if _state_two_m(spec, state) == two_m)


def _validate_state(state: int) -> None:
    if not isinstance(state, int) or isinstance(state, bool) or state < 0:
        raise ValueError("state must be a nonnegative integer bit pattern")


def _validate_two_m(spec: SphereSpec, two_m: int) -> None:
    if not isinstance(two_m, int) or isinstance(two_m, bool):
        raise ValueError("two_m must be a Python integer")
    if two_m % 2 != 0:
        raise ValueError("two_m must lie on the doubled many-body M lattice")
    if abs(two_m) > spec.particles * spec.two_q:
        raise ValueError("two_m must satisfy |two_m| <= particles * two_q")


def _validate_orbital(state: int, orbital: int) -> None:
    _validate_state(state)
    if not isinstance(orbital, int) or isinstance(orbital, bool) or orbital < 0:
        raise ValueError("orbital must be a nonnegative integer")


def _fermion_sign(state: int, orbital: int) -> float:
    lower_mask = (1 << orbital) - 1
    return -1.0 if (state & lower_mask).bit_count() % 2 else 1.0


def _state_two_m(spec: SphereSpec, state: int) -> int:
    total = 0
    for orbital, two_m in enumerate(spec.two_m_values):
        if state & (1 << orbital):
            total += two_m
    return total
