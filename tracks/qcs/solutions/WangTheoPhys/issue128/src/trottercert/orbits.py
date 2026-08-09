from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .algebra import PauliString, PauliSum, QComplex
from .lattice import SquareLattice


GridOp = tuple[tuple[int, int, str], ...]


@dataclass(frozen=True)
class TranslationOrbit:
    representative: GridOp
    # Coefficient used in one unit-cell density. Translating and summing this
    # density reconstructs the global orbit, including finite-size stabilizers.
    coefficient: QComplex
    members: tuple[PauliString, ...]
    unit_cell: tuple[int, int] = (1, 1)
    global_coefficient: QComplex = QComplex()
    stabilizer: int = 1

    @property
    def width(self) -> int:
        return 1 + max(x for x, _, _ in self.representative)

    @property
    def height(self) -> int:
        return 1 + max(y for _, y, _ in self.representative)


def translate_pauli_torus(
    pauli: PauliString,
    lattice: SquareLattice,
    dx: int,
    dy: int,
) -> PauliString:
    translated: dict[int, str] = {}
    for site, op in pauli.ops:
        x, y = lattice.coordinates(site)
        translated[lattice.site(x + dx, y + dy)] = op
    return PauliString(translated)


def _grid_form(
    pauli: PauliString,
    lattice: SquareLattice,
    unit_cell: tuple[int, int],
) -> GridOp:
    coordinates = [
        (*lattice.coordinates(site), op)
        for site, op in pauli.ops
    ]
    min_x = min(x for x, _, _ in coordinates)
    min_y = min(y for _, y, _ in coordinates)
    step_x, step_y = unit_cell
    shift_x = (min_x // step_x) * step_x
    shift_y = (min_y // step_y) * step_y
    return tuple(
        sorted((x - shift_x, y - shift_y, op) for x, y, op in coordinates)
    )


def canonical_translation(
    pauli: PauliString,
    lattice: SquareLattice,
    unit_cell: tuple[int, int] = (1, 1),
) -> tuple[GridOp, tuple[PauliString, ...]]:
    if not pauli.ops:
        return (), (pauli,)
    step_x, step_y = unit_cell
    if lattice.length % step_x or lattice.length % step_y:
        raise ValueError("unit cell must divide lattice length")
    translations = {
        translate_pauli_torus(pauli, lattice, dx, dy)
        for dx in range(0, lattice.length, step_x)
        for dy in range(0, lattice.length, step_y)
    }
    candidates: list[tuple[tuple[int, int, int, GridOp], GridOp]] = []
    for translated in translations:
        grid = _grid_form(translated, lattice, unit_cell)
        width = 1 + max(x for x, _, _ in grid)
        height = 1 + max(y for _, y, _ in grid)
        candidates.append(((width + height, width, height, grid), grid))
    representative = min(candidates)[1]
    return representative, tuple(sorted(translations))


def translation_orbits(
    operator: PauliSum,
    lattice: SquareLattice,
    *,
    require_invariant: bool = True,
    unit_cell: tuple[int, int] = (1, 1),
) -> tuple[TranslationOrbit, ...]:
    remaining = set(operator.terms)
    result: list[TranslationOrbit] = []
    while remaining:
        seed = min(remaining)
        representative, members = canonical_translation(seed, lattice, unit_cell)
        present = tuple(member for member in members if member in operator.terms)
        coefficients = {operator.terms[member] for member in present}
        if require_invariant and (
            len(present) != len(members) or len(coefficients) != 1
        ):
            raise ValueError("operator is not translation invariant orbit by orbit")
        global_coefficient = operator.terms[seed]
        step_x, step_y = unit_cell
        n_translations = (
            lattice.length // step_x
        ) * (
            lattice.length // step_y
        )
        if n_translations % len(members):
            raise ArithmeticError("translation orbit size does not divide group size")
        stabilizer = n_translations // len(members)
        coefficient = global_coefficient / stabilizer
        result.append(
            TranslationOrbit(
                representative,
                coefficient,
                present,
                unit_cell,
                global_coefficient,
                stabilizer,
            )
        )
        remaining.difference_update(present)
    return tuple(sorted(result, key=lambda orbit: orbit.representative))


def embed_grid_op(grid: GridOp, patch_width: int, offset_x: int, offset_y: int) -> PauliString:
    mapping: dict[int, str] = {}
    for x, y, op in grid:
        mapping[(y + offset_y) * patch_width + x + offset_x] = op
    return PauliString(mapping)
