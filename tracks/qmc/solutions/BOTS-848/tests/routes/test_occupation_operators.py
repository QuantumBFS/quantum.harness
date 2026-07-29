from __future__ import annotations

import math
import random
import struct
from collections import Counter
from decimal import (
    ROUND_CEILING,
    ROUND_FLOOR,
    ROUND_HALF_EVEN,
    Decimal,
    localcontext,
)
from itertools import permutations

import numpy as np
import pytest

from benchmark_v0.fock_ed import (
    apply_annihilation,
    apply_creation,
    apply_two_body as oracle_apply_two_body,
    fixed_m_basis,
    full_basis,
    hamiltonian_matrix,
    l_plus_matrix,
    l_squared_matrix,
)
from benchmark_v0.lll_coulomb import (
    antisymmetrized_pair_matrix,
    coulomb_integrals,
)
from scalable_v1.routes.occupation_autoregressive import operators
from scalable_v1.routes.occupation_autoregressive.operators import (
    PreparedPairOperator,
    apply_one_body,
    apply_two_body,
    compose_ladders,
    ladder_neighbors,
    local_energy,
    local_from_log_neighbors,
    local_l2,
    two_body_neighbors,
)


def _oracle_apply_one_body(
    state: int,
    *,
    a: int,
    c: int,
) -> tuple[int, int] | None:
    annihilated = apply_annihilation(state, c)
    if annihilated is None:
        return None
    intermediate, sign_1 = annihilated
    created = apply_creation(intermediate, a)
    if created is None:
        return None
    target, sign_2 = created
    return target, sign_1 * sign_2


def _logpsi_from_basis(
    basis: tuple[int, ...],
    values: np.ndarray,
    *,
    real_shift: float = 0.0,
    phase_shift: float = 0.0,
):
    log_values = {
        state: (
            complex(-math.inf, phase_shift)
            if value == 0.0
            else complex(
                math.log(abs(value)) + real_shift,
                math.atan2(value.imag, value.real) + phase_shift,
            )
        )
        for state, value in zip(basis, values, strict=True)
    }
    return log_values.__getitem__


def _oracle_phase_direction(target_phase: float, source_phase: float) -> complex:
    if target_phase == source_phase:
        return 1.0 + 0.0j
    period = 2.0 * math.pi
    difference = math.remainder(target_phase, period) - math.remainder(
        source_phase,
        period,
    )
    reduced = math.remainder(difference, period)
    return complex(math.cos(reduced), math.sin(reduced))


def _decimal_row_oracle(
    state: int,
    neighbors: dict[int, complex],
    log_values: dict[int, complex],
) -> complex:
    """Independent whole-row oracle using exact binary64 Decimal inputs."""

    source = log_values[state]
    with localcontext() as context:
        context.prec = 2500
        context.Emax = 999_999
        context.Emin = -999_999
        real = Decimal(0)
        imaginary = Decimal(0)
        for target, coefficient in neighbors.items():
            target_logpsi = log_values[target]
            phase = _oracle_phase_direction(target_logpsi.imag, source.imag)
            coefficient_real = Decimal.from_float(coefficient.real)
            coefficient_imaginary = Decimal.from_float(coefficient.imag)
            phase_real = Decimal.from_float(phase.real)
            phase_imaginary = Decimal.from_float(phase.imag)
            rotated_real = (
                coefficient_real * phase_real
                - coefficient_imaginary * phase_imaginary
            )
            rotated_imaginary = (
                coefficient_real * phase_imaginary
                + coefficient_imaginary * phase_real
            )
            relative_logabs = Decimal.from_float(
                target_logpsi.real
            ) - Decimal.from_float(source.real)
            factor = relative_logabs.exp()
            real += rotated_real * factor
            imaginary += rotated_imaginary * factor
    return complex(float(real), float(imaginary))


def _float_hex(value: float) -> str:
    return struct.pack(">d", value).hex()


def test_route_local_fermion_actions_match_fock_ed_term_by_term() -> None:
    two_q = 3
    for state in range(1 << (two_q + 1)):
        for a in range(two_q + 1):
            for c in range(two_q + 1):
                assert apply_one_body(state, a=a, c=c, two_q=two_q) == (
                    _oracle_apply_one_body(state, a=a, c=c)
                )
                for b in range(two_q + 1):
                    for d in range(two_q + 1):
                        # Convention: c_a^dagger c_b^dagger c_d c_c.
                        assert apply_two_body(
                            state,
                            a=a,
                            b=b,
                            c=c,
                            d=d,
                            two_q=two_q,
                        ) == oracle_apply_two_body(
                            state,
                            a=a,
                            b=b,
                            c=c,
                            d=d,
                        )


def test_fermion_actions_include_pauli_zero_and_repeated_indices() -> None:
    source = (1 << 0) | (1 << 2)

    assert apply_one_body(source, a=1, c=1, two_q=3) is None
    assert apply_one_body(source, a=2, c=0, two_q=3) is None
    assert apply_two_body(source, a=1, b=1, c=0, d=2, two_q=3) is None
    assert apply_two_body(source, a=1, b=3, c=0, d=0, two_q=3) is None


@pytest.mark.parametrize(
    ("function", "kwargs", "error", "message"),
    [
        (apply_one_body, {"state": True, "a": 0, "c": 0, "two_q": 1}, TypeError, "state must be an integer"),
        (apply_one_body, {"state": -1, "a": 0, "c": 0, "two_q": 1}, ValueError, "non-negative"),
        (apply_one_body, {"state": 4, "a": 0, "c": 0, "two_q": 1}, ValueError, "outside the orbital range"),
        (apply_one_body, {"state": 1, "a": True, "c": 0, "two_q": 1}, TypeError, "a must be an integer"),
        (apply_one_body, {"state": 1, "a": 2, "c": 0, "two_q": 1}, ValueError, "a must be in"),
        (apply_two_body, {"state": 3, "a": 0, "b": 1, "c": 0, "d": -1, "two_q": 1}, ValueError, "d must be in"),
        (apply_two_body, {"state": 3, "a": 0, "b": 1, "c": 0, "d": 1, "two_q": 1.0}, TypeError, "two_q must be an integer"),
    ],
)
def test_fermion_actions_reject_bad_types_and_ranges(
    function,
    kwargs: dict[str, object],
    error: type[Exception],
    message: str,
) -> None:
    with pytest.raises(error, match=message):
        function(**kwargs)


