from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Iterable, Sequence

from .algebra import (
    PauliString,
    PauliSum,
    commutator,
    pauli_strings_commute,
)


Coordinate = tuple[int, int]
CoordinateBond = tuple[Coordinate, Coordinate]


@dataclass
class CoordinateRegistry:
    coordinate_to_site: dict[Coordinate, int] = field(default_factory=dict)
    site_to_coordinate: list[Coordinate] = field(default_factory=list)

    def site(self, coordinate: Coordinate) -> int:
        if coordinate not in self.coordinate_to_site:
            self.coordinate_to_site[coordinate] = len(self.site_to_coordinate)
            self.site_to_coordinate.append(coordinate)
        return self.coordinate_to_site[coordinate]

    def coordinate(self, site: int) -> Coordinate:
        return self.site_to_coordinate[site]


def matching_partner(coordinate: Coordinate, color: int) -> Coordinate:
    x, y = coordinate
    if color == 0:
        return (x + 1, y) if x % 2 == 0 else (x - 1, y)
    if color == 1:
        return (x + 1, y) if x % 2 == 1 else (x - 1, y)
    if color == 2:
        return (x, y + 1) if y % 2 == 0 else (x, y - 1)
    if color == 3:
        return (x, y + 1) if y % 2 == 1 else (x, y - 1)
    raise ValueError("matching color must be 0, 1, 2 or 3")


def canonical_coordinate_bond(u: Coordinate, v: Coordinate) -> CoordinateBond:
    return (u, v) if u < v else (v, u)


def representative_bonds(color: int) -> tuple[CoordinateBond, CoordinateBond]:
    if color in (0, 1):
        start_x = color
        return (
            canonical_coordinate_bond((start_x, 0), (start_x + 1, 0)),
            canonical_coordinate_bond((start_x, 1), (start_x + 1, 1)),
        )
    start_y = color - 2
    return (
        canonical_coordinate_bond((0, start_y), (0, start_y + 1)),
        canonical_coordinate_bond((1, start_y), (1, start_y + 1)),
    )


def coordinate_heisenberg_bond(
    registry: CoordinateRegistry,
    bond: CoordinateBond,
) -> PauliSum:
    u, v = (registry.site(coordinate) for coordinate in bond)
    result = PauliSum.zero()
    for op in ("X", "Y", "Z"):
        result += PauliSum.term(
            PauliString({u: op, v: op}),
            Fraction(1, 4),
        )
    return result


def local_fragment_adjoint(
    registry: CoordinateRegistry,
    color: int,
    operator: PauliSum,
) -> PauliSum:
    candidate_bonds: set[CoordinateBond] = set()
    for pauli in operator.terms:
        for site in pauli.support:
            coordinate = registry.coordinate(site)
            candidate_bonds.add(
                canonical_coordinate_bond(
                    coordinate,
                    matching_partner(coordinate, color),
                )
            )
    result = PauliSum.zero()
    for bond in sorted(candidate_bonds):
        result += commutator(coordinate_heisenberg_bond(registry, bond), operator)
    return result


def local_nested_commutator_density(
    key: tuple[int, ...],
    cache: dict[tuple[int, ...], tuple[CoordinateRegistry, PauliSum]] | None = None,
) -> tuple[CoordinateRegistry, PauliSum]:
    """Return one 2x2-cell density for ``(outermost,...,base)``."""

    # A fresh registry per complete key keeps cached Pauli site labels valid.
    registry = CoordinateRegistry()
    base = key[-1]
    operator = PauliSum.zero()
    for bond in representative_bonds(base):
        operator += coordinate_heisenberg_bond(registry, bond)
    for color in reversed(key[:-1]):
        operator = local_fragment_adjoint(registry, color, operator)
    return registry, operator


def local_nested_pauli_l1_density(key: tuple[int, ...]) -> Fraction:
    _, operator = local_nested_commutator_density(key)
    return operator.exact_axis_l1()


