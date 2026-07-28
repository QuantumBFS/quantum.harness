"""Sparse occupation-basis operators for the autoregressive route."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from numbers import Integral, Real
from types import MappingProxyType

import numpy as np


NeighborMap = dict[int, complex]
Amplitude = Callable[[int], complex]

# The maximum-norm Hermitian defect is compared with this fraction of the
# maximum matrix-element magnitude. A zero matrix therefore has zero tolerance.
HERMITIAN_RELATIVE_TOLERANCE = 1.0e-12


def _integer(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(f"{name} must be an integer")
    return int(value)


def _validated_state(state: object, two_q: object) -> tuple[int, int]:
    bitset = _integer("state", state)
    orbital_limit = _integer("two_q", two_q)
    if bitset < 0:
        raise ValueError("state must be non-negative")
    if orbital_limit < 0:
        raise ValueError("two_q must be non-negative")
    if bitset >= 1 << (orbital_limit + 1):
        raise ValueError("state has an occupation outside the orbital range")
    return bitset, orbital_limit


def _validated_nonnegative_state(state: object) -> int:
    bitset = _integer("state", state)
    if bitset < 0:
        raise ValueError("state must be non-negative")
    return bitset


def _orbital(name: str, value: object, two_q: int) -> int:
    orbital = _integer(name, value)
    if not 0 <= orbital <= two_q:
        raise ValueError(f"{name} must be in [0, {two_q}]")
    return orbital


def _annihilate(state: int, orbital: int) -> tuple[int, int] | None:
    mask = 1 << orbital
    if not state & mask:
        return None
    sign = -1 if (state & (mask - 1)).bit_count() % 2 else 1
    return state ^ mask, sign


def _create(state: int, orbital: int) -> tuple[int, int] | None:
    mask = 1 << orbital
    if state & mask:
        return None
    sign = -1 if (state & (mask - 1)).bit_count() % 2 else 1
    return state | mask, sign


def apply_one_body(
    state: int,
    a: int,
    c: int,
    two_q: int,
) -> tuple[int, int] | None:
    """Apply ``c_a^dagger c_c`` to an occupation bitset."""

    current, orbital_limit = _validated_state(state, two_q)
    target_orbital = _orbital("a", a, orbital_limit)
    source_orbital = _orbital("c", c, orbital_limit)
    annihilated = _annihilate(current, source_orbital)
    if annihilated is None:
        return None
    intermediate, sign_1 = annihilated
    created = _create(intermediate, target_orbital)
    if created is None:
        return None
    target, sign_2 = created
    return target, sign_1 * sign_2


def apply_two_body(
    state: int,
    a: int,
    b: int,
    c: int,
    d: int,
    two_q: int,
) -> tuple[int, int] | None:
    """Apply ``c_a^dagger c_b^dagger c_d c_c`` to a bitset."""

    current, orbital_limit = _validated_state(state, two_q)
    orbitals = (
        _orbital("a", a, orbital_limit),
        _orbital("b", b, orbital_limit),
        _orbital("c", c, orbital_limit),
        _orbital("d", d, orbital_limit),
    )
    target_a, target_b, source_c, source_d = orbitals
    sign = 1
    for operation, orbital in (
        (_annihilate, source_c),
        (_annihilate, source_d),
        (_create, target_b),
        (_create, target_a),
    ):
        applied = operation(current, orbital)
        if applied is None:
            return None
        current, step_sign = applied
        sign *= step_sign
    return current, sign


def _validated_pairs(
    pairs: Sequence[tuple[int, int]],
    two_q: int,
) -> tuple[tuple[int, int], ...]:
    try:
        entries = tuple(pairs)
    except TypeError as error:
        raise TypeError("pairs must be a sequence of orbital pairs") from error
    validated = []
    seen: set[tuple[int, int]] = set()
    for index, pair in enumerate(entries):
        if not isinstance(pair, Sequence) or isinstance(pair, (str, bytes)):
            raise TypeError(f"pairs[{index}] must contain two orbitals")
        if len(pair) != 2:
            raise ValueError(f"pairs[{index}] must contain two orbitals")
        first = _orbital(f"pairs[{index}][0]", pair[0], two_q)
        second = _orbital(f"pairs[{index}][1]", pair[1], two_q)
        if first >= second:
            raise ValueError(f"pairs[{index}] must use canonical order a < b")
        canonical_pair = (first, second)
        if canonical_pair in seen:
            raise ValueError("pairs must be globally unique")
        seen.add(canonical_pair)
        validated.append(canonical_pair)
    return tuple(validated)


def _validated_pair_matrix(
    pair_matrix: object,
    pair_count: int,
) -> np.ndarray:
    raw = np.asarray(pair_matrix)
    expected_shape = (pair_count, pair_count)
    if raw.shape != expected_shape:
        raise ValueError(f"pair_matrix must have shape {expected_shape}")
    try:
        matrix = np.array(pair_matrix, dtype=np.complex128, copy=True, order="C")
    except (TypeError, ValueError) as error:
        raise TypeError("pair_matrix must contain numeric values") from error
    if not np.all(np.isfinite(matrix)):
        raise ValueError("pair_matrix must contain only finite values")
    return matrix


@dataclass(frozen=True, slots=True, init=False)
class PreparedPairOperator:
    """Validated, immutable pair data prepared once outside sampling loops.

    Hermiticity uses the scale-relative maximum-norm criterion
    ``max(abs(A - A^dagger)) <= HERMITIAN_RELATIVE_TOLERANCE * max(abs(A))``.
    The matrix owns no writable buffer, and nonzero target rows are cached per
    source column so per-configuration work never rescans the pair matrix.
    """

    two_q: int
    pairs: tuple[tuple[int, int], ...]
    matrix: np.ndarray
    nonzero_by_column: tuple[tuple[tuple[int, complex], ...], ...]
    source_column_by_pair: Mapping[tuple[int, int], int]

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError(
            "PreparedPairOperator instances must be created with build()"
        )

    @classmethod
    def build(
        cls,
        pairs: Sequence[tuple[int, int]],
        pair_matrix: object,
        two_q: int,
    ) -> PreparedPairOperator:
        orbital_limit = _integer("two_q", two_q)
        if orbital_limit < 0:
            raise ValueError("two_q must be non-negative")
        pair_basis = _validated_pairs(pairs, orbital_limit)
        matrix = _validated_pair_matrix(pair_matrix, len(pair_basis))
        scale = float(np.max(np.abs(matrix), initial=0.0))
        defect = float(
            np.max(np.abs(matrix - matrix.conj().T), initial=0.0)
        )
        tolerance = HERMITIAN_RELATIVE_TOLERANCE * scale
        if defect > tolerance:
            raise ValueError(
                "pair_matrix must be Hermitian within relative tolerance "
                f"{HERMITIAN_RELATIVE_TOLERANCE:g}"
            )

        nonzero_by_column = tuple(
            tuple(
                (int(row), complex(matrix[row, column]))
                for row in np.flatnonzero(matrix[:, column] != 0.0)
            )
            for column in range(len(pair_basis))
        )
        frozen_matrix = np.frombuffer(
            matrix.tobytes(order="C"),
            dtype=np.complex128,
        ).reshape(matrix.shape)
        instance = object.__new__(cls)
        object.__setattr__(instance, "two_q", orbital_limit)
        object.__setattr__(instance, "pairs", pair_basis)
        object.__setattr__(instance, "matrix", frozen_matrix)
        object.__setattr__(instance, "nonzero_by_column", nonzero_by_column)
        object.__setattr__(
            instance,
            "source_column_by_pair",
            MappingProxyType(
                {pair: column for column, pair in enumerate(pair_basis)}
            ),
        )
        return instance


def two_body_neighbors(
    state: int,
    operator: PreparedPairOperator,
) -> NeighborMap:
    """Return sparse ``H[target, source]`` entries for one source bitset.

    The pair matrix uses target-pair rows and source-pair columns. Repeated
    determinant targets are merged before this mapping is returned.
    """

    if not isinstance(operator, PreparedPairOperator):
        raise TypeError("operator must be a PreparedPairOperator")
    source, orbital_limit = _validated_state(state, operator.two_q)
    occupied_orbitals = [
        orbital
        for orbital in range(orbital_limit + 1)
        if source & (1 << orbital)
    ]
    neighbors: NeighborMap = {}
    for first_index, c in enumerate(occupied_orbitals):
        for d in occupied_orbitals[first_index + 1 :]:
            column = operator.source_column_by_pair.get((c, d))
            if column is None:
                continue
            for row, matrix_element in operator.nonzero_by_column[column]:
                a, b = operator.pairs[row]
                applied = apply_two_body(
                    source,
                    a=a,
                    b=b,
                    c=c,
                    d=d,
                    two_q=orbital_limit,
                )
                if applied is None:
                    continue
                target, sign = applied
                neighbors[target] = (
                    neighbors.get(target, 0.0j) + sign * matrix_element
                )
    return {
        target: coefficient
        for target, coefficient in neighbors.items()
        if coefficient != 0.0
    }


def _amplitude_value(
    amplitude: Amplitude,
    state: int,
    *,
    label: str,
) -> complex:
    try:
        raw_value = amplitude(state)
    except TypeError:
        raise
    value_array = np.asarray(raw_value)
    if value_array.shape != ():
        raise TypeError(f"{label} must be a scalar")
    try:
        value = complex(value_array.item())
    except (TypeError, ValueError) as error:
        raise TypeError(f"{label} must be numeric") from error
    if not math.isfinite(value.real) or not math.isfinite(value.imag):
        raise ValueError(f"{label} must be finite")
    return value


def local_from_neighbors(
    state: int,
    neighbors: Mapping[int, complex],
    amplitude: Amplitude,
) -> complex:
    """Evaluate ``sum_t H[s,t] psi(t) / psi(s)`` from a sparse row."""

    source = _validated_nonnegative_state(state)
    if not isinstance(neighbors, Mapping):
        raise TypeError("neighbors must be a mapping")
    if not callable(amplitude):
        raise TypeError("amplitude must be callable")
    denominator = _amplitude_value(
        amplitude,
        source,
        label="sampled amplitude",
    )
    if denominator == 0.0:
        raise ValueError("sampled amplitude must be nonzero")

    numerator = 0.0j
    for target_raw, coefficient_raw in neighbors.items():
        target = _validated_nonnegative_state(target_raw)
        coefficient_array = np.asarray(coefficient_raw)
        if coefficient_array.shape != ():
            raise TypeError("neighbor coefficient must be a scalar")
        try:
            coefficient = complex(coefficient_array.item())
        except (TypeError, ValueError) as error:
            raise TypeError("neighbor coefficient must be numeric") from error
        if not math.isfinite(coefficient.real) or not math.isfinite(coefficient.imag):
            raise ValueError("neighbor coefficient must be finite")
        if coefficient == 0.0:
            continue
        target_amplitude = _amplitude_value(
            amplitude,
            target,
            label="neighbor amplitude",
        )
        numerator += coefficient * target_amplitude
    return numerator / denominator


def local_energy(
    state: int,
    operator: PreparedPairOperator,
    amplitude: Amplitude,
) -> complex:
    """Evaluate the local energy for a Hermitian two-body Hamiltonian.

    ``two_body_neighbors`` constructs the source column ``H[target, source]``.
    Hermiticity therefore makes the required row entry ``H[source, target]``
    its complex conjugate, including for genuinely complex pair matrices.
    """

    column = two_body_neighbors(state, operator)
    row = {target: coefficient.conjugate() for target, coefficient in column.items()}
    return local_from_neighbors(state, row, amplitude)


def ladder_neighbors(
    state: int,
    two_q: int,
    direction: int,
) -> NeighborMap:
    """Return sparse total angular-momentum ladder neighbors.

    ``direction=1`` applies ``L_+`` and ``direction=-1`` applies ``L_-``.
    """

    source, orbital_limit = _validated_state(state, two_q)
    step = _integer("direction", direction)
    if step not in (-1, 1):
        raise ValueError("direction must be -1 or 1")
    neighbors: NeighborMap = {}
    for orbital in range(orbital_limit + 1):
        if not source & (1 << orbital):
            continue
        destination = orbital + step
        if not 0 <= destination <= orbital_limit:
            continue
        applied = apply_one_body(
            source,
            a=destination,
            c=orbital,
            two_q=orbital_limit,
        )
        if applied is None:
            continue
        target, sign = applied
        lower = min(orbital, destination)
        coefficient = math.sqrt((orbital_limit - lower) * (lower + 1))
        neighbors[target] = neighbors.get(target, 0.0j) + sign * coefficient
    return neighbors


def compose_ladders(state: int, two_q: int) -> NeighborMap:
    """Return sparse entries of ``L_- L_+`` for one source bitset."""

    source, orbital_limit = _validated_state(state, two_q)
    neighbors: NeighborMap = {}
    for raised, coefficient_up in ladder_neighbors(
        source,
        orbital_limit,
        direction=1,
    ).items():
        for final, coefficient_down in ladder_neighbors(
            raised,
            orbital_limit,
            direction=-1,
        ).items():
            neighbors[final] = (
                neighbors.get(final, 0.0j)
                + coefficient_down * coefficient_up
            )
    return {
        target: coefficient
        for target, coefficient in neighbors.items()
        if coefficient != 0.0
    }


def _target_m2(target_m: object) -> int:
    if isinstance(target_m, bool) or not isinstance(target_m, Real):
        raise TypeError("target_m must be a finite integer or half-integer")
    value = float(target_m)
    if not math.isfinite(value):
        raise ValueError("target_m must be a finite integer or half-integer")
    doubled = 2.0 * value
    rounded = round(doubled)
    if doubled != rounded:
        raise ValueError("target_m must be a finite integer or half-integer")
    return rounded


def local_l2(
    state: int,
    two_q: int,
    target_m: float,
    amplitude: Amplitude,
) -> complex:
    """Evaluate ``L_- L_+ + M(M+1)`` locally in a fixed-M sector."""

    source, orbital_limit = _validated_state(state, two_q)
    target_m2 = _target_m2(target_m)
    actual_m2 = sum(
        -orbital_limit + 2 * orbital
        for orbital in range(orbital_limit + 1)
        if source & (1 << orbital)
    )
    if actual_m2 != target_m2:
        raise ValueError("state is not in the requested target_m sector")

    neighbors = compose_ladders(source, orbital_limit)
    diagonal = (target_m2 / 2.0) * (target_m2 / 2.0 + 1.0)
    if diagonal != 0.0:
        neighbors[source] = neighbors.get(source, 0.0j) + diagonal
    return local_from_neighbors(source, neighbors, amplitude)