def test_local_energy_matches_tiny_public_coulomb_hamiltonian() -> None:
    two_q = 6
    basis = fixed_m_basis(3, two_q, 0.0)
    integrals = coulomb_integrals(two_q, n_theta=20, n_phi=28)
    pairs, pair_matrix = antisymmetrized_pair_matrix(integrals)
    operator = PreparedPairOperator.build(pairs, pair_matrix, two_q)
    hamiltonian = hamiltonian_matrix(basis, pairs, pair_matrix)
    values = np.array(
        [1.0 + 0.17j * (index + 1) for index in range(len(basis))],
        dtype=np.complex128,
    )
    logpsi = _logpsi_from_basis(basis, values)
    expected = hamiltonian @ values

    for index, state in enumerate(basis):
        assert local_energy(
            state,
            operator=operator,
            logpsi=logpsi,
        ) == pytest.approx(expected[index] / values[index], abs=1.0e-12)


def test_local_energy_uses_h_current_target_for_complex_hermitian_input() -> None:
    two_q = 3
    pairs = ((0, 1), (2, 3))
    pair_matrix = np.array(
        [[0.0, 1.0 + 2.0j], [1.0 - 2.0j, 0.0]],
        dtype=np.complex128,
    )
    operator = PreparedPairOperator.build(pairs, pair_matrix, two_q)
    basis = full_basis(2, two_q)
    hamiltonian = hamiltonian_matrix(basis, pairs, pair_matrix)
    values = np.array(
        [1.0 + (0.1 + 0.2j) * index for index in range(len(basis))],
        dtype=np.complex128,
    )
    logpsi = _logpsi_from_basis(basis, values)

    assert pair_matrix[0, 1] != pair_matrix[1, 0]
    for index, state in enumerate(basis):
        expected = (hamiltonian @ values)[index] / values[index]
        assert local_energy(
            state,
            operator=operator,
            logpsi=logpsi,
        ) == pytest.approx(expected, abs=1.0e-12)


def test_random_complex_hermitian_prepared_operator_matches_full_basis() -> None:
    two_q = 4
    pairs = tuple(
        (a, b)
        for a in range(two_q + 1)
        for b in range(a + 1, two_q + 1)
    )
    rng = np.random.default_rng(848)
    raw = rng.normal(size=(len(pairs), len(pairs))) + 1j * rng.normal(
        size=(len(pairs), len(pairs))
    )
    pair_matrix = raw + raw.conj().T
    operator = PreparedPairOperator.build(pairs, pair_matrix, two_q)
    basis = full_basis(2, two_q)
    hamiltonian = hamiltonian_matrix(basis, pairs, pair_matrix)
    values = rng.normal(size=len(basis)) + 1j * rng.normal(size=len(basis))
    values += 1.0 + 0.5j
    logpsi = _logpsi_from_basis(basis, values)

    for index, state in enumerate(basis):
        expected = (hamiltonian @ values)[index] / values[index]
        assert local_energy(
            state,
            operator=operator,
            logpsi=logpsi,
        ) == pytest.approx(expected, abs=1.0e-12)


def test_two_body_neighbors_merge_repeated_targets_before_amplitude_calls() -> None:
    two_q = 4
    pairs = tuple((a, b) for a in range(5) for b in range(a + 1, 5))
    pair_index = {pair: index for index, pair in enumerate(pairs)}
    pair_matrix = np.zeros((len(pairs), len(pairs)), dtype=np.complex128)
    pair_matrix[pair_index[(0, 3)], pair_index[(0, 2)]] = 2.0
    pair_matrix[pair_index[(1, 3)], pair_index[(1, 2)]] = -0.5
    pair_matrix += pair_matrix.conj().T
    operator = PreparedPairOperator.build(pairs, pair_matrix, two_q)
    source = (1 << 0) | (1 << 1) | (1 << 2)
    target = (1 << 0) | (1 << 1) | (1 << 3)

    neighbors = two_body_neighbors(
        source,
        operator=operator,
    )
    assert set(neighbors) == {target}

    calls: Counter[int] = Counter()

    def logpsi(state: int) -> complex:
        calls[state] += 1
        value = 1.0 + 0.25j * state
        return complex(math.log(abs(value)), math.atan2(value.imag, value.real))

    local_energy(
        source,
        operator=operator,
        logpsi=logpsi,
    )

    assert calls[target] == 1
    assert calls[source] == 1


def test_ladder_neighbors_matches_tiny_l_plus_matrix() -> None:
    two_q = 6
    source_basis = fixed_m_basis(3, two_q, 0.0)
    target_basis = fixed_m_basis(3, two_q, 1.0)
    expected = l_plus_matrix(source_basis, target_basis, two_q=two_q)
    target_index = {state: index for index, state in enumerate(target_basis)}

    for column, state in enumerate(source_basis):
        observed = ladder_neighbors(state, two_q, direction=1)
        observed_column = np.zeros(len(target_basis), dtype=np.complex128)
        for target, coefficient in observed.items():
            observed_column[target_index[target]] += coefficient
        np.testing.assert_allclose(observed_column, expected[:, column], atol=1.0e-14)


def test_ladder_coefficient_and_fermion_sign_are_explicit() -> None:
    two_q = 4
    source = (1 << 0) | (1 << 2)

    assert ladder_neighbors(source, two_q, direction=1) == {
        (1 << 1) | (1 << 2): math.sqrt(4.0),
        (1 << 0) | (1 << 3): math.sqrt(6.0),
    }
    assert ladder_neighbors((1 << 0) | (1 << 1), two_q, direction=1) == {
        (1 << 0) | (1 << 2): math.sqrt(6.0),
    }


