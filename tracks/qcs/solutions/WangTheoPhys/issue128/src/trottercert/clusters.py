from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import isqrt
from math import lcm

import numpy as np

from .algebra import PauliString, PauliSum, QComplex, pauli_strings_commute
from .orbits import TranslationOrbit, embed_grid_op
from .lattice import SquareLattice
from .orbits import translation_orbits


@dataclass(frozen=True)
class ClusterPlacement:
    orbit_index: int
    offsets: tuple[tuple[int, int], ...]
    weights: tuple[Fraction, ...]

    def validate(self) -> None:
        if not self.offsets or len(self.offsets) != len(self.weights):
            raise ValueError("placement offsets and weights must be nonempty and aligned")
        if any(weight < 0 for weight in self.weights):
            raise ValueError("cluster weights must be nonnegative")
        if sum(self.weights, Fraction()) != 1:
            raise ValueError("weights for each translation orbit must sum to one")


@dataclass(frozen=True)
class ClusterCertificate:
    width: int
    height: int
    placements: tuple[ClusterPlacement, ...]
    operator: PauliSum
    row_sum_bound: Fraction


@dataclass(frozen=True)
class PartitionedOperatorCertificate:
    unit_cell: tuple[int, int]
    n_cells: int
    horizontal: ClusterCertificate
    vertical: ClusterCertificate
    global_bound: Fraction


@dataclass(frozen=True)
class FullPatchOperatorCertificate:
    unit_cell: tuple[int, int]
    n_cells: int
    cluster_operator: PauliSum
    placements: tuple[ClusterPlacement, ...]
    density_bound: Fraction
    global_bound: Fraction


@dataclass(frozen=True)
class CollatzCertificate:
    denominator: int
    vector: tuple[int, ...]
    max_numerator: int
    max_denominator_component: int
    bound: Fraction


@dataclass(frozen=True)
class AnticommutingCertificate:
    groups: tuple[tuple[PauliString, ...], ...]
    bound: Fraction


@dataclass(frozen=True)
class PhasePartitionedCertificate:
    unit_cell: tuple[int, int]
    n_cells: int
    phase_bounds: tuple[tuple[tuple[int, int], CollatzCertificate], ...]
    global_bound: Fraction


def uniform_cluster_operator(
    orbits: tuple[TranslationOrbit, ...],
    width: int,
    height: int,
) -> tuple[PauliSum, tuple[ClusterPlacement, ...]]:
    cluster = PauliSum.zero()
    placements: list[ClusterPlacement] = []
    for orbit_index, orbit in enumerate(orbits):
        if orbit.width > width or orbit.height > height:
            raise ValueError(
                f"orbit {orbit_index} with {orbit.width}x{orbit.height} support "
                f"does not fit {width}x{height} patch"
            )
        step_x, step_y = orbit.unit_cell
        offsets = tuple(
            (dx, dy)
            for dy in range(0, height - orbit.height + 1, step_y)
            for dx in range(0, width - orbit.width + 1, step_x)
        )
        if not offsets:
            raise ValueError(f"orbit {orbit_index} has no unit-cell-aligned placement")
        weight = Fraction(1, len(offsets))
        weights = tuple(weight for _ in offsets)
        placement = ClusterPlacement(orbit_index, offsets, weights)
        placement.validate()
        placements.append(placement)
        for (dx, dy), local_weight in zip(offsets, weights):
            cluster += PauliSum.term(
                embed_grid_op(orbit.representative, width, dx, dy),
                orbit.coefficient * local_weight,
            )
    return cluster, tuple(placements)


def _sqrt_fraction_upper(value: Fraction, decimal_places: int = 30) -> Fraction:
    if value < 0:
        raise ValueError("cannot bound square root of negative value")
    if value == 0:
        return Fraction()
    scale = 10**decimal_places
    quotient = (value.numerator * scale * scale) // value.denominator
    root = isqrt(quotient)
    if Fraction(root * root, scale * scale) < value:
        root += 1
    return Fraction(root, scale)


def paulis_anticommute(left: PauliString, right: PauliString) -> bool:
    return not pauli_strings_commute(left, right)


