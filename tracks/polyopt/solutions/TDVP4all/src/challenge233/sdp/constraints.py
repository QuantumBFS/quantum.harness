from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from challenge233.sdp.algebra import (
    GaussianRational,
    PauliPolynomial,
    PauliWord,
    add_polynomials,
    adjoint_polynomial,
    expand_word,
    multiply_polynomials,
    polynomial_from_word,
    scale_polynomial,
)
from challenge233.sdp.symmetry import (
    DihedralElement,
    act_on_polynomial,
    dihedral_elements,
    dihedral_irrep_catalog,
    representation_permutation,
    sector_multiplicities,
)


@dataclass(frozen=True)
class MomentEntry:
    row: int
    column: int
    polynomial: PauliPolynomial


@dataclass(frozen=True)
class ZeroLocalizerRow:
    site: int
    row: int
    column: int
    polynomial: PauliPolynomial


@dataclass(frozen=True)
class IndexOrbit:
    representative: int
    members: tuple


@dataclass(frozen=True)
class ConstraintMap:
    """Legacy equivariance map; arbitrary sandwiches are not solver rows."""

    size: int
    moment_basis: tuple
    localizer_basis: tuple
    moment_entries: tuple
    zero_localizers: tuple
    group_elements: tuple
    moment_basis_permutations: tuple
    localizer_basis_permutations: tuple
    moment_entry_permutations: tuple
    zero_localizer_permutations: tuple
    irrep_catalog: tuple
    moment_sector_multiplicities: tuple
    localizer_sector_multiplicities: tuple
    moment_entry_orbits: tuple
    zero_localizer_orbits: tuple
    assembly_statistics: dict


def blockade_polynomial(site: int, size: int) -> PauliPolynomial:
    """Return the exact periodic blockade projector C_i=n_i n_{i+1}."""
    size = int(size)
    if size < 2:
        raise ValueError("blockade size must be at least 2")
    site = int(site)
    if not 0 <= site < size:
        raise ValueError(
            f"site must lie in range(size), got site={site}, size={size}"
        )
    return expand_word(
        (
            (site, "n"),
            ((site + 1) % size, "n"),
        )
    )


def pxp_hamiltonian_polynomial(
    size: int,
    detuning: Fraction,
) -> PauliPolynomial:
    """Return the exact periodic PXP Hamiltonian at rational detuning."""
    size = int(size)
    if size < 4:
        raise ValueError("PXP Hamiltonian size must be at least 4")
    if not isinstance(detuning, Fraction):
        raise TypeError("detuning must be a Fraction")

    detuning_coefficient = GaussianRational(
        -detuning,
        Fraction(0),
    )
    terms = []
    for site in range(size):
        terms.append(
            expand_word(
                (
                    ((site - 1) % size, "P"),
                    (site, "X"),
                    ((site + 1) % size, "P"),
                )
            )
        )
        terms.append(
            scale_polynomial(
                detuning_coefficient,
                expand_word(((site, "n"),)),
            )
        )
    return add_polynomials(*terms)


def _validate_constraint_size(size: int) -> int:
    size = int(size)
    if size < 4:
        raise ValueError("constraint-map size must be at least 4")
    return size


def _validate_basis_words(name: str, basis, size: int) -> tuple:
    basis = tuple(basis)
    for word in basis:
        if not isinstance(word, PauliWord):
            raise TypeError(
                f"every {name} element must be a PauliWord"
            )
        for site, _ in word.factors:
            if not 0 <= site < size:
                raise ValueError(
                    f"{name} factor site must lie in range(size): "
                    f"site={site}, size={size}"
                )
    if len(set(basis)) != len(basis):
        raise ValueError(f"{name} contains duplicate words")
    return basis


def _basis_permutations(
    name: str,
    basis: tuple,
    group_elements: tuple,
    size: int,
) -> tuple:
    result = []
    for element in group_elements:
        try:
            permutation = representation_permutation(
                element,
                basis,
                size,
            )
        except ValueError as error:
            raise ValueError(
                f"{name} is not closed under D_N"
            ) from error
        result.append(permutation)
    return tuple(result)


def _moment_entries(moment_basis: tuple) -> tuple:
    word_polynomials = tuple(
        polynomial_from_word(word)
        for word in moment_basis
    )
    adjoints = tuple(
        adjoint_polynomial(polynomial)
        for polynomial in word_polynomials
    )
    return tuple(
        MomentEntry(
            row=row,
            column=column,
            polynomial=multiply_polynomials(
                adjoints[row],
                word_polynomials[column],
            ),
        )
        for row in range(len(moment_basis))
        for column in range(len(moment_basis))
    )