def test_compose_ladders_merges_paths_and_keeps_diagonal_return() -> None:
    two_q = 6
    basis = fixed_m_basis(3, two_q, 0.0)
    raised_basis = fixed_m_basis(3, two_q, 1.0)
    l_plus = l_plus_matrix(basis, raised_basis, two_q=two_q)
    expected = l_plus.T @ l_plus
    basis_index = {state: index for index, state in enumerate(basis)}

    saw_merged_target = False
    for column, state in enumerate(basis):
        observed = compose_ladders(state, two_q)
        assert state in observed
        observed_column = np.zeros(len(basis), dtype=np.complex128)
        for target, coefficient in observed.items():
            observed_column[basis_index[target]] += coefficient
        np.testing.assert_allclose(observed_column, expected[:, column], atol=1.0e-14)

        path_targets = []
        for raised in ladder_neighbors(state, two_q, direction=1):
            path_targets.extend(ladder_neighbors(raised, two_q, direction=-1))
        saw_merged_target |= len(path_targets) > len(set(path_targets))

    assert saw_merged_target


@pytest.mark.parametrize(
    ("two_q", "target_m"),
    [(6, 0.0), (6, 1.0), (5, -0.5)],
)
def test_local_l2_matches_tiny_exact_matrix_for_complex_amplitudes(
    two_q: int,
    target_m: float,
) -> None:
    basis = fixed_m_basis(3, two_q, target_m)
    matrix = l_squared_matrix(basis, two_q=two_q, target_m=target_m)
    rng = np.random.default_rng(848 + round(2 * target_m))
    values = rng.normal(size=len(basis)) + 1j * rng.normal(size=len(basis))
    values += 0.7 + 0.3j
    logpsi = _logpsi_from_basis(basis, values)
    expected = matrix @ values

    for index, state in enumerate(basis):
        assert local_l2(
            state,
            two_q=two_q,
            target_m=target_m,
            logpsi=logpsi,
        ) == pytest.approx(expected[index] / values[index], abs=1.0e-12)


@pytest.mark.parametrize(
    "value",
    [
        complex(-math.inf, 0.25),
        complex(math.inf, 0.0),
        complex(math.nan, 0.0),
        complex(0.0, math.inf),
        complex(0.0, math.nan),
    ],
)
def test_local_estimator_rejects_zero_or_nonfinite_sampled_logpsi(
    value: complex,
) -> None:
    with pytest.raises(ValueError, match="sampled logpsi"):
        local_from_log_neighbors(1, {1: 2.0}, lambda _state: value)


def test_local_estimator_skips_exact_zero_neighbor_logpsi() -> None:
    log_values = {
        1: complex(0.0, 0.5),
        2: complex(-math.inf, 123.0),
        3: complex(math.log(2.0), 0.5),
    }

    observed = local_from_log_neighbors(
        1,
        {2: 1.0e308, 3: 0.25},
        log_values.__getitem__,
    )

    assert observed == pytest.approx(0.5)


@pytest.mark.parametrize(
    "value",
    [
        complex(math.inf, 0.0),
        complex(math.nan, 0.0),
        complex(0.0, math.inf),
        complex(-math.inf, math.inf),
    ],
)
def test_local_estimator_rejects_other_nonfinite_neighbor_logpsi(
    value: complex,
) -> None:
    log_values = {1: 0.0j, 2: value}

    with pytest.raises(ValueError, match="neighbor logpsi"):
        local_from_log_neighbors(1, {2: 1.0}, log_values.__getitem__)


def test_local_estimator_skips_zero_coefficient_before_logpsi_call() -> None:
    calls: Counter[int] = Counter()

    def logpsi(state: int) -> complex:
        calls[state] += 1
        if state == 2:
            raise AssertionError("zero coefficient evaluated logpsi")
        return 0.0j

    assert local_from_log_neighbors(1, {2: 0.0, 3: 2.0}, logpsi) == 2.0
    assert calls == Counter({1: 1, 3: 1})


@pytest.mark.parametrize("real_shift", [-1000.0, 0.0, 1000.0])
@pytest.mark.parametrize("phase_shift", [0.0, 19.75])
def test_local_estimator_is_invariant_under_global_logpsi_shifts(
    real_shift: float,
    phase_shift: float,
) -> None:
    basis = (1, 2)
    neighbors = {1: 2.0 - 0.5j, 2: -0.25 + 0.75j}
    values = np.array([1.0 + 0.5j, -0.4 + 0.8j])
    expected = local_from_log_neighbors(
        1,
        neighbors,
        _logpsi_from_basis(basis, values),
    )

    observed = local_from_log_neighbors(
        1,
        neighbors,
        _logpsi_from_basis(
            basis,
            values,
            real_shift=real_shift,
            phase_shift=phase_shift,
        ),
    )

    assert math.isfinite(observed.real)
    assert math.isfinite(observed.imag)
    assert observed == pytest.approx(expected, rel=2.0e-14, abs=2.0e-14)


def test_local_estimator_is_order_invariant_for_true_near_maximum_overflow() -> None:
    maximum = np.finfo(np.float64).max
    limit = math.log(maximum)
    log_values = {
        1: 0.0j,
        2: complex(limit, 0.0),
        3: complex(limit - math.log(1.0e300), 0.0),
    }
    term_a = (2, 1.0)
    term_b = (3, 1.0e300j)

    for order in ((term_a, term_b), (term_b, term_a)):
        with pytest.raises(OverflowError, match="outside complex128 range"):
            local_from_log_neighbors(
                1,
                dict(order),
                log_values.__getitem__,
            )