def greedy_anticommuting_certificate(operator: PauliSum) -> AnticommutingCertificate:
    if any(coefficient.imag for coefficient in operator.terms.values()):
        raise ValueError("anticommuting certificate currently requires real coefficients")
    ordered = sorted(
        operator.terms,
        key=lambda pauli: (
            -abs(operator.terms[pauli].real),
            pauli,
        ),
    )
    masks: dict[PauliString, tuple[int, int]] = {}
    for pauli in ordered:
        x_mask = z_mask = 0
        for site, op in pauli.ops:
            bit = 1 << site
            if op in {"X", "Y"}:
                x_mask |= bit
            if op in {"Z", "Y"}:
                z_mask |= bit
        masks[pauli] = (x_mask, z_mask)

    def fast_anticommutes(left: PauliString, right: PauliString) -> bool:
        left_x, left_z = masks[left]
        right_x, right_z = masks[right]
        return bool(
            ((left_x & right_z).bit_count() + (left_z & right_x).bit_count())
            & 1
        )

    groups: list[list[PauliString]] = []
    for pauli in ordered:
        compatible = [
            index
            for index, group in enumerate(groups)
            if all(fast_anticommutes(pauli, member) for member in group)
        ]
        if compatible:
            # Prefer the largest compatible group to reduce the number of
            # triangle inequalities deterministically.
            selected = max(compatible, key=lambda index: (len(groups[index]), -index))
            groups[selected].append(pauli)
        else:
            groups.append([pauli])
    bound = Fraction()
    for group in groups:
        squared = sum(
            (operator.terms[pauli].real ** 2 for pauli in group),
            Fraction(),
        )
        bound += _sqrt_fraction_upper(squared)
    return AnticommutingCertificate(
        groups=tuple(tuple(group) for group in groups),
        bound=bound,
    )


def computational_row_sum_bound(operator: PauliSum, n_qubits: int) -> Fraction:
    """Rigorous max absolute row-sum bound using exact merged amplitudes."""

    if n_qubits > 16:
        raise ValueError("row enumeration is restricted to at most 16 qubits")
    best = Fraction()
    parsed = []
    for pauli, coefficient in operator.terms.items():
        flip_mask = 0
        z_sites: list[int] = []
        y_sites: list[int] = []
        for site, op in pauli.ops:
            if op in {"X", "Y"}:
                flip_mask |= 1 << (n_qubits - 1 - site)
            if op == "Z":
                z_sites.append(site)
            elif op == "Y":
                y_sites.append(site)
        parsed.append((flip_mask, tuple(z_sites), tuple(y_sites), coefficient))

    for basis in range(1 << n_qubits):
        amplitudes: dict[int, QComplex] = {}
        for flip_mask, z_sites, y_sites, coefficient in parsed:
            phase = QComplex(1)
            for site in z_sites:
                bit = (basis >> (n_qubits - 1 - site)) & 1
                if bit:
                    phase = -phase
            for site in y_sites:
                bit = (basis >> (n_qubits - 1 - site)) & 1
                phase *= QComplex(0, -1 if bit else 1)
            target = basis ^ flip_mask
            amplitudes[target] = amplitudes.get(target, QComplex()) + coefficient * phase
        row = Fraction()
        for amplitude in amplitudes.values():
            squared = amplitude.real**2 + amplitude.imag**2
            row += _sqrt_fraction_upper(squared)
        best = max(best, row)
    return best


def computational_row_taxicab_bound(operator: PauliSum, n_qubits: int) -> Fraction:
    """Fast exact row bound using ``|z| <= |Re z| + |Im z|``.

    Coefficients are lifted to a common integer denominator. Amplitudes with
    the same computational-basis transition are merged exactly using int64
    arrays, retaining cancellations before the taxicab inequality.
    """

    if n_qubits > 20:
        raise ValueError("taxicab row enumeration is restricted to at most 20 qubits")
    denominator = 1
    for coefficient in operator.terms.values():
        denominator = lcm(
            denominator,
            coefficient.real.denominator,
            coefficient.imag.denominator,
        )
    grouped: dict[int, list[tuple[int, int, int, int]]] = {}
    max_scaled = 0
    for pauli, coefficient in operator.terms.items():
        flip_mask = 0
        phase_mask = 0
        n_y = 0
        for site, op in pauli.ops:
            bit_mask = 1 << (n_qubits - 1 - site)
            if op in {"X", "Y"}:
                flip_mask |= bit_mask
            if op in {"Z", "Y"}:
                phase_mask |= bit_mask
            if op == "Y":
                n_y += 1
        real = coefficient.real.numerator * (
            denominator // coefficient.real.denominator
        )
        imag = coefficient.imag.numerator * (
            denominator // coefficient.imag.denominator
        )
        phase = n_y % 4
        if phase == 1:
            real, imag = -imag, real
        elif phase == 2:
            real, imag = -real, -imag
        elif phase == 3:
            real, imag = imag, -real
        max_scaled += abs(real) + abs(imag)
        grouped.setdefault(flip_mask, []).append((phase_mask, real, imag, n_y))
    if max_scaled >= np.iinfo(np.int64).max // max(1, len(operator.terms)):
        raise OverflowError("scaled exact amplitudes exceed int64 safety margin")

    size = 1 << n_qubits
    indices = np.arange(size, dtype=np.uint64)
    parity = np.fromiter(
        ((index.bit_count() & 1) for index in range(size)),
        dtype=np.int8,
        count=size,
    )
    row_sums = np.zeros(size, dtype=np.int64)
    for terms in grouped.values():
        real_amplitude = np.zeros(size, dtype=np.int64)
        imag_amplitude = np.zeros(size, dtype=np.int64)
        for phase_mask, real, imag, _ in terms:
            signs = 1 - 2 * parity[np.bitwise_and(indices, phase_mask)]
            real_amplitude += real * signs
            imag_amplitude += imag * signs
        row_sums += np.abs(real_amplitude) + np.abs(imag_amplitude)
    return Fraction(int(row_sums.max()), denominator)


