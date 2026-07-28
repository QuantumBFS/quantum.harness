"""Sparse occupation-basis operators for the autoregressive route."""

from __future__ import annotations

import math
import struct
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, localcontext
from numbers import Integral, Real
from types import MappingProxyType

import numpy as np


NeighborMap = dict[int, complex]
LogAmplitude = Callable[[int], complex]

# The maximum-norm Hermitian defect is compared with this fraction of the
# maximum matrix-element magnitude. A zero matrix therefore has zero tolerance.
HERMITIAN_RELATIVE_TOLERANCE = 1.0e-12
_MAX_FLOAT = float(np.finfo(np.float64).max)
_MIN_SUBNORMAL = math.ldexp(1.0, -1074)
_FAST_COMPONENT_MIN = math.ldexp(1.0, -900)
_FAST_COMPONENT_MAX = _MAX_FLOAT / 32.0
_LN_2 = math.log(2.0)
_LOG_10_OF_2 = math.log10(2.0)
_LOG_10_OF_5 = math.log10(5.0)
_FALLBACK_BASE_PRECISION = 1600
_FALLBACK_MAX_PRECISION = 6400


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


def _validated_coefficient(coefficient: complex, *, label: str) -> complex:
    """Retain both finite binary64 rectangular components without rescaling."""

    if not math.isfinite(coefficient.real) or not math.isfinite(
        coefficient.imag
    ):
        raise ValueError(f"{label} must be finite")
    return coefficient


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


def _float_bits(value: float) -> int:
    if value == 0.0:
        return 0
    return struct.unpack(">Q", struct.pack(">d", value))[0]


@dataclass(frozen=True, slots=True)
class _Dyadic:
    """Exact ``mantissa * 2**exponent`` representation of binary64 data."""

    mantissa: int
    exponent: int


def _normalized_dyadic(mantissa: int, exponent: int) -> _Dyadic:
    if mantissa == 0:
        return _Dyadic(0, 0)
    trailing = (abs(mantissa) & -abs(mantissa)).bit_length() - 1
    return _Dyadic(mantissa >> trailing, exponent + trailing)


def _dyadic_from_float(value: float) -> _Dyadic:
    if value == 0.0:
        return _Dyadic(0, 0)
    numerator, denominator = value.as_integer_ratio()
    return _normalized_dyadic(numerator, -(denominator.bit_length() - 1))


def _dyadic_add(left: _Dyadic, right: _Dyadic) -> _Dyadic:
    if left.mantissa == 0:
        return right
    if right.mantissa == 0:
        return left
    exponent = min(left.exponent, right.exponent)
    mantissa = (
        (left.mantissa << (left.exponent - exponent))
        + (right.mantissa << (right.exponent - exponent))
    )
    return _normalized_dyadic(mantissa, exponent)


def _dyadic_negate(value: _Dyadic) -> _Dyadic:
    return _Dyadic(-value.mantissa, value.exponent)


def _dyadic_multiply(left: _Dyadic, right: _Dyadic) -> _Dyadic:
    return _normalized_dyadic(
        left.mantissa * right.mantissa,
        left.exponent + right.exponent,
    )


def _dyadic_to_decimal(value: _Dyadic) -> Decimal:
    return Decimal(value.mantissa) * (Decimal(2) ** value.exponent)


def _dyadic_required_decimal_digits(value: _Dyadic) -> int:
    if value.mantissa == 0:
        return 1
    mantissa_bits = abs(value.mantissa).bit_length()
    if value.exponent >= 0:
        return int((mantissa_bits + value.exponent) * _LOG_10_OF_2) + 4
    return int(
        mantissa_bits * _LOG_10_OF_2
        + (-value.exponent) * _LOG_10_OF_5
    ) + 4


def _dyadic_logabs(value: _Dyadic) -> float:
    magnitude = abs(value.mantissa)
    bits = magnitude.bit_length()
    shift = max(bits - 53, 0)
    leading = magnitude >> shift
    return math.fsum(
        (
            math.log(float(leading)),
            float(shift + value.exponent) * _LN_2,
        )
    )


def _dyadic_to_float(value: _Dyadic) -> float | None:
    try:
        result = math.ldexp(float(value.mantissa), value.exponent)
    except OverflowError:
        return None
    if not math.isfinite(result) or result == 0.0 and value.mantissa != 0:
        return None
    return result


def _dyadic_ratio_float(left: _Dyadic, right: _Dyadic) -> float | None:
    try:
        ratio = float(left.mantissa) / float(right.mantissa)
        ratio = math.ldexp(ratio, left.exponent - right.exponent)
    except (OverflowError, ZeroDivisionError):
        return None
    if not math.isfinite(ratio) or ratio == 0.0 and left.mantissa != 0:
        return None
    return ratio