class LocalDensityEvaluator:
    """Suffix-memoized evaluator for connected matching commutators."""

    def __init__(self) -> None:
        self.registries = {color: CoordinateRegistry() for color in range(4)}
        self.cache: dict[tuple[int, ...], PauliSum] = {}

    def evaluate(self, key: tuple[int, ...]) -> PauliSum:
        if key in self.cache:
            return self.cache[key]
        base = key[-1]
        registry = self.registries[base]
        if len(key) == 1:
            operator = PauliSum.zero()
            for bond in representative_bonds(base):
                operator += coordinate_heisenberg_bond(registry, bond)
        else:
            operator = local_fragment_adjoint(
                registry,
                key[0],
                self.evaluate(key[1:]),
            )
        self.cache[key] = operator
        return operator

    def pauli_l1_density(self, key: tuple[int, ...]) -> Fraction:
        return self.evaluate(key).exact_axis_l1()


GaussianInteger = tuple[int, int]
DyadicTerms = dict[PauliString, GaussianInteger]


def _multiply_gaussian_by_phase(
    coefficient: GaussianInteger,
    phase_real: int,
    phase_imag: int,
) -> GaussianInteger:
    real, imag = coefficient
    return (
        real * phase_real - imag * phase_imag,
        real * phase_imag + imag * phase_real,
    )


def _accumulate_gaussian(
    terms: DyadicTerms,
    pauli: PauliString,
    coefficient: GaussianInteger,
) -> None:
    previous = terms.get(pauli)
    if previous is None:
        if coefficient != (0, 0):
            terms[pauli] = coefficient
        return
    updated = (previous[0] + coefficient[0], previous[1] + coefficient[1])
    if updated == (0, 0):
        del terms[pauli]
    else:
        terms[pauli] = updated


def dyadic_local_fragment_adjoint(
    registry: CoordinateRegistry,
    color: int,
    operator: DyadicTerms,
) -> DyadicTerms:
    """Apply ``ad_H_color`` to a Gaussian-integer numerator map.

    A Heisenberg bond coefficient is ``1/4`` and a nonzero Pauli
    commutator contributes a factor two. Thus every adjoint increases the
    shared binary denominator exponent by exactly one.
    """

    candidate_bonds: set[CoordinateBond] = set()
    for pauli in operator:
        for site in pauli.support:
            coordinate = registry.coordinate(site)
            candidate_bonds.add(
                canonical_coordinate_bond(
                    coordinate,
                    matching_partner(coordinate, color),
                )
            )

    result: DyadicTerms = {}
    for bond in sorted(candidate_bonds):
        u, v = (registry.site(coordinate) for coordinate in bond)
        for op in ("X", "Y", "Z"):
            bond_pauli = PauliString({u: op, v: op})
            for pauli, coefficient in operator.items():
                if pauli_strings_commute(bond_pauli, pauli):
                    continue
                phase, product_pauli = bond_pauli.multiply(pauli)
                _accumulate_gaussian(
                    result,
                    product_pauli,
                    _multiply_gaussian_by_phase(
                        coefficient,
                        int(phase.real),
                        int(phase.imag),
                    ),
                )
    return result


class DyadicLocalDensityEvaluator:
    """Fast exact evaluator with a shared power-of-two denominator.

    A key of length ``d`` has common coefficient scale ``2**(-(d+1))``.
    """

    def __init__(self) -> None:
        self.registries = {color: CoordinateRegistry() for color in range(4)}
        self.cache: dict[tuple[int, ...], DyadicTerms] = {}

    @staticmethod
    def denominator_exponent(key: tuple[int, ...]) -> int:
        return len(key) + 1

    def evaluate(self, key: tuple[int, ...]) -> DyadicTerms:
        if not key:
            raise ValueError("nested-commutator key must be nonempty")
        if key in self.cache:
            return self.cache[key]
        base = key[-1]
        registry = self.registries[base]
        if len(key) == 1:
            operator: DyadicTerms = {}
            for bond in representative_bonds(base):
                u, v = (registry.site(coordinate) for coordinate in bond)
                for op in ("X", "Y", "Z"):
                    _accumulate_gaussian(
                        operator,
                        PauliString({u: op, v: op}),
                        (1, 0),
                    )
        else:
            operator = dyadic_local_fragment_adjoint(
                registry,
                key[0],
                self.evaluate(key[1:]),
            )
        self.cache[key] = operator
        return operator

    def pauli_l1_density(self, key: tuple[int, ...]) -> Fraction:
        numerator = sum(
            abs(real) + abs(imag)
            for real, imag in self.evaluate(key).values()
        )
        return Fraction(numerator, 1 << self.denominator_exponent(key))