def _taxicab_transition_groups(
    operator: PauliSum,
    n_qubits: int,
) -> tuple[int, tuple[tuple[int, np.ndarray], ...]]:
    denominator = 1
    for coefficient in operator.terms.values():
        denominator = lcm(
            denominator,
            coefficient.real.denominator,
            coefficient.imag.denominator,
        )
    grouped: dict[int, list[tuple[int, int, int]]] = {}
    for pauli, coefficient in operator.terms.items():
        flip_mask = 0
        phase_mask = 0
        n_y = 0
        for site, op in pauli.ops:
            bit_mask = 1 << (n_qubits - 1 - site)
            if op in {"X", "Y"}:
                flip_mask |= bit_mask
            if op in {"Z", "Y"}:
                phase_mask |= bit_mask
            if op == "Y":
                n_y += 1
        real = coefficient.real.numerator * (
            denominator // coefficient.real.denominator
        )
        imag = coefficient.imag.numerator * (
            denominator // coefficient.imag.denominator
        )
        phase = n_y % 4
        if phase == 1:
            real, imag = -imag, real
        elif phase == 2:
            real, imag = -real, -imag
        elif phase == 3:
            real, imag = imag, -real
        grouped.setdefault(flip_mask, []).append((phase_mask, real, imag))

    size = 1 << n_qubits
    indices = np.arange(size, dtype=np.uint64)
    parity = np.fromiter(
        ((index.bit_count() & 1) for index in range(size)),
        dtype=np.int8,
        count=size,
    )
    transitions: list[tuple[int, np.ndarray]] = []
    for flip_mask, terms in grouped.items():
        real_amplitude = np.zeros(size, dtype=np.int64)
        imag_amplitude = np.zeros(size, dtype=np.int64)
        for phase_mask, real, imag in terms:
            signs = 1 - 2 * parity[np.bitwise_and(indices, phase_mask)]
            real_amplitude += real * signs
            imag_amplitude += imag * signs
        values = np.abs(real_amplitude) + np.abs(imag_amplitude)
        transitions.append((flip_mask, values))
    return denominator, tuple(transitions)


def collatz_taxicab_certificate(
    operator: PauliSum,
    n_qubits: int,
    *,
    iterations: int = 40,
    quantization: int = 10**9,
) -> CollatzCertificate:
    """Certify the taxicab comparison-matrix norm by Collatz--Wielandt."""

    denominator, transitions = _taxicab_transition_groups(operator, n_qubits)
    size = 1 << n_qubits
    indices = np.arange(size, dtype=np.uint64)
    vector = np.ones(size, dtype=np.float64)
    for _ in range(iterations):
        updated = np.zeros(size, dtype=np.float64)
        for flip_mask, values in transitions:
            updated += values * vector[np.bitwise_xor(indices, flip_mask)]
        maximum = float(updated.max())
        if maximum == 0:
            return CollatzCertificate(
                denominator, tuple([1] * size), 0, 1, Fraction()
            )
        vector = updated / maximum
        vector += np.finfo(np.float64).eps
    integer_vector = np.maximum(1, np.rint(vector * quantization)).astype(np.int64)

    applied = np.zeros(size, dtype=np.int64)
    for flip_mask, values in transitions:
        contribution = values * integer_vector[np.bitwise_xor(indices, flip_mask)]
        if np.any(contribution < 0):
            raise OverflowError("integer overflow in Collatz verification")
        applied += contribution
        if np.any(applied < 0):
            raise OverflowError("integer overflow in Collatz verification")

    best_index = max(
        range(size),
        key=lambda index: Fraction(int(applied[index]), int(integer_vector[index])),
    )
    numerator = int(applied[best_index])
    vector_component = int(integer_vector[best_index])
    bound = Fraction(numerator, denominator * vector_component)
    return CollatzCertificate(
        denominator=denominator,
        vector=tuple(int(value) for value in integer_vector),
        max_numerator=numerator,
        max_denominator_component=vector_component,
        bound=bound,
    )