@dataclass(frozen=True, slots=True)
class _DyadicLogTerm:
    target_logabs: float
    value: _Dyadic

    @property
    def sort_key(self) -> tuple[int, int, int]:
        return (
            _float_bits(self.target_logabs),
            self.value.exponent,
            self.value.mantissa,
        )


def _effective_log(term: _DyadicLogTerm) -> float:
    try:
        return math.fsum((term.target_logabs, _dyadic_logabs(term.value)))
    except OverflowError:
        return math.copysign(math.inf, term.target_logabs)


def _try_fast_component(
    terms: Sequence[_DyadicLogTerm],
    source_logabs: float,
) -> float | None:
    """Deterministic ordinary-row path using true dyadic component ratios."""

    anchor = max(terms, key=lambda term: (_effective_log(term), term.sort_key))
    relative_terms: list[float] = []
    for term in sorted(terms, key=lambda item: item.sort_key):
        ratio = _dyadic_ratio_float(term.value, anchor.value)
        if ratio is None:
            return None
        try:
            target_delta = math.fsum(
                (term.target_logabs, -anchor.target_logabs)
            )
        except OverflowError:
            return None
        if not math.isfinite(target_delta) or abs(target_delta) > 745.0:
            return None
        relative = ratio * math.exp(target_delta)
        if not math.isfinite(relative) or relative == 0.0:
            return None
        relative_terms.append(relative)

    try:
        scaled = math.fsum(relative_terms)
        absolute_sum = math.fsum(abs(value) for value in relative_terms)
    except OverflowError:
        return None
    if scaled == 0.0 or not math.isfinite(scaled):
        return None
    if absolute_sum > abs(scaled) * math.ldexp(1.0, 20):
        return None

    anchor_value = _dyadic_to_float(anchor.value)
    if anchor_value is None:
        return None
    try:
        source_delta = math.fsum((anchor.target_logabs, -source_logabs))
    except OverflowError:
        return None
    if not math.isfinite(source_delta) or abs(source_delta) > 700.0:
        return None
    base = anchor_value * math.exp(source_delta)
    candidate = base * scaled
    if not math.isfinite(candidate) or candidate == 0.0:
        return None
    magnitude = abs(candidate)
    if not _FAST_COMPONENT_MIN <= magnitude <= _FAST_COMPONENT_MAX:
        return None
    return candidate


def _decimal_component_once(
    terms: Sequence[_DyadicLogTerm],
    source_logabs: float,
    precision: int,
) -> tuple[str, float | None, bool]:
    with localcontext() as context:
        context.prec = precision
        context.Emax = 999_999
        context.Emin = -999_999

        anchor = max(terms, key=lambda term: (_effective_log(term), term.sort_key))
        anchor_effective = _effective_log(anchor)
        band_limit = precision * math.log(10.0) * 0.75
        included: list[_DyadicLogTerm] = []
        lower: list[_DyadicLogTerm] = []
        for term in terms:
            difference = anchor_effective - _effective_log(term)
            if difference <= band_limit + 64.0:
                included.append(term)
            else:
                lower.append(term)

        anchor_decimal = abs(_dyadic_to_decimal(anchor.value))
        scaled = Decimal(0)
        scaled_absolute_sum = Decimal(0)
        anchor_target = Decimal.from_float(anchor.target_logabs)
        for term in sorted(included, key=lambda item: item.sort_key):
            ratio = _dyadic_to_decimal(term.value) / anchor_decimal
            target_delta = Decimal.from_float(term.target_logabs) - anchor_target
            if abs(target_delta) > Decimal(100_000):
                return "indeterminate", None, False
            contribution = ratio * target_delta.exp()
            scaled += contribution
            scaled_absolute_sum += abs(contribution)

        rounding_uncertainty = (
            scaled_absolute_sum + abs(scaled) + Decimal(1)
        ) * (Decimal(10) ** (-precision + 64))
        lower_uncertainty = Decimal(len(lower)) * Decimal(
            -band_limit
        ).exp()
        scaled_uncertainty = rounding_uncertainty + lower_uncertainty
        if scaled == 0 or abs(scaled) <= scaled_uncertainty * 4:
            return "indeterminate", None, False

        source_delta = anchor_target - Decimal.from_float(source_logabs)
        base_logabs = anchor_decimal.ln() + source_delta
        final_logabs = base_logabs + abs(scaled).ln()
        maximum_logabs = Decimal.from_float(_MAX_FLOAT).ln()
        half_minimum_logabs = (
            Decimal.from_float(_MIN_SUBNORMAL) / Decimal(2)
        ).ln()

        if final_logabs > maximum_logabs + Decimal(2):
            return "overflow", None, True
        if final_logabs < half_minimum_logabs - Decimal(2):
            return "value", math.copysign(0.0, float(scaled)), True
        if abs(source_delta) > Decimal(100_000):
            return "indeterminate", None, False

        base = anchor_decimal * source_delta.exp()
        central = base * scaled
        absolute_uncertainty = abs(base) * scaled_uncertainty
        lower_endpoint = central - absolute_uncertainty
        upper_endpoint = central + absolute_uncertainty
        candidate = float(central)
        lower_float = float(lower_endpoint)
        upper_float = float(upper_endpoint)
        certified = (
            _float_bits(candidate) == _float_bits(lower_float)
            and _float_bits(candidate) == _float_bits(upper_float)
        )
        if not math.isfinite(candidate):
            return "overflow", None, certified
        return "value", candidate, certified


