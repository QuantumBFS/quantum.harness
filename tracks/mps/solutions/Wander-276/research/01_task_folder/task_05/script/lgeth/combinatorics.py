"""Exact root combinatorics for geometric-accessibility filtrations."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from math import comb
from typing import Iterator


Occupation = tuple[int, ...]


@dataclass(frozen=True)
class RootPartition:
    """Partition a fixed-particle root space by deletion accessibility."""

    n_particles: int
    n_flux: int
    q: int
    k: int
    r: int
    states: tuple[Occupation, ...]
    zero_modes: tuple[int, ...]
    descendants: tuple[int, ...]
    descendant_external: tuple[int, ...]
    primitive: tuple[int, ...]


def occupation_states(
    n_particles: int,
    n_orbitals: int,
) -> Iterator[Occupation]:
    """Yield weak compositions in deterministic lexicographic order."""

    particles = int(n_particles)
    orbitals = int(n_orbitals)
    if particles < 0:
        raise ValueError("n_particles must be nonnegative")
    if orbitals <= 0:
        raise ValueError("n_orbitals must be positive")

    def recurse(remaining: int, length: int) -> Iterator[Occupation]:
        if length == 1:
            yield (remaining,)
            return
        for population in range(remaining + 1):
            for suffix in recurse(remaining - population, length - 1):
                yield (population,) + suffix

    yield from recurse(particles, orbitals)


def cyclic_kr_admissible(
    state: Occupation,
    k: int,
    r: int,
) -> bool:
    """Return whether every cyclic window of length ``r`` contains at most ``k``."""

    if not state:
        raise ValueError("state must be nonempty")
    cluster = int(k)
    window = int(r)
    if cluster < 0:
        raise ValueError("k must be nonnegative")
    if window <= 0 or window > len(state):
        raise ValueError("r must lie between one and the orbital count")
    return all(
        sum(
            state[(start + offset) % len(state)]
            for offset in range(window)
        )
        <= cluster
        for start in range(len(state))
    )


def _validate_laughlin_domain(
    n_particles: int,
    n_flux: int,
) -> tuple[int, int]:
    particles = int(n_particles)
    flux = int(n_flux)
    if particles <= 0:
        raise ValueError("n_particles must be positive")
    if flux < 2 * particles:
        raise ValueError("n_flux must be at least 2*n_particles")
    return particles, flux


def laughlin_zero_mode_count(
    n_particles: int,
    n_flux: int,
) -> int:
    """Return the cyclic bosonic Laughlin ``(1,2)`` root count."""

    particles, flux = _validate_laughlin_domain(
        n_particles,
        n_flux,
    )
    return (
        flux
        * comb(flux - particles, particles)
        // (flux - particles)
    )


def laughlin_onebody_capacity(
    n_particles: int,
    n_flux: int,
) -> int:
    """Return ``dim(W_N^(1)/P_N)`` for cyclic Laughlin roots."""

    particles, flux = _validate_laughlin_domain(
        n_particles,
        n_flux,
    )
    if particles == 1:
        return 0
    return 2 * flux * comb(flux - particles, particles - 2)


def _bounded_removals(
    state: Occupation,
    total: int,
) -> Iterator[Occupation]:
    """Yield occupation removals bounded componentwise by ``state``."""

    target = int(total)

    def recurse(
        orbital: int,
        remaining: int,
        prefix: Occupation,
    ) -> Iterator[Occupation]:
        if orbital == len(state):
            if remaining == 0:
                yield prefix
            return
        maximum = min(state[orbital], remaining)
        for removed in range(maximum + 1):
            yield from recurse(
                orbital + 1,
                remaining - removed,
                prefix + (removed,),
            )

    yield from recurse(0, target, ())


@lru_cache(maxsize=None)
def _deletion_accessible(
    state: Occupation,
    q: int,
    k: int,
    r: int,
) -> bool:
    for removal in _bounded_removals(state, q):
        reduced = tuple(
            population - removed
            for population, removed in zip(state, removal, strict=True)
        )
        if cyclic_kr_admissible(reduced, k=k, r=r):
            return True
    return False


def root_descendant_partition(
    n_particles: int,
    n_flux: int,
    q: int,
    k: int = 1,
    r: int = 2,
) -> RootPartition:
    """Partition roots by whether deleting ``q`` particles leaves an admissible root."""

    particles = int(n_particles)
    flux = int(n_flux)
    body_order = int(q)
    if particles <= 0:
        raise ValueError("n_particles must be positive")
    if flux <= 0:
        raise ValueError("n_flux must be positive")
    if body_order < 0 or body_order > particles:
        raise ValueError("q must lie between zero and n_particles")
    if r > flux:
        raise ValueError("r cannot exceed n_flux")

    states = tuple(occupation_states(particles, flux))
    zero_modes = tuple(
        index
        for index, state in enumerate(states)
        if cyclic_kr_admissible(state, k=k, r=r)
    )
    descendants = tuple(
        index
        for index, state in enumerate(states)
        if _deletion_accessible(
            state,
            q=body_order,
            k=int(k),
            r=int(r),
        )
    )
    zero_set = set(zero_modes)
    descendant_set = set(descendants)
    descendant_external = tuple(sorted(descendant_set - zero_set))
    primitive = tuple(
        sorted(set(range(len(states))) - descendant_set)
    )
    return RootPartition(
        n_particles=particles,
        n_flux=flux,
        q=body_order,
        k=int(k),
        r=int(r),
        states=states,
        zero_modes=zero_modes,
        descendants=descendants,
        descendant_external=descendant_external,
        primitive=primitive,
    )