def phase_partitioned_collatz_certificate(
    operator: PauliSum,
    lattice: SquareLattice,
    unit_cell: tuple[int, int] = (2, 2),
    *,
    iterations: int = 35,
) -> PhasePartitionedCertificate:
    """Use separate patch origins for distinct colored unit-cell phases."""

    orbits = translation_orbits(operator, lattice, unit_cell=unit_cell)
    grouped: dict[tuple[int, int], list[TranslationOrbit]] = {}
    for orbit in orbits:
        min_x = min(x for x, _, _ in orbit.representative)
        min_y = min(y for _, y, _ in orbit.representative)
        phase = (min_x % unit_cell[0], min_y % unit_cell[1])
        normalized = tuple(
            (x - phase[0], y - phase[1], op)
            for x, y, op in orbit.representative
        )
        grouped.setdefault(phase, []).append(
            TranslationOrbit(
                normalized,
                orbit.coefficient,
                orbit.members,
                orbit.unit_cell,
                orbit.global_coefficient,
                orbit.stabilizer,
            )
        )
    phase_bounds: list[tuple[tuple[int, int], CollatzCertificate]] = []
    density_sum = Fraction()
    for phase in sorted(grouped):
        cluster, _ = uniform_cluster_operator(tuple(grouped[phase]), 4, 4)
        certificate = collatz_taxicab_certificate(
            cluster, 16, iterations=iterations
        )
        phase_bounds.append((phase, certificate))
        density_sum += certificate.bound
    step_x, step_y = unit_cell
    n_cells = (lattice.length // step_x) * (lattice.length // step_y)
    return PhasePartitionedCertificate(
        unit_cell,
        n_cells,
        tuple(phase_bounds),
        n_cells * density_sum,
    )


def build_uniform_cluster_certificate(
    orbits: tuple[TranslationOrbit, ...],
    width: int,
    height: int,
) -> ClusterCertificate:
    operator, placements = uniform_cluster_operator(orbits, width, height)
    bound = computational_row_sum_bound(operator, width * height)
    return ClusterCertificate(width, height, placements, operator, bound)


def build_partitioned_operator_certificate(
    operator: PauliSum,
    lattice: SquareLattice,
    unit_cell: tuple[int, int] = (2, 2),
) -> PartitionedOperatorCertificate:
    """Certify a colored translation-invariant range-three operator.

    Horizontal/diagonal-support representatives with ``width >= height`` use
    a 4x3 patch; the others use a 3x4 patch. Splitting costs one triangle
    inequality but keeps each exact row enumeration at 12 qubits.
    """

    orbits = translation_orbits(operator, lattice, unit_cell=unit_cell)
    horizontal_orbits = tuple(
        orbit for orbit in orbits if orbit.width >= orbit.height
    )
    vertical_orbits = tuple(
        orbit for orbit in orbits if orbit.width < orbit.height
    )
    horizontal = build_uniform_cluster_certificate(horizontal_orbits, 4, 3)
    vertical = build_uniform_cluster_certificate(vertical_orbits, 3, 4)
    step_x, step_y = unit_cell
    n_cells = (lattice.length // step_x) * (lattice.length // step_y)
    global_bound = n_cells * (
        horizontal.row_sum_bound + vertical.row_sum_bound
    )
    return PartitionedOperatorCertificate(
        unit_cell,
        n_cells,
        horizontal,
        vertical,
        global_bound,
    )


def build_full_patch_operator_certificate(
    operator: PauliSum,
    lattice: SquareLattice,
    unit_cell: tuple[int, int] = (2, 2),
    patch: tuple[int, int] = (4, 4),
) -> FullPatchOperatorCertificate:
    orbits = translation_orbits(operator, lattice, unit_cell=unit_cell)
    width, height = patch
    cluster, placements = uniform_cluster_operator(orbits, width, height)
    density_bound = computational_row_taxicab_bound(cluster, width * height)
    step_x, step_y = unit_cell
    n_cells = (lattice.length // step_x) * (lattice.length // step_y)
    return FullPatchOperatorCertificate(
        unit_cell,
        n_cells,
        cluster,
        placements,
        density_bound,
        n_cells * density_bound,
    )