def _zero_localizers(
    size: int,
    localizer_basis: tuple,
) -> tuple:
    word_polynomials = tuple(
        polynomial_from_word(word)
        for word in localizer_basis
    )
    adjoints = tuple(
        adjoint_polynomial(polynomial)
        for polynomial in word_polynomials
    )
    blockades = tuple(
        blockade_polynomial(site, size)
        for site in range(size)
    )
    return tuple(
        ZeroLocalizerRow(
            site=site,
            row=row,
            column=column,
            polynomial=multiply_polynomials(
                multiply_polynomials(
                    adjoints[row],
                    blockades[site],
                ),
                word_polynomials[column],
            ),
        )
        for site in range(size)
        for row in range(len(localizer_basis))
        for column in range(len(localizer_basis))
    )


def _moment_entry_permutation(
    basis_permutation: tuple,
) -> tuple:
    basis_size = len(basis_permutation)
    return tuple(
        basis_permutation[row] * basis_size
        + basis_permutation[column]
        for row in range(basis_size)
        for column in range(basis_size)
    )


def _blockade_site_image(
    element: DihedralElement,
    site: int,
    size: int,
) -> int:
    if element.reflected:
        return (element.shift - site - 1) % size
    return (element.shift + site) % size


def _zero_localizer_permutation(
    element: DihedralElement,
    basis_permutation: tuple,
    size: int,
) -> tuple:
    basis_size = len(basis_permutation)
    block_size = basis_size**2
    return tuple(
        _blockade_site_image(element, site, size) * block_size
        + basis_permutation[row] * basis_size
        + basis_permutation[column]
        for site in range(size)
        for row in range(basis_size)
        for column in range(basis_size)
    )


def _validate_equivariance(
    size: int,
    group_elements: tuple,
    entries: tuple,
    permutations: tuple,
    component: str,
) -> None:
    for element, permutation in zip(
        group_elements,
        permutations,
    ):
        if sorted(permutation) != list(range(len(entries))):
            raise ValueError(
                f"{component} action is not a permutation"
            )
        for source, destination in enumerate(permutation):
            transformed = act_on_polynomial(
                element,
                entries[source].polynomial,
                size,
            )
            if transformed != entries[destination].polynomial:
                raise ValueError(
                    f"{component} polynomial is not D_N-equivariant: "
                    f"source={source}, destination={destination}, "
                    f"element={element}"
                )


def _index_orbits(
    table_size: int,
    permutations: tuple,
) -> tuple:
    for permutation in permutations:
        if len(permutation) != table_size:
            raise ValueError(
                "index permutation length does not match its table"
            )
        if sorted(permutation) != list(range(table_size)):
            raise ValueError("index action is not a permutation")

    unassigned = set(range(table_size))
    result = []
    while unassigned:
        representative = min(unassigned)
        members = tuple(
            sorted(
                {
                    permutation[representative]
                    for permutation in permutations
                }
            )
        )
        if not set(members) <= unassigned:
            raise ValueError("index orbits overlap")
        if not members or representative != members[0]:
            raise ValueError(
                "index orbit representative is not canonical"
            )
        unassigned.difference_update(members)
        result.append(IndexOrbit(representative, members))
    return tuple(result)


def build_constraint_map(
    size: int,
    moment_basis,
    localizer_basis,
) -> ConstraintMap:
    """Build the legacy structural map, never a solver-ready localizer map."""
    size = _validate_constraint_size(size)
    moment_basis = _validate_basis_words(
        "moment basis",
        moment_basis,
        size,
    )
    localizer_basis = _validate_basis_words(
        "localizer basis",
        localizer_basis,
        size,
    )
    group_elements = dihedral_elements(size)
    moment_basis_permutations = _basis_permutations(
        "moment basis",
        moment_basis,
        group_elements,
        size,
    )
    localizer_basis_permutations = _basis_permutations(
        "localizer basis",
        localizer_basis,
        group_elements,
        size,
    )

    moment_entries = _moment_entries(moment_basis)
    zero_localizers = _zero_localizers(size, localizer_basis)
    moment_entry_permutations = tuple(
        _moment_entry_permutation(permutation)
        for permutation in moment_basis_permutations
    )
    zero_localizer_permutations = tuple(
        _zero_localizer_permutation(
            element,
            permutation,
            size,
        )
        for element, permutation in zip(
            group_elements,
            localizer_basis_permutations,
        )
    )
    _validate_equivariance(
        size,
        group_elements,
        moment_entries,
        moment_entry_permutations,
        "moment entry",
    )
    _validate_equivariance(
        size,
        group_elements,
        zero_localizers,
        zero_localizer_permutations,
        "zero localizer",
    )

    moment_entry_orbits = _index_orbits(
        len(moment_entries),
        moment_entry_permutations,
    )
    zero_localizer_orbits = _index_orbits(
        len(zero_localizers),
        zero_localizer_permutations,
    )
    moment_basis_size = len(moment_basis)
    localizer_basis_size = len(localizer_basis)
    assembly_statistics = {
        "moment_basis_size": moment_basis_size,
        "moment_entry_count": moment_basis_size**2,
        "localizer_basis_size": localizer_basis_size,
        "zero_localizer_count": (
            size * localizer_basis_size**2
        ),
        "group_order": 2 * size,
        "dense_complex_matrix_bytes": (
            16 * moment_basis_size**2
            + 16 * size * localizer_basis_size**2
        ),
    }
    constraint_map = ConstraintMap(
        size=size,
        moment_basis=moment_basis,
        localizer_basis=localizer_basis,
        moment_entries=moment_entries,
        zero_localizers=zero_localizers,
        group_elements=group_elements,
        moment_basis_permutations=moment_basis_permutations,
        localizer_basis_permutations=(
            localizer_basis_permutations
        ),
        moment_entry_permutations=moment_entry_permutations,
        zero_localizer_permutations=(
            zero_localizer_permutations
        ),
        irrep_catalog=dihedral_irrep_catalog(size),
        moment_sector_multiplicities=sector_multiplicities(
            moment_basis,
            size,
        ),
        localizer_sector_multiplicities=sector_multiplicities(
            localizer_basis,
            size,
        ),
        moment_entry_orbits=moment_entry_orbits,
        zero_localizer_orbits=zero_localizer_orbits,
        assembly_statistics=assembly_statistics,
    )
    if (
        expand_moment_entry_orbits(constraint_map)
        != moment_entries
    ):
        raise ValueError(
            "moment-entry equivariance orbits failed dense expansion"
        )
    if (
        expand_zero_localizer_orbits(constraint_map)
        != zero_localizers
    ):
        raise ValueError(
            "zero-localizer equivariance orbits failed dense expansion"
        )
    return constraint_map


