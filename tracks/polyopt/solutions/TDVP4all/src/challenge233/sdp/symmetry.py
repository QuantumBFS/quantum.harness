from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from challenge233.sdp.algebra import (
    PauliPolynomial,
    PauliWord,
)


@dataclass(frozen=True, order=True)
class DihedralElement:
    """The element T^shift R^reflected of the periodic-chain D_N group."""

    shift: int
    reflected: bool


@dataclass(frozen=True)
class TranslationOrbit:
    representative: PauliWord
    members: tuple


@dataclass(frozen=True)
class DihedralIrrep:
    label: str
    dimension: int
    momenta: tuple
    reflection_parity: Optional[int]


@dataclass(frozen=True)
class SectorMultiplicity:
    irrep: DihedralIrrep
    multiplicity: int


def _validate_size(size: int) -> int:
    size = int(size)
    if size < 3:
        raise ValueError("dihedral size must be at least 3")
    return size


def normalize(
    element: DihedralElement,
    size: int,
) -> DihedralElement:
    size = _validate_size(size)
    if not isinstance(element, DihedralElement):
        raise TypeError("element must be a DihedralElement")
    return DihedralElement(
        element.shift % size,
        bool(element.reflected),
    )


def compose(
    left: DihedralElement,
    right: DihedralElement,
    size: int,
) -> DihedralElement:
    """Return left after right, using T^s R^a T^t R^b."""
    size = _validate_size(size)
    left = normalize(left, size)
    right = normalize(right, size)
    sign = -1 if left.reflected else 1
    return normalize(
        DihedralElement(
            left.shift + sign * right.shift,
            left.reflected ^ right.reflected,
        ),
        size,
    )


def dihedral_elements(size: int) -> tuple:
    size = _validate_size(size)
    return tuple(
        DihedralElement(shift, reflected)
        for reflected in (False, True)
        for shift in range(size)
    )


def act_on_site(
    element: DihedralElement,
    site: int,
    size: int,
) -> int:
    size = _validate_size(size)
    site = int(site)
    if not 0 <= site < size:
        raise ValueError(
            f"site must lie in range(size), got site={site}, size={size}"
        )
    element = normalize(element, size)
    sign = -1 if element.reflected else 1
    return (element.shift + sign * site) % size


def act_on_word(
    element: DihedralElement,
    word: PauliWord,
    size: int,
) -> PauliWord:
    if not isinstance(word, PauliWord):
        raise TypeError("word must be a PauliWord")
    return PauliWord(
        tuple(
            sorted(
                (
                    act_on_site(element, site, size),
                    label,
                )
                for site, label in word.factors
            )
        )
    )


def act_on_polynomial(
    element: DihedralElement,
    polynomial: PauliPolynomial,
    size: int,
) -> PauliPolynomial:
    if not isinstance(polynomial, PauliPolynomial):
        raise TypeError("polynomial must be a PauliPolynomial")
    return PauliPolynomial.from_terms(
        (
            act_on_word(element, word, size),
            coefficient,
        )
        for word, coefficient in polynomial.terms
    )


def word_orbit(word: PauliWord, size: int) -> tuple:
    return tuple(
        sorted(
            {
                act_on_word(element, word, size)
                for element in dihedral_elements(size)
            }
        )
    )


def representation_permutation(
    element: DihedralElement,
    basis,
    size: int,
) -> tuple:
    size = _validate_size(size)
    basis = tuple(basis)
    if len(set(basis)) != len(basis):
        raise ValueError("basis contains duplicate words")
    index = {word: position for position, word in enumerate(basis)}
    permutation = []
    for word in basis:
        image = act_on_word(element, word, size)
        if image not in index:
            raise ValueError(
                "basis is not closed under D_N: "
                f"missing image {image}"
            )
        permutation.append(index[image])
    if sorted(permutation) != list(range(len(basis))):
        raise ValueError("group action did not produce a basis permutation")
    return tuple(permutation)


def translation_orbits(basis, size: int) -> tuple:
    """Partition a translation-closed basis into ordered T-orbits."""
    size = _validate_size(size)
    basis = tuple(basis)
    if len(set(basis)) != len(basis):
        raise ValueError("basis contains duplicate words")
    for word in basis:
        if not isinstance(word, PauliWord):
            raise TypeError("every basis element must be a PauliWord")
        for site, _ in word.factors:
            if not 0 <= site < size:
                raise ValueError(
                    "word factor site must lie in range(size): "
                    f"site={site}, size={size}"
                )

    translation = DihedralElement(1, False)
    representation_permutation(translation, basis, size)

    unassigned = set(basis)
    result = []
    while unassigned:
        representative = min(unassigned)
        members = []
        seen = set()
        current = representative
        for _ in range(size):
            if current in seen:
                break
            seen.add(current)
            members.append(current)
            current = act_on_word(translation, current, size)
        if current != representative:
            raise ValueError(
                "translation action did not close an orbit within size steps"
            )
        member_set = set(members)
        if not member_set <= unassigned:
            raise ValueError(
                "translation orbits overlap before partition completion"
            )
        if representative != min(member_set):
            raise ValueError(
                "translation orbit representative is not canonical"
            )
        unassigned.difference_update(member_set)
        result.append(
            TranslationOrbit(
                representative=representative,
                members=tuple(members),
            )
        )
    return tuple(result)


