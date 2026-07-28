"""Sparse occupation-basis operators for the autoregressive route."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from numbers import Integral, Real
from types import MappingProxyType

import numpy as np


NeighborMap = dict[int, complex]
LogAmplitude = Callable[[int], complex]

# The maximum-norm Hermitian defect is compared with this fraction of the
# maximum matrix-element magnitude. A zero matrix therefore has zero tolerance.
HERMITIAN_RELATIVE_TOLERANCE = 1.0e-12
_LOG_MAX_FLOAT = math.log(np.finfo(np.float64).max)
_LOG_TWO = math.log(2.0)


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


def _coefficient_logpolar(
    coefficient: complex,
    *,
    label: str,
) -> tuple[float, complex, float, float]:
    """Validate a coefficient and return stable log-polar scale data.

    The rectangular components are normalized by their largest magnitude
    before a direction is formed.  If this normalization loses an originally
    nonzero component, the coefficient cannot be represented faithfully by
    the log-polar estimator and is rejected explicitly.
    """

    if not math.isfinite(coefficient.real) or not math.isfinite(
        coefficient.imag
    ):
        raise ValueError(f"{label} must be finite")
    rectangular_scale = max(abs(coefficient.real), abs(coefficient.imag))
    if rectangular_scale == 0.0:
        return -math.inf, 0.0j, 0.0, -math.inf

    scaled_real = coefficient.real / rectangular_scale
    scaled_imag = coefficient.imag / rectangular_scale
    if (
        coefficient.real != 0.0
        and scaled_real == 0.0
        or coefficient.imag != 0.0
        and scaled_imag == 0.0
    ):
        raise ValueError(
            f"{label} component dynamic range cannot be "
            "represented in log-polar form"
        )
    normalized_magnitude = math.hypot(scaled_real, scaled_imag)
    direction = complex(
        scaled_real / normalized_magnitude,
        scaled_imag / normalized_magnitude,
    )
    log_rectangular_scale = math.log(rectangular_scale)
    log_magnitude = log_rectangular_scale + math.log(normalized_magnitude)
    return (
        log_magnitude,
        direction,
        rectangular_scale,
        log_rectangular_scale,
    )


@dataclass(frozen=True, slots=True, init=False, eq=False)
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
        for coefficient in matrix.flat:
            value = complex(coefficient)
            if value != 0.0:
                _coefficient_logpolar(
                    value,
                    label="pair_matrix coefficient",
                )
        rectangular_scale = float(
            np.max(
                np.maximum(np.abs(matrix.real), np.abs(matrix.imag)),
                initial=0.0,
            )
        )
        normalized = (
            matrix / rectangular_scale
            if rectangular_scale != 0.0
            else matrix
        )
        scale = float(np.max(np.abs(normalized), initial=0.0))
        defect = float(
            np.max(
                np.abs(normalized - normalized.conj().T),
                initial=0.0,
            )
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


def _scalar_complex(raw_value: object, *, label: str) -> complex:
    value_array = np.asarray(raw_value)
    if value_array.shape != ():
        raise TypeError(f"{label} must be a scalar")
    try:
        return complex(value_array.item())
    except (TypeError, ValueError) as error:
        raise TypeError(f"{label} must be numeric") from error


def _logpsi_value(
    logpsi: LogAmplitude,
    state: int,
    *,
    label: str,
    allow_zero: bool,
) -> complex | None:
    value = _scalar_complex(logpsi(state), label=label)
    if value.real == -math.inf and math.isfinite(value.imag):
        if allow_zero:
            return None
        raise ValueError(f"{label} must represent a nonzero amplitude")
    if not math.isfinite(value.real) or not math.isfinite(value.imag):
        raise ValueError(
            f"{label} must have a finite log-magnitude and phase"
        )
    return value


def _phase_direction(target_phase: float, source_phase: float) -> complex:
    if target_phase == source_phase:
        return 1.0 + 0.0j
    period = 2.0 * math.pi
    difference = math.remainder(target_phase, period) - math.remainder(
        source_phase,
        period,
    )
    reduced = math.remainder(difference, period)
    return complex(math.cos(reduced), math.sin(reduced))


def _log_difference(
    coefficient_logabs: float,
    target_logabs: float,
    anchor_coefficient_logabs: float,
    anchor_target_logabs: float,
) -> float:
    values = (
        coefficient_logabs,
        target_logabs,
        -anchor_coefficient_logabs,
        -anchor_target_logabs,
    )
    try:
        return math.fsum(values)
    except OverflowError:
        exact = sum(
            (Decimal.from_float(value) for value in values),
            start=Decimal(0),
        )
        return float(exact)


def _scaled_exp_product(scale: float, relative_logabs: float) -> float:
    """Return ``scale * exp(relative_logabs)`` without intermediate overflow."""

    if relative_logabs == -math.inf:
        return 0.0
    if relative_logabs == math.inf:
        raise OverflowError("local estimator result is outside complex128 range")

    mantissa, exponent = math.frexp(scale)
    shift = math.floor(relative_logabs / _LOG_TWO)
    combined_exponent = exponent + shift
    if combined_exponent > 1024:
        raise OverflowError("local estimator result is outside complex128 range")
    if combined_exponent < -1075:
        return 0.0

    residual = math.fsum((relative_logabs, -shift * _LOG_TWO))
    if residual < 0.0:
        shift -= 1
        residual += _LOG_TWO
    elif residual >= _LOG_TWO:
        shift += 1
        residual -= _LOG_TWO
    try:
        result = math.ldexp(
            mantissa * math.exp(residual),
            exponent + shift,
        )
    except OverflowError as error:
        raise OverflowError(
            "local estimator result is outside complex128 range"
        ) from error
    if not math.isfinite(result):
        raise OverflowError("local estimator result is outside complex128 range")
    return result


def _restore_component(
    anchor_scale: float,
    anchor_logscale: float,
    relative_logabs: float,
    sign: float,
) -> float:
    if relative_logabs == -math.inf:
        return math.copysign(0.0, sign)
    if relative_logabs == math.inf:
        raise OverflowError("local estimator result is outside complex128 range")
    try:
        relative_magnitude = math.exp(relative_logabs)
    except OverflowError:
        relative_magnitude = math.inf
    if math.isfinite(relative_magnitude):
        candidate = anchor_scale * relative_magnitude
        if math.isfinite(candidate) and candidate != 0.0:
            return math.copysign(candidate, sign)
    full_logabs = _log_difference(
        anchor_logscale,
        relative_logabs,
        0.0,
        0.0,
    )
    if full_logabs == -math.inf:
        return math.copysign(0.0, sign)
    if full_logabs < _LOG_MAX_FLOAT:
        magnitude = math.exp(full_logabs)
    elif full_logabs > _LOG_MAX_FLOAT:
        raise OverflowError(
            "local estimator result is outside complex128 range"
        )
    else:
        magnitude = _scaled_exp_product(anchor_scale, relative_logabs)
    return math.copysign(magnitude, sign)


def local_from_log_neighbors(
    state: int,
    neighbors: Mapping[int, complex],
    logpsi: LogAmplitude,
) -> complex:
    """Evaluate ``sum_t H[s,t] exp(logpsi(t) - logpsi(s))`` stably."""

    source = _validated_nonnegative_state(state)
    if not isinstance(neighbors, Mapping):
        raise TypeError("neighbors must be a mapping")
    if not callable(logpsi):
        raise TypeError("logpsi must be callable")
    source_logpsi = _logpsi_value(
        logpsi,
        source,
        label="sampled logpsi",
        allow_zero=False,
    )
    assert source_logpsi is not None

    terms: list[tuple[float, float, complex, float, float]] = []
    for target_raw, coefficient_raw in neighbors.items():
        target = _validated_nonnegative_state(target_raw)
        coefficient = _scalar_complex(
            coefficient_raw,
            label="neighbor coefficient",
        )
        if coefficient == 0.0:
            continue
        (
            coefficient_logabs,
            coefficient_direction,
            rectangular_scale,
            log_rectangular_scale,
        ) = _coefficient_logpolar(
            coefficient,
            label="neighbor coefficient",
        )
        target_logpsi = _logpsi_value(
            logpsi,
            target,
            label="neighbor logpsi",
            allow_zero=True,
        )
        if target_logpsi is None:
            continue
        direction = coefficient_direction * _phase_direction(
            target_logpsi.imag,
            source_logpsi.imag,
        )
        terms.append(
            (
                coefficient_logabs,
                target_logpsi.real,
                direction,
                rectangular_scale,
                log_rectangular_scale,
            )
        )
    if not terms:
        return 0.0j

    anchor_index = 0
    for index in range(1, len(terms)):
        coefficient_logabs, target_logabs, _, _, _ = terms[index]
        anchor_coefficient_logabs, anchor_target_logabs, _, _, _ = terms[
            anchor_index
        ]
        difference = _log_difference(
            coefficient_logabs,
            target_logabs,
            anchor_coefficient_logabs,
            anchor_target_logabs,
        )
        # Effective ties use the largest exact rectangular scale so the
        # restoration path is independent of neighbor insertion order.
        if difference > 0.0 or (
            difference == 0.0
            and terms[index][3] > terms[anchor_index][3]
        ):
            anchor_index = index

    (
        anchor_coefficient_logabs,
        anchor_target_logabs,
        _,
        anchor_scale,
        anchor_logscale,
    ) = terms[anchor_index]
    scaled_real: list[float] = []
    scaled_imag: list[float] = []
    for coefficient_logabs, target_logabs, direction, _, _ in terms:
        delta = _log_difference(
            coefficient_logabs,
            target_logabs,
            anchor_coefficient_logabs,
            anchor_target_logabs,
        )
        if delta == math.inf:
            raise OverflowError(
                "local estimator log scale is outside the supported range"
            )
        scaled_magnitude = math.exp(delta) if delta > -math.inf else 0.0
        scaled_real.append(scaled_magnitude * direction.real)
        scaled_imag.append(scaled_magnitude * direction.imag)

    bounded_real = math.fsum(scaled_real)
    bounded_imag = math.fsum(scaled_imag)
    if bounded_real == 0.0 and bounded_imag == 0.0:
        return 0.0j
    anchor_relative_logabs = _log_difference(
        anchor_coefficient_logabs,
        anchor_target_logabs,
        anchor_logscale,
        source_logpsi.real,
    )
    if anchor_relative_logabs == math.inf:
        raise OverflowError(
            "local estimator result is outside complex128 range"
        )
    if anchor_relative_logabs == -math.inf:
        return 0.0j

    components = []
    for bounded_component in (bounded_real, bounded_imag):
        if bounded_component == 0.0:
            components.append(0.0)
            continue
        relative_logabs = _log_difference(
            anchor_relative_logabs,
            math.log(abs(bounded_component)),
            0.0,
            0.0,
        )
        components.append(
            _restore_component(
                anchor_scale,
                anchor_logscale,
                relative_logabs,
                bounded_component,
            )
        )
    return complex(*components)


def local_energy(
    state: int,
    operator: PreparedPairOperator,
    logpsi: LogAmplitude,
) -> complex:
    """Evaluate the local energy for a Hermitian two-body Hamiltonian.

    ``two_body_neighbors`` constructs the source column ``H[target, source]``.
    Hermiticity therefore makes the required row entry ``H[source, target]``
    its complex conjugate, including for genuinely complex pair matrices.
    """

    column = two_body_neighbors(state, operator)
    row = {target: coefficient.conjugate() for target, coefficient in column.items()}
    return local_from_log_neighbors(state, row, logpsi)


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
    logpsi: LogAmplitude,
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
    return local_from_log_neighbors(source, neighbors, logpsi)