SymplecticPauli = tuple[int, int]
SymplecticTerms = dict[SymplecticPauli, int]


def _iter_set_bits(mask: int) -> Iterable[int]:
    while mask:
        least = mask & -mask
        yield least.bit_length() - 1
        mask ^= least


def _symplectic_product_phase(
    left: SymplecticPauli,
    right: SymplecticPauli,
) -> tuple[int, SymplecticPauli]:
    """Return the exponent ``e`` in ``P(left)P(right)=i**e P(product)``."""

    left_x, left_z = left
    right_x, right_z = right
    result = (left_x ^ right_x, left_z ^ right_z)
    exponent = (
        (left_x & left_z).bit_count()
        + (right_x & right_z).bit_count()
        + 2 * (left_z & right_x).bit_count()
        - (result[0] & result[1]).bit_count()
    ) % 4
    return exponent, result


def _symplectic_anticommutes(
    left: SymplecticPauli,
    right: SymplecticPauli,
) -> bool:
    return (
        ((left[0] & right[1]).bit_count() + (left[1] & right[0]).bit_count())
        & 1
    ) == 1


def _symplectic_bond_terms(first: int, second: int) -> tuple[SymplecticPauli, ...]:
    sites = (1 << first) | (1 << second)
    return ((sites, 0), (sites, sites), (0, sites))


def symplectic_local_fragment_adjoint(
    registry: CoordinateRegistry,
    color: int,
    operator: SymplecticTerms,
) -> SymplecticTerms:
    candidate_bonds: set[CoordinateBond] = set()
    for x_mask, z_mask in operator:
        for site in _iter_set_bits(x_mask | z_mask):
            coordinate = registry.coordinate(site)
            candidate_bonds.add(
                canonical_coordinate_bond(
                    coordinate,
                    matching_partner(coordinate, color),
                )
            )

    result: SymplecticTerms = {}
    for bond in sorted(candidate_bonds):
        first, second = (registry.site(coordinate) for coordinate in bond)
        for bond_pauli in _symplectic_bond_terms(first, second):
            for pauli, coefficient in operator.items():
                if not _symplectic_anticommutes(bond_pauli, pauli):
                    continue
                phase, product_pauli = _symplectic_product_phase(bond_pauli, pauli)
                # Anticommuting Hermitian Paulis have product phase +/- i.
                sign = 1 if phase == 1 else -1
                updated = result.get(product_pauli, 0) + sign * coefficient
                if updated:
                    result[product_pauli] = updated
                else:
                    result.pop(product_pauli, None)
    return result


class SymplecticDyadicLocalDensityEvaluator:
    """Fastest exact evaluator: bit-packed Paulis and integer coefficients.

    The common phase ``i**(len(key)-1)`` and denominator
    ``2**(len(key)+1)`` are factored out of every coefficient.
    """

    def __init__(self, *, shared_coordinates: bool = False) -> None:
        if shared_coordinates:
            registry = CoordinateRegistry()
            self.registries = {color: registry for color in range(4)}
        else:
            self.registries = {color: CoordinateRegistry() for color in range(4)}
        self.cache: dict[tuple[int, ...], SymplecticTerms] = {}

    @staticmethod
    def denominator_exponent(key: tuple[int, ...]) -> int:
        return len(key) + 1

    def evaluate(self, key: tuple[int, ...]) -> SymplecticTerms:
        if not key:
            raise ValueError("nested-commutator key must be nonempty")
        if key in self.cache:
            return self.cache[key]
        base = key[-1]
        registry = self.registries[base]
        if len(key) == 1:
            operator: SymplecticTerms = {}
            for bond in representative_bonds(base):
                first, second = (registry.site(coordinate) for coordinate in bond)
                for pauli in _symplectic_bond_terms(first, second):
                    operator[pauli] = operator.get(pauli, 0) + 1
        else:
            operator = symplectic_local_fragment_adjoint(
                registry,
                key[0],
                self.evaluate(key[1:]),
            )
        self.cache[key] = operator
        return operator

    def pauli_l1_density(self, key: tuple[int, ...]) -> Fraction:
        numerator = sum(abs(value) for value in self.evaluate(key).values())
        return Fraction(numerator, 1 << self.denominator_exponent(key))