def dihedral_irrep_catalog(size: int) -> tuple:
    """Return every real D_N irrep label, including absent sectors."""
    size = _validate_size(size)
    result = [
        DihedralIrrep(
            label="k=0,r=+1",
            dimension=1,
            momenta=(0,),
            reflection_parity=1,
        ),
        DihedralIrrep(
            label="k=0,r=-1",
            dimension=1,
            momenta=(0,),
            reflection_parity=-1,
        ),
    ]
    if size % 2 == 0:
        result.extend(
            (
                DihedralIrrep(
                    label="k=pi,r=+1",
                    dimension=1,
                    momenta=(size // 2,),
                    reflection_parity=1,
                ),
                DihedralIrrep(
                    label="k=pi,r=-1",
                    dimension=1,
                    momenta=(size // 2,),
                    reflection_parity=-1,
                ),
            )
        )

    generic_stop = (size + 1) // 2
    result.extend(
        DihedralIrrep(
            label=f"k={momentum}<->{size - momentum}",
            dimension=2,
            momenta=(momentum, size - momentum),
            reflection_parity=None,
        )
        for momentum in range(1, generic_stop)
    )
    catalog = tuple(result)
    if sum(irrep.dimension**2 for irrep in catalog) != 2 * size:
        raise ValueError("D_N irrep catalog failed the group-dimension sum")
    return catalog


def sector_multiplicities(basis, size: int) -> tuple:
    """Decompose a D_N-closed word permutation representation exactly."""
    size = _validate_size(size)
    basis = tuple(basis)
    orbits = translation_orbits(basis, size)
    for element in dihedral_elements(size):
        representation_permutation(element, basis, size)

    word_location = {}
    for orbit_index, orbit in enumerate(orbits):
        for shift, word in enumerate(orbit.members):
            word_location[word] = (orbit_index, shift)

    catalog = dihedral_irrep_catalog(size)
    multiplicities = {
        irrep.label: 0
        for irrep in catalog
    }

    for irrep in catalog:
        if irrep.dimension == 2:
            momentum = irrep.momenta[0]
            multiplicities[irrep.label] = sum(
                (momentum * len(orbit.members)) % size == 0
                for orbit in orbits
            )

    reflection = DihedralElement(0, True)
    self_inverse_momenta = [0]
    if size % 2 == 0:
        self_inverse_momenta.append(size // 2)

    for momentum in self_inverse_momenta:
        supporting = {
            index
            for index, orbit in enumerate(orbits)
            if (momentum * len(orbit.members)) % size == 0
        }
        remaining = set(supporting)
        parity_counts = {1: 0, -1: 0}
        while remaining:
            orbit_index = min(remaining)
            orbit = orbits[orbit_index]
            image = act_on_word(
                reflection,
                orbit.representative,
                size,
            )
            image_orbit, shift = word_location[image]
            if image_orbit not in supporting:
                raise ValueError(
                    "reflection did not preserve a self-inverse "
                    "momentum space"
                )
            if image_orbit == orbit_index:
                phase_index = (momentum * shift) % size
                parity = 1 if phase_index == 0 else -1
                parity_counts[parity] += 1
                remaining.remove(orbit_index)
            else:
                if image_orbit not in remaining:
                    raise ValueError(
                        "reflection did not pair translation orbits "
                        "involutively"
                    )
                parity_counts[1] += 1
                parity_counts[-1] += 1
                remaining.remove(orbit_index)
                remaining.remove(image_orbit)

        momentum_label = "0" if momentum == 0 else "pi"
        for parity in (1, -1):
            parity_label = "+1" if parity == 1 else "-1"
            multiplicities[
                f"k={momentum_label},r={parity_label}"
            ] = parity_counts[parity]

    inventory = tuple(
        SectorMultiplicity(
            irrep=irrep,
            multiplicity=multiplicities[irrep.label],
        )
        for irrep in catalog
    )
    represented_dimension = sum(
        item.irrep.dimension * item.multiplicity
        for item in inventory
    )
    if represented_dimension != len(basis):
        raise ValueError(
            "D_N sector multiplicities do not reconstruct the "
            "representation dimension: "
            f"{represented_dimension} != {len(basis)}"
        )
    return inventory