def test_local_estimator_is_order_invariant_at_finite_near_maximum() -> None:
    maximum = np.finfo(np.float64).max
    limit = math.log(maximum)
    finite_imaginary_logabs = math.nextafter(
        limit - math.log(1.0e300),
        -math.inf,
    )
    log_values = {
        1: 0.0j,
        2: complex(limit, 0.0),
        3: complex(finite_imaginary_logabs, 0.0),
    }
    term_a = (2, 1.0)
    term_b = (3, 1.0e300j)
    observed = [
        local_from_log_neighbors(1, dict(order), log_values.__getitem__)
        for order in ((term_a, term_b), (term_b, term_a))
    ]

    assert all(math.isfinite(value.real) for value in observed)
    assert all(math.isfinite(value.imag) for value in observed)
    assert observed[0].real == 1.7976931348622732e308
    assert observed[0].imag == 1.7976931348623095e308
    assert observed[1] == observed[0]


def test_local_estimator_saturates_unrepresentable_negative_log_difference() -> None:
    log_values = {
        1: complex(1.0e308, 0.0),
        2: complex(1.0e308, 0.0),
        3: complex(-1.0e308, 0.0),
    }

    observed = local_from_log_neighbors(
        1,
        {2: 1.0, 3: 1.0},
        log_values.__getitem__,
    )

    assert observed == pytest.approx(1.0)


def test_local_estimator_preserves_binary64_coefficient_ulp_residual() -> None:
    x = 1.0e300
    y = math.nextafter(x, math.inf)
    expected = complex(math.fsum((x, -y)))
    log_values = {1: 0.0j, 2: 0.0j, 3: 0.0j}

    for order in (((2, x), (3, -y)), ((3, -y), (2, x))):
        observed = local_from_log_neighbors(
            1,
            dict(order),
            log_values.__getitem__,
        )

        assert observed == expected


@pytest.mark.parametrize(
    "coefficient",
    [
        float(np.finfo(np.float64).max),
        math.ldexp(1.0, -1074),
    ],
)
def test_local_estimator_preserves_binary64_endpoint_at_unit_factor(
    coefficient: float,
) -> None:
    assert local_from_log_neighbors(
        1,
        {2: coefficient},
        lambda _state: 0.0j,
    ) == complex(coefficient)


def _dyadic_rounding_cases() -> list[tuple[operators._Dyadic, float]]:
    minimum = math.ldexp(1.0, -1074)
    normal = math.ldexp(1.0, -901)
    normal_next = math.nextafter(normal, math.inf)
    maximum = float(np.finfo(np.float64).max)
    halfway_even = operators._dyadic_add(
        operators._dyadic_from_float(normal),
        operators._normalized_dyadic(1, -954),
    )
    halfway_odd = operators._dyadic_add(
        operators._dyadic_from_float(normal_next),
        operators._normalized_dyadic(1, -954),
    )
    overflow_halfway = operators._dyadic_add(
        operators._dyadic_from_float(maximum),
        operators._normalized_dyadic(1, 970),
    )
    return [
        (operators._normalized_dyadic(3, -1), 1.5),
        (operators._normalized_dyadic(1, -1074), minimum),
        (operators._normalized_dyadic(1, -1075), 0.0),
        (operators._normalized_dyadic(-1, -1076), -0.0),
        (operators._normalized_dyadic(3, -1076), minimum),
        (halfway_even, normal),
        (halfway_odd, math.nextafter(normal_next, math.inf)),
        (operators._dyadic_from_float(maximum), maximum),
        (overflow_halfway, math.inf),
    ]


@pytest.mark.parametrize(("value", "expected"), _dyadic_rounding_cases())
def test_exact_dyadic_to_binary64_rounds_nearest_even(
    value: operators._Dyadic,
    expected: float,
) -> None:
    observed = operators._dyadic_to_binary64(value)

    assert _float_hex(observed) == _float_hex(expected)


def test_local_estimator_does_not_round_rotated_subnormal_anchor_before_scale() -> None:
    minimum = math.ldexp(1.0, -1074)
    log_values = {
        1: complex(-700.0, 0.0),
        2: complex(0.0, math.acos(0.75)),
    }

    observed = local_from_log_neighbors(
        1,
        {2: minimum},
        log_values.__getitem__,
    )

    assert observed == complex(
        3.758229113666584e-20,
        3.314446534921493e-20,
    )


def test_local_estimator_certifies_ordinary_row_rounding_under_all_orders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_logabs = 1.3735516793873876
    terms = (
        (2, 3.4428098013331905),
        (3, 6.530397713504417),
        (4, -5.208222393324844),
        (5, -4.376072469198897),
    )
    log_values = {
        1: complex(source_logabs, 0.0),
        2: complex(-0.47673852159895347, 0.0),
        3: complex(-0.8514257707488002, 0.0),
        4: complex(-1.2559283904236707, 0.0),
        5: complex(0.06587580241150182, 0.0),
    }
    expected_bits = "bfd3faafc743ed09"

    for order in permutations(terms):
        observed = local_from_log_neighbors(
            1,
            dict(order),
            log_values.__getitem__,
        )

        assert _float_hex(observed.real) == expected_bits

    monkeypatch.setattr(
        operators,
        "_certify_fast_components",
        lambda *_args: None,
    )
    fallback = local_from_log_neighbors(
        1,
        dict(terms),
        log_values.__getitem__,
    )
    assert _float_hex(fallback.real) == expected_bits


def test_fast_roundoff_multiplier_expands_with_operation_count() -> None:
    small = operators._fast_roundoff_multiplier(20)
    large = operators._fast_roundoff_multiplier(147)

    assert small is not None
    assert large is not None
    assert large > small
    with localcontext() as context:
        context.prec = 80
        unit_roundoff = Decimal(5).scaleb(
            -operators._FAST_CERTIFIER_PRECISION
        )
        accumulated = Decimal(147) * unit_roundoff
        gamma = accumulated / (Decimal(1) - accumulated)
        required = gamma / (Decimal(1) - gamma)
    assert large >= required


