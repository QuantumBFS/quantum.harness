"""Deterministic global and local bases for the Ky Fan hierarchy."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, product

from challenge233.sdp.algebra import PauliWord
from challenge233.sdp.localizers import SafeWord, expand_safe_word
from challenge233.sdp.symmetry import (
    act_on_site,
    dihedral_elements,
)


@dataclass(frozen=True, order=True)
class HierarchyLevel:
    name: str
    range_sites: int
    moment_weight: int
    safe_depth: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", str(self.name))
        object.__setattr__(self, "range_sites", int(self.range_sites))
        object.__setattr__(self, "moment_weight", int(self.moment_weight))
        object.__setattr__(self, "safe_depth", int(self.safe_depth))
        if not self.name:
            raise ValueError("hierarchy level name must be non-empty")
        if self.range_sites < 1:
            raise ValueError("hierarchy range must be positive")
        if self.moment_weight < 0:
            raise ValueError("hierarchy moment weight must be non-negative")
        if self.safe_depth < 0:
            raise ValueError("hierarchy safe depth must be non-negative")


LOCAL_LEVELS = (
    HierarchyLevel("L0", 3, 2, 1),
    HierarchyLevel("L1", 4, 2, 1),
    HierarchyLevel("L2", 4, 3, 2),
    HierarchyLevel("L3", 5, 3, 2),
)


def _validate_size(size: int) -> int:
    size = int(size)
    if size < 4:
        raise ValueError("Ky Fan hierarchy size must be at least 4")
    return size


def _window_sites(
    size: int,
    start: int,
    range_sites: int,
) -> tuple[int, ...]:
    size = _validate_size(size)
    start = int(start) % size
    width = min(int(range_sites), size)
    if width < 1:
        raise ValueError("window range must be positive")
    return tuple((start + offset) % size for offset in range(width))


def _pauli_basis_on_sites(
    sites,
    max_weight: int,
) -> tuple[PauliWord, ...]:
    ordered_sites = tuple(dict.fromkeys(int(site) for site in sites))
    max_weight = int(max_weight)
    if max_weight < 0:
        raise ValueError("maximum Pauli weight must be non-negative")
    words = [PauliWord()]
    for weight in range(
        1,
        min(max_weight, len(ordered_sites)) + 1,
    ):
        for chosen in combinations(ordered_sites, weight):
            for labels in product(("X", "Y", "Z"), repeat=weight):
                words.append(
                    PauliWord(tuple(sorted(zip(chosen, labels))))
                )
    return tuple(sorted(set(words)))


def global_pauli_basis(
    size: int,
    max_weight: int,
) -> tuple[PauliWord, ...]:
    """Enumerate all canonical Pauli words up to a global weight."""
    size = _validate_size(size)
    return _pauli_basis_on_sites(range(size), max_weight)


def local_pauli_basis(
    size: int,
    start: int,
    level: HierarchyLevel,
) -> tuple[PauliWord, ...]:
    """Enumerate a level's Pauli words on one periodic interval."""
    if not isinstance(level, HierarchyLevel):
        raise TypeError("level must be a HierarchyLevel")
    sites = _window_sites(size, start, level.range_sites)
    return _pauli_basis_on_sites(sites, level.moment_weight)


def _polynomial_support(polynomial) -> frozenset[int]:
    return frozenset(
        site
        for word, _ in polynomial.terms
        for site, _ in word.factors
    )


def safe_localizer_basis(
    size: int,
    start: int,
    level: HierarchyLevel,
) -> tuple[SafeWord, ...]:
    """Enumerate distinct safe polynomials supported in one window."""
    if not isinstance(level, HierarchyLevel):
        raise TypeError("level must be a HierarchyLevel")
    size = _validate_size(size)
    window = _window_sites(size, start, level.range_sites)
    window_set = frozenset(window)
    letters = tuple(
        SafeWord(((site, label),))
        for site in window
        for label in ("F", "Z", "P", "n")
    )

    representatives = {}
    identity = SafeWord()
    identity_polynomial = expand_safe_word(identity, size)
    representatives[identity_polynomial] = identity
    for depth in range(1, level.safe_depth + 1):
        for factors in product(letters, repeat=depth):
            word = SafeWord(
                tuple(
                    factor
                    for letter in factors
                    for factor in letter.factors
                )
            )
            polynomial = expand_safe_word(word, size)
            if not _polynomial_support(polynomial) <= window_set:
                continue
            representatives.setdefault(polynomial, word)
    return tuple(
        sorted(
            representatives.values(),
            key=lambda word: (
                len(word.factors),
                word.factors,
            ),
        )
    )


def clique_orbit(
    size: int,
    start: int,
    range_sites: int,
) -> tuple[tuple[int, ...], ...]:
    """Return all distinct translated/reflected interval site sets."""
    size = _validate_size(size)
    seed = _window_sites(size, start, range_sites)
    return tuple(
        sorted(
            {
                tuple(
                    sorted(
                        act_on_site(element, site, size)
                        for site in seed
                    )
                )
                for element in dihedral_elements(size)
            }
        )
    )


def validate_nested_levels(levels) -> None:
    """Reject a declared ladder that drops any earlier word or localizer."""
    levels = tuple(levels)
    if any(not isinstance(level, HierarchyLevel) for level in levels):
        raise TypeError("levels must contain HierarchyLevel values")
    if len({level.name for level in levels}) != len(levels):
        raise ValueError("hierarchy level names must be unique")
    if not levels:
        return
    size = max(20, *(level.range_sites for level in levels))
    pauli_sets = [
        set(local_pauli_basis(size, 0, level))
        for level in levels
    ]
    safe_sets = [
        {
            expand_safe_word(word, size)
            for word in safe_localizer_basis(size, 0, level)
        }
        for level in levels
    ]
    for lower_index, (lower, upper) in enumerate(
        zip(pauli_sets, pauli_sets[1:])
    ):
        if not lower <= upper:
            raise ValueError(
                "hierarchy Pauli bases are not nested at "
                f"level index {lower_index}"
            )
    for lower_index, (lower, upper) in enumerate(
        zip(safe_sets, safe_sets[1:])
    ):
        if not lower <= upper:
            raise ValueError(
                "hierarchy safe localizers are not nested at "
                f"level index {lower_index}"
            )