def _group_index_for_member(
    representative: int,
    member: int,
    permutations: tuple,
) -> int:
    for group_index, permutation in enumerate(permutations):
        if permutation[representative] == member:
            return group_index
    raise ValueError(
        "orbit member is unreachable from its representative"
    )


def _validate_orbit_partition(
    orbits: tuple,
    permutations: tuple,
    table_size: int,
) -> None:
    members_seen = []
    for orbit in orbits:
        if not isinstance(orbit, IndexOrbit):
            raise TypeError("every orbit must be an IndexOrbit")
        expected = tuple(
            sorted(
                {
                    permutation[orbit.representative]
                    for permutation in permutations
                }
            )
        )
        if orbit.members != expected:
            raise ValueError(
                "orbit members do not match the exported group action"
            )
        if not orbit.members:
            raise ValueError("index orbit cannot be empty")
        if orbit.representative != orbit.members[0]:
            raise ValueError(
                "index orbit representative is not canonical"
            )
        members_seen.extend(orbit.members)
    if sorted(members_seen) != list(range(table_size)):
        raise ValueError(
            "index orbits do not partition the complete table"
        )


def expand_moment_entry_orbits(
    constraint_map: ConstraintMap,
) -> tuple:
    if not isinstance(constraint_map, ConstraintMap):
        raise TypeError("constraint_map must be a ConstraintMap")
    table_size = len(constraint_map.moment_entries)
    _validate_orbit_partition(
        constraint_map.moment_entry_orbits,
        constraint_map.moment_entry_permutations,
        table_size,
    )
    basis_size = len(constraint_map.moment_basis)
    expanded = [None] * table_size
    for orbit in constraint_map.moment_entry_orbits:
        representative_entry = constraint_map.moment_entries[
            orbit.representative
        ]
        for member in orbit.members:
            group_index = _group_index_for_member(
                orbit.representative,
                member,
                constraint_map.moment_entry_permutations,
            )
            expanded[member] = MomentEntry(
                row=member // basis_size,
                column=member % basis_size,
                polynomial=act_on_polynomial(
                    constraint_map.group_elements[group_index],
                    representative_entry.polynomial,
                    constraint_map.size,
                ),
            )
    if any(entry is None for entry in expanded):
        raise ValueError("moment-entry orbit expansion is incomplete")
    return tuple(expanded)


def expand_zero_localizer_orbits(
    constraint_map: ConstraintMap,
) -> tuple:
    if not isinstance(constraint_map, ConstraintMap):
        raise TypeError("constraint_map must be a ConstraintMap")
    table_size = len(constraint_map.zero_localizers)
    _validate_orbit_partition(
        constraint_map.zero_localizer_orbits,
        constraint_map.zero_localizer_permutations,
        table_size,
    )
    basis_size = len(constraint_map.localizer_basis)
    block_size = basis_size**2
    expanded = [None] * table_size
    for orbit in constraint_map.zero_localizer_orbits:
        representative_entry = constraint_map.zero_localizers[
            orbit.representative
        ]
        for member in orbit.members:
            group_index = _group_index_for_member(
                orbit.representative,
                member,
                constraint_map.zero_localizer_permutations,
            )
            within_site = member % block_size
            expanded[member] = ZeroLocalizerRow(
                site=member // block_size,
                row=within_site // basis_size,
                column=within_site % basis_size,
                polynomial=act_on_polynomial(
                    constraint_map.group_elements[group_index],
                    representative_entry.polynomial,
                    constraint_map.size,
                ),
            )
    if any(entry is None for entry in expanded):
        raise ValueError(
            "zero-localizer orbit expansion is incomplete"
        )
    return tuple(expanded)