def test_local_estimator_falls_back_when_operation_bound_crosses_rn_cell(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    neighbors: dict[int, complex] = {}
    log_values = {1: 0.0j}
    target = 2
    for index in range(32):
        lower_logabs = 2.0 + index * 0.01
        upper_logabs = math.nextafter(lower_logabs, math.inf)
        neighbors[target] = complex(1.0, 0.5)
        log_values[target] = complex(lower_logabs, 0.0)
        target += 1
        neighbors[target] = complex(-1.0, -0.5)
        log_values[target] = complex(upper_logabs, 0.0)
        target += 1

    base = 0.9973454279020186
    neighbors[target] = complex(base, base * 0.5)
    log_values[target] = 0.0j
    target += 1
    tuner = math.ldexp(1.0, -10)
    neighbors[target] = complex(tuner, tuner * 0.5)
    log_values[target] = complex(0.9999999999994481, 0.0)

    assert len(neighbors) == 66
    expected = _decimal_row_oracle(1, neighbors, log_values)
    absolute_real_sum = math.fsum(
        abs(coefficient.real) * math.exp(log_values[state].real)
        for state, coefficient in neighbors.items()
    )
    assert absolute_real_sum > 500.0 * abs(expected.real)

    fallback_calls: Counter[str] = Counter()
    fallback = operators._fallback_component

    def fallback_spy(
        terms: tuple[operators._DyadicLogTerm, ...],
        source_logabs: float,
    ) -> float:
        fallback_calls["components"] += 1
        return fallback(terms, source_logabs)

    monkeypatch.setattr(operators, "_fallback_component", fallback_spy)
    observed = local_from_log_neighbors(
        1,
        neighbors,
        log_values.__getitem__,
    )

    assert _float_hex(observed.real) == _float_hex(expected.real)
    assert _float_hex(observed.imag) == _float_hex(expected.imag)
    assert fallback_calls == Counter(components=2)


def test_local_estimator_falls_back_across_signed_zero_rounding_cells(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    minimum = math.ldexp(1.0, -1074)
    neighbors = {2: minimum, 3: -minimum}
    log_values = {
        1: 0.0j,
        2: 0.0j,
        3: complex(minimum, 0.0),
    }
    expected = _decimal_row_oracle(1, neighbors, log_values)
    assert _float_hex(expected.real) == "8000000000000000"

    fallback_calls: Counter[str] = Counter()
    fallback = operators._fallback_component

    def fallback_spy(
        terms: tuple[operators._DyadicLogTerm, ...],
        source_logabs: float,
    ) -> float:
        fallback_calls["components"] += 1
        return fallback(terms, source_logabs)

    monkeypatch.setattr(operators, "_fallback_component", fallback_spy)
    observed = local_from_log_neighbors(
        1,
        neighbors,
        log_values.__getitem__,
    )

    assert (
        _float_hex(observed.real),
        fallback_calls,
    ) == (
        "8000000000000000",
        Counter(components=1),
    )


@pytest.mark.parametrize(
    ("ambient_rounding", "coefficient_sign"),
    [(ROUND_FLOOR, 1.0), (ROUND_CEILING, -1.0)],
)
def test_fast_certifier_path_is_ambient_rounding_independent(
    ambient_rounding: str,
    coefficient_sign: float,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_logabs = 2.9586827049504487
    neighbors = {
        2: coefficient_sign * 2.6389857554844767,
        3: coefficient_sign * 6.031655559834185,
        4: coefficient_sign * -3.1429711648954353,
        5: coefficient_sign * -5.809692494403778,
        6: coefficient_sign * 2.7885636787746346,
        7: coefficient_sign * 3.661802348908374,
        8: coefficient_sign * -2.0058140673197453,
        9: coefficient_sign * -3.6936025018572565,
    }
    log_values = {
        1: complex(source_logabs, 0.0),
        2: complex(-0.03676691738333204, 0.0),
        3: complex(-0.11991049957751487, 0.0),
        4: complex(-0.07739889502763386, 0.0),
        5: complex(-0.5549432476680991, 0.0),
        6: complex(2.256192270806035, 0.0),
        7: complex(0.860089900166435, 0.0),
        8: complex(2.9347831332270893, 0.0),
        9: complex(-1.8076460319581793, 0.0),
    }
    with localcontext() as baseline_context:
        baseline_context.rounding = ROUND_HALF_EVEN
        baseline = local_from_log_neighbors(
            1,
            neighbors,
            log_values.__getitem__,
        )

    fallback_calls: Counter[str] = Counter()
    fallback = operators._fallback_component

    def fallback_spy(
        terms: tuple[operators._DyadicLogTerm, ...],
        received_source_logabs: float,
    ) -> float:
        fallback_calls["components"] += 1
        return fallback(terms, received_source_logabs)

    monkeypatch.setattr(operators, "_fallback_component", fallback_spy)
    with localcontext() as ambient_context:
        ambient_context.rounding = ambient_rounding
        observed = local_from_log_neighbors(
            1,
            neighbors,
            log_values.__getitem__,
        )

    assert (
        _float_hex(observed.real),
        _float_hex(observed.imag),
    ) == (
        _float_hex(baseline.real),
        _float_hex(baseline.imag),
    )
    assert fallback_calls == Counter()


def test_local_estimator_terminates_exact_dyadic_halfway_tie(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    even = math.ldexp(1.0, -901)
    halfway = math.ldexp(1.0, -954)
    terms = ((2, even), (3, halfway))
    monkeypatch.setattr(operators, "_FALLBACK_MAX_PRECISION", 1600)

    for order in permutations(terms):
        observed = local_from_log_neighbors(
            1,
            dict(order),
            lambda _state: 0.0j,
        )

        assert _float_hex(observed.real) == _float_hex(even)


def test_local_estimator_recovers_tiny_component_after_exact_row_cancellation() -> None:
    maximum = float(np.finfo(np.float64).max)
    minimum = math.ldexp(1.0, -1074)
    terms = ((2, complex(maximum, minimum)), (3, complex(-maximum)))
    log_values = {1: 0.0j, 2: 0.0j, 3: 0.0j}

    for order in permutations(terms):
        observed = local_from_log_neighbors(
            1,
            dict(order),
            log_values.__getitem__,
        )

        assert observed == complex(0.0, minimum)


def test_local_estimator_combines_ulp_residual_with_lower_log_band() -> None:
    x = 1.0e300
    y = math.nextafter(x, math.inf)
    residual = abs(math.fsum((x, -y)))
    terms = ((2, x), (3, -y), (4, residual))
    log_values = {
        1: 0.0j,
        2: 0.0j,
        3: 0.0j,
        4: complex(-math.log(2.0), 0.0),
    }
    expected = _decimal_row_oracle(1, dict(terms), log_values)

    for order in permutations(terms):
        observed = local_from_log_neighbors(
            1,
            dict(order),
            log_values.__getitem__,
        )

        assert observed == expected


def test_local_estimator_accumulates_multiple_sub_half_ulp_lower_terms() -> None:
    lower_logabs = -54.0 * math.log(2.0)
    terms = ((2, 1.0), (3, 1.0), (4, 1.0), (5, 1.0))
    log_values = {
        1: 0.0j,
        2: 0.0j,
        3: complex(math.nextafter(lower_logabs, -math.inf), 0.0),
        4: complex(lower_logabs, 0.0),
        5: complex(math.nextafter(lower_logabs, math.inf), 0.0),
    }
    expected = _decimal_row_oracle(1, dict(terms), log_values)

    assert expected == complex(math.nextafter(1.0, math.inf))
    for order in permutations(terms):
        observed = local_from_log_neighbors(
            1,
            dict(order),
            log_values.__getitem__,
        )

        assert observed == expected


def test_local_estimator_descends_after_signed_dominant_cancellation() -> None:
    coefficients = {2: 1.0, 3: -1.0, 4: 1.0}
    log_values = {
        1: 0.0j,
        2: complex(1.0e308, 0.0),
        3: complex(1.0e308, 0.0),
        4: 0.0j,
    }

    for order in permutations(coefficients):
        neighbors = {state: coefficients[state] for state in order}
        observed = local_from_log_neighbors(1, neighbors, log_values.__getitem__)

        assert observed == 1.0 + 0.0j


def test_local_estimator_descends_through_orthogonal_cancellation_levels() -> None:
    coefficients = {
        2: 1.0,
        3: -1.0,
        4: 1.0j,
        5: -1.0j,
        6: 2.0 + 3.0j,
    }
    log_values = {
        1: 0.0j,
        2: complex(1.0e308, 0.0),
        3: complex(1.0e308, 0.0),
        4: complex(5.0e307, 0.0),
        5: complex(5.0e307, 0.0),
        6: 0.0j,
    }

    for order in permutations(coefficients):
        neighbors = {state: coefficients[state] for state in order}
        observed = local_from_log_neighbors(1, neighbors, log_values.__getitem__)

        assert observed == pytest.approx(2.0 + 3.0j, rel=1.0e-15)


@pytest.mark.parametrize(
    ("coefficient", "target_logabs", "expected"),
    [
        (1.0e-300, 1400.5582407915977, 1.7976931348622307e308),
        (
            math.ldexp(1.0, -1074),
            1454.2227848147652,
            1.7976931348621938e308,
        ),
    ],
)
def test_local_estimator_restores_finite_near_maximum_component(
    coefficient: float,
    target_logabs: float,
    expected: float,
) -> None:
    log_values = {1: 0.0j, 2: complex(target_logabs, 0.0)}

    observed = local_from_log_neighbors(
        1,
        {2: coefficient},
        log_values.__getitem__,
    )

    assert observed == complex(expected)


def test_local_estimator_rejects_true_near_maximum_overflow() -> None:
    log_values = {1: 0.0j, 2: complex(19.00718499517029, 0.0)}

    with pytest.raises(OverflowError, match="outside complex128 range"):
        local_from_log_neighbors(
            1,
            {2: 1.0e300},
            log_values.__getitem__,
        )


def test_local_estimator_rounds_minimum_subnormal_halfway_boundary() -> None:
    minimum = math.ldexp(1.0, -1074)
    threshold = -math.log(2.0)

    below = local_from_log_neighbors(
        1,
        {2: minimum},
        {1: 0.0j, 2: complex(math.nextafter(threshold, -math.inf), 0.0)}.__getitem__,
    )
    above = local_from_log_neighbors(
        1,
        {2: minimum},
        {1: 0.0j, 2: complex(math.nextafter(threshold, math.inf), 0.0)}.__getitem__,
    )

    assert below == 0.0j
    assert above == complex(minimum)


def test_local_estimator_preserves_maximum_complex_components() -> None:
    maximum = float(np.finfo(np.float64).max)
    coefficient = complex(maximum, maximum)

    observed = local_from_log_neighbors(
        1,
        {2: coefficient},
        lambda _state: 0.0j,
    )

    assert observed == coefficient


def test_local_estimator_rejects_true_complex_component_overflow() -> None:
    maximum = float(np.finfo(np.float64).max)
    coefficient = complex(maximum, maximum)
    log_values = {1: 0.0j, 2: complex(math.ulp(1.0), 0.0)}

    with pytest.raises(OverflowError, match="outside complex128 range"):
        local_from_log_neighbors(
            1,
            {2: coefficient},
            log_values.__getitem__,
        )


def test_local_estimator_handles_huge_log_difference_without_direct_exp() -> None:
    safe_logs = {
        1: complex(1.0e308, 0.0),
        2: complex(-1.0e308, 0.0),
    }
    overflow_logs = {
        1: complex(-1.0e308, 0.0),
        2: complex(1.0e308, 0.0),
    }

    assert local_from_log_neighbors(
        1,
        {2: 1.0},
        safe_logs.__getitem__,
    ) == 0.0j
    with pytest.raises(OverflowError, match="outside complex128 range"):
        local_from_log_neighbors(
            1,
            {2: 1.0},
            overflow_logs.__getitem__,
        )


def test_local_estimator_preserves_multiply_first_extreme_result() -> None:
    log_values = {
        1: complex(math.log(1.0e-315), 0.0),
        2: complex(math.log(1.0e-315), 0.0),
    }

    observed = local_from_log_neighbors(
        1,
        {2: complex(1.0e-10)},
        log_values.__getitem__,
    )

    assert isinstance(observed, complex)
    assert observed == pytest.approx(complex(1.0e-10), rel=1.0e-14)


def test_local_estimator_preserves_divide_first_extreme_result() -> None:
    log_values = {
        1: complex(math.log(1.0e-315), 0.0),
        2: complex(0.0, 0.0),
    }

    observed = local_from_log_neighbors(
        1,
        {2: complex(1.0e-315)},
        log_values.__getitem__,
    )

    assert isinstance(observed, complex)
    assert observed == pytest.approx(complex(1.0), rel=2.0e-14)


def test_local_estimator_preserves_coefficient_component_dynamic_range() -> None:
    coefficient = complex(
        float(np.finfo(np.float64).max),
        math.ldexp(1.0, -1074),
    )

    assert local_from_log_neighbors(
        1,
        {2: coefficient},
        lambda _state: 0.0j,
    ) == coefficient


@pytest.mark.parametrize(
    "coefficient",
    [complex(math.inf), complex(math.nan), complex(1.0, math.inf)],
)
def test_local_estimator_rejects_nonfinite_coefficient(
    coefficient: complex,
) -> None:
    with pytest.raises(ValueError, match="neighbor coefficient must be finite"):
        local_from_log_neighbors(1, {2: coefficient}, lambda _state: 0.0j)


def test_local_estimator_preserves_complex_phase_across_binary_extremes() -> None:
    coefficient = complex(
        math.ldexp(1.0, -1050),
        math.ldexp(1.0, -1051),
    )
    target = complex(
        math.ldexp(1.0, 1000),
        -math.ldexp(1.0, 999),
    )
    denominator = complex(
        math.ldexp(1.0, -1000),
        math.ldexp(1.0, -1001),
    )
    expected = complex(
        math.ldexp(1.0, 950),
        -math.ldexp(1.0, 949),
    )
    logpsi = _logpsi_from_basis(
        (1, 2),
        np.array([denominator, target], dtype=np.complex128),
    )

    observed = local_from_log_neighbors(
        1,
        {2: coefficient},
        logpsi,
    )

    assert isinstance(observed, complex)
    assert observed == pytest.approx(expected, rel=1.0e-13)


def test_local_estimator_rejects_mathematically_unrepresentable_term() -> None:
    coefficient = complex(math.ldexp(1.0, 1023))
    log_values = {1: 0.0j, 2: complex(math.log(2.0), 0.0)}

    with pytest.raises(OverflowError, match="outside complex128 range"):
        local_from_log_neighbors(1, {2: coefficient}, log_values.__getitem__)


def test_local_estimator_sums_canceling_large_terms_before_final_restore() -> None:
    log_values = {state: 0.0j for state in range(1, 5)}
    neighbors = {
        2: complex(1.0e308),
        3: complex(1.0e308),
        4: complex(-1.0e308),
    }

    observed = local_from_log_neighbors(1, neighbors, log_values.__getitem__)

    assert observed == complex(1.0e308)


def test_local_estimator_rejects_unrepresentable_final_row_sum() -> None:
    log_values = {state: 0.0j for state in range(1, 4)}
    neighbors = {2: complex(1.0e308), 3: complex(1.0e308)}

    with pytest.raises(OverflowError, match="outside complex128 range"):
        local_from_log_neighbors(1, neighbors, log_values.__getitem__)


def test_local_estimator_allows_out_of_range_terms_to_cancel() -> None:
    scale = complex(math.ldexp(1.0, 1023))
    log_values = {
        1: 0.0j,
        2: complex(math.log(2.0), 0.0),
        3: complex(math.log(2.0), 0.0),
        4: 0.0j,
    }
    neighbors = {2: scale, 3: -scale, 4: complex(1.0)}

    observed = local_from_log_neighbors(1, neighbors, log_values.__getitem__)

    assert observed == pytest.approx(complex(1.0), rel=5.0e-14)


def test_local_estimator_returns_zero_for_exactly_canceling_row() -> None:
    log_values = {state: 0.0j for state in range(1, 4)}
    neighbors = {2: complex(1.0e308), 3: complex(-1.0e308)}

    observed = local_from_log_neighbors(1, neighbors, log_values.__getitem__)

    assert observed == 0.0j


def test_local_estimator_matches_wide_exponent_decimal_oracle_under_shuffle() -> None:
    rng = random.Random(848)
    for case in range(6):
        source_logabs = rng.uniform(-200.0, 200.0)
        source_phase = rng.uniform(-20.0, 20.0)
        log_values = {1: complex(source_logabs, source_phase)}
        terms: list[tuple[int, complex]] = []
        for offset in range(8):
            state = offset + 2
            coefficient = complex(
                math.ldexp(rng.uniform(-1.0, 1.0), rng.randint(-300, 300)),
                math.ldexp(rng.uniform(-1.0, 1.0), rng.randint(-300, 300)),
            )
            target_logabs = source_logabs + rng.uniform(-350.0, 350.0)
            target_phase = rng.uniform(-20.0, 20.0)
            log_values[state] = complex(target_logabs, target_phase)
            terms.append((state, coefficient))

        expected = _decimal_row_oracle(1, dict(terms), log_values)
        observed: list[complex] = []
        for shuffle in range(3):
            shuffled = list(terms)
            random.Random(10_000 * case + shuffle).shuffle(shuffled)
            observed.append(
                local_from_log_neighbors(
                    1,
                    dict(shuffled),
                    log_values.__getitem__,
                )
            )

        assert all(value == observed[0] for value in observed)
        assert observed[0] == pytest.approx(expected, rel=5.0e-13, abs=1.0e-300)


def test_prepared_pair_operator_rejects_non_hermitian_20_6_input() -> None:
    pair_matrix = np.array(
        [[0.0, 1.0 + 2.0j], [20.6 + 0.0j, 0.0]],
        dtype=np.complex128,
    )

    with pytest.raises(ValueError, match="pair_matrix must be Hermitian"):
        PreparedPairOperator.build(((0, 1), (2, 3)), pair_matrix, two_q=3)


def test_prepared_pair_operator_rejects_extreme_non_hermitian_input() -> None:
    maximum = np.finfo(np.float64).max
    pair_matrix = np.array(
        [[0.0, complex(maximum, maximum)], [0.0, 0.0]],
        dtype=np.complex128,
    )

    with pytest.raises(ValueError, match="pair_matrix must be Hermitian"):
        PreparedPairOperator.build(((0, 1), (2, 3)), pair_matrix, two_q=3)


def test_prepared_pair_operator_preserves_coefficient_component_dynamic_range() -> None:
    coefficient = complex(
        float(np.finfo(np.float64).max),
        math.ldexp(1.0, -1074),
    )
    pair_matrix = np.array(
        [[0.0, coefficient], [coefficient.conjugate(), 0.0]],
        dtype=np.complex128,
    )

    prepared = PreparedPairOperator.build(
        ((0, 1), (2, 3)),
        pair_matrix,
        two_q=3,
    )

    assert prepared.matrix[0, 1] == coefficient
    assert prepared.matrix[1, 0] == coefficient.conjugate()


def test_prepared_pair_operator_rejects_direct_construction() -> None:
    with pytest.raises(TypeError, match="must be created with build"):
        PreparedPairOperator()


def test_prepared_pair_operator_uses_identity_equality() -> None:
    first = PreparedPairOperator.build(((0, 1),), np.eye(1), two_q=1)
    second = PreparedPairOperator.build(((0, 1),), np.eye(1), two_q=1)

    assert first == first
    assert first != second


@pytest.mark.parametrize(
    ("pairs", "two_q", "error", "message"),
    [
        (((1, 0),), 1, ValueError, "canonical order"),
        (((0, 0),), 1, ValueError, "canonical order"),
        (((0, 1), (0, 1)), 1, ValueError, "unique"),
        (((0, 2),), 1, ValueError, "must be in"),
        (((False, 1),), 1, TypeError, "must be an integer"),
        (((0, 1),), True, TypeError, "two_q must be an integer"),
    ],
)
def test_prepared_pair_operator_requires_canonical_unique_integer_pairs(
    pairs,
    two_q,
    error: type[Exception],
    message: str,
) -> None:
    pair_count = len(pairs)
    with pytest.raises(error, match=message):
        PreparedPairOperator.build(
            pairs,
            np.eye(pair_count, dtype=np.complex128),
            two_q,
        )


def test_prepared_pair_operator_copies_and_freezes_inputs() -> None:
    source_pairs = [[0, 1], [2, 3]]
    source_matrix = np.array(
        [[2.0, 1.0 + 2.0j], [1.0 - 2.0j, 3.0]],
        dtype=np.complex128,
    )
    expected_matrix = source_matrix.copy()

    operator = PreparedPairOperator.build(source_pairs, source_matrix, two_q=3)
    source_pairs[0][0] = 1
    source_matrix[:] = 99.0

    assert operator.two_q == 3
    assert operator.pairs == ((0, 1), (2, 3))
    np.testing.assert_array_equal(operator.matrix, expected_matrix)
    assert not operator.matrix.flags.writeable
    assert isinstance(operator.nonzero_by_column, tuple)
    assert all(isinstance(entries, tuple) for entries in operator.nonzero_by_column)
    assert dict(operator.source_column_by_pair) == {(0, 1): 0, (2, 3): 1}
    with pytest.raises(ValueError, match="read-only"):
        operator.matrix[0, 0] = 0.0
    with pytest.raises(TypeError):
        operator.source_column_by_pair[(0, 1)] = 7


def test_prepared_pair_operator_is_reused_without_quadratic_rescan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    two_q = 3
    pairs = tuple((a, b) for a in range(4) for b in range(a + 1, 4))
    pair_matrix = np.eye(len(pairs), dtype=np.complex128)
    operator = PreparedPairOperator.build(pairs, pair_matrix, two_q)
    cached_nonzeros = operator.nonzero_by_column

    def unexpected_scan(*_args, **_kwargs):
        raise AssertionError("hot path repeated the pair-matrix scan")

    monkeypatch.setattr(operators.np, "flatnonzero", unexpected_scan)

    for state in full_basis(2, two_q):
        assert two_body_neighbors(state, operator=operator) == {state: 1.0}
        assert local_energy(
            state,
            operator=operator,
            logpsi=lambda _state: 0.0j,
        ) == pytest.approx(1.0)
    assert operator.nonzero_by_column is cached_nonzeros


def test_operator_estimators_reject_bad_shapes_and_configuration_inputs() -> None:
    pairs = ((0, 1),)
    logpsi = lambda _state: 0.0j

    with pytest.raises(ValueError, match="pair_matrix must have shape"):
        PreparedPairOperator.build(pairs, np.zeros((1, 2)), two_q=1)
    with pytest.raises(ValueError, match="outside the orbital range"):
        ladder_neighbors(1 << 3, 1, direction=1)
    with pytest.raises(ValueError, match="direction must be -1 or 1"):
        ladder_neighbors(1, 1, direction=0)
    with pytest.raises(TypeError, match="target_m must be a finite integer or half-integer"):
        local_l2(1, two_q=1, target_m=True, logpsi=logpsi)
    with pytest.raises(ValueError, match="target_m must be a finite integer or half-integer"):
        local_l2(1, two_q=1, target_m=0.25, logpsi=logpsi)
    with pytest.raises(ValueError, match="target_m must be a finite integer or half-integer"):
        local_l2(1, two_q=1, target_m=np.inf, logpsi=logpsi)