def _fallback_component(
    terms: Sequence[_DyadicLogTerm],
    source_logabs: float,
) -> float:
    required_digits = max(
        _FALLBACK_BASE_PRECISION,
        *( _dyadic_required_decimal_digits(term.value) + 64 for term in terms),
    )
    precision = _FALLBACK_BASE_PRECISION
    while precision < required_digits:
        precision *= 2
    while precision <= _FALLBACK_MAX_PRECISION:
        status, value, certified = _decimal_component_once(
            terms,
            source_logabs,
            precision,
        )
        if certified:
            if status == "overflow":
                raise OverflowError(
                    "local estimator result is outside complex128 range"
                )
            assert value is not None
            return value
        precision *= 2
    raise ArithmeticError(
        "local estimator rounding is indeterminate at precision limit"
    )


def _sum_dyadic_component(
    terms: Sequence[_DyadicLogTerm],
    source_logabs: float,
) -> float:
    if not terms:
        return 0.0
    fast = _try_fast_component(terms, source_logabs)
    if fast is not None:
        return fast
    return _fallback_component(terms, source_logabs)


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

    factor_groups: dict[
        tuple[int, int, int],
        tuple[float, complex, _Dyadic, _Dyadic],
    ] = {}
    for target_raw, coefficient_raw in neighbors.items():
        target = _validated_nonnegative_state(target_raw)
        coefficient = _validated_coefficient(
            _scalar_complex(
                coefficient_raw,
                label="neighbor coefficient",
            ),
            label="neighbor coefficient",
        )
        if coefficient == 0.0:
            continue
        target_logpsi = _logpsi_value(
            logpsi,
            target,
            label="neighbor logpsi",
            allow_zero=True,
        )
        if target_logpsi is None:
            continue
        phase = _phase_direction(
            target_logpsi.imag,
            source_logpsi.imag,
        )
        factor_key = (
            _float_bits(target_logpsi.real),
            _float_bits(phase.real),
            _float_bits(phase.imag),
        )
        coefficient_real = _dyadic_from_float(coefficient.real)
        coefficient_imaginary = _dyadic_from_float(coefficient.imag)
        previous = factor_groups.get(factor_key)
        if previous is None:
            factor_groups[factor_key] = (
                target_logpsi.real,
                phase,
                coefficient_real,
                coefficient_imaginary,
            )
        else:
            factor_groups[factor_key] = (
                previous[0],
                previous[1],
                _dyadic_add(previous[2], coefficient_real),
                _dyadic_add(previous[3], coefficient_imaginary),
            )

    target_groups: dict[int, tuple[float, _Dyadic, _Dyadic]] = {}
    for factor_key in sorted(factor_groups):
        target_logabs, phase, coefficient_real, coefficient_imaginary = (
            factor_groups[factor_key]
        )
        if coefficient_real.mantissa == 0 and coefficient_imaginary.mantissa == 0:
            continue
        phase_real = _dyadic_from_float(phase.real)
        phase_imaginary = _dyadic_from_float(phase.imag)
        rotated_real = _dyadic_add(
            _dyadic_multiply(coefficient_real, phase_real),
            _dyadic_negate(
                _dyadic_multiply(coefficient_imaginary, phase_imaginary)
            ),
        )
        rotated_imaginary = _dyadic_add(
            _dyadic_multiply(coefficient_real, phase_imaginary),
            _dyadic_multiply(coefficient_imaginary, phase_real),
        )
        target_key = _float_bits(target_logabs)
        previous_target = target_groups.get(target_key)
        if previous_target is None:
            target_groups[target_key] = (
                target_logabs,
                rotated_real,
                rotated_imaginary,
            )
        else:
            target_groups[target_key] = (
                previous_target[0],
                _dyadic_add(previous_target[1], rotated_real),
                _dyadic_add(previous_target[2], rotated_imaginary),
            )

    if not target_groups:
        return 0.0j
    real_terms = tuple(
        _DyadicLogTerm(target_logabs, real)
        for target_logabs, real, _imaginary in target_groups.values()
        if real.mantissa != 0
    )
    imaginary_terms = tuple(
        _DyadicLogTerm(target_logabs, imaginary)
        for target_logabs, _real, imaginary in target_groups.values()
        if imaginary.mantissa != 0
    )
    return complex(
        _sum_dyadic_component(
            real_terms,
            source_logpsi.real,
        ),
        _sum_dyadic_component(
            imaginary_terms,
            source_logpsi.real,
        ),
    )


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
