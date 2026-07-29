from __future__ import annotations

import cmath
import math
from collections.abc import Callable, Mapping

import numpy as np
import pytest

import scalable_v1.routes.occupation_autoregressive.tower as tower_module
from scalable_v1.routes.occupation_autoregressive.constraints import (
    FeasibilityTable,
)
from scalable_v1.routes.occupation_autoregressive.model import AutoregressiveNQS
from scalable_v1.routes.occupation_autoregressive.operators import local_l2
from scalable_v1.routes.occupation_autoregressive.tower import (
    LadderComponent,
    LadderTower,
    spin2_ladder_coefficient,
)


N_ELECTRONS = 2
TWO_Q = 3
M0_LEFT = (1 << 0) | (1 << 3)
M0_RIGHT = (1 << 1) | (1 << 2)
M_PLUS_ONE = (1 << 1) | (1 << 3)
M_MINUS_ONE = (1 << 0) | (1 << 2)


def _logpsi_from_amplitudes(
    amplitudes: Mapping[int, complex],
) -> Callable[[int], complex]:
    table = {int(state): complex(value) for state, value in amplitudes.items()}

    def logpsi(state: int) -> complex:
        value = table[state]
        if value == 0.0:
            return complex(-math.inf, 0.0)
        return complex(math.log(abs(value)), math.atan2(value.imag, value.real))

    return logpsi


def _zero_score(width: int = 3) -> Callable[[int], np.ndarray]:
    def score(_state: int) -> np.ndarray:
        return np.zeros(width, dtype=np.complex128)

    return score


def _exact_l2_tower() -> LadderTower:
    coefficient = 1.0 / math.sqrt(2.0)
    return LadderTower.from_m0(
        logpsi=_logpsi_from_amplitudes(
            {M0_LEFT: coefficient, M0_RIGHT: coefficient}
        ),
        log_score=_zero_score(),
        n_electrons=N_ELECTRONS,
        two_q=TWO_Q,
        l=2,
    )


def _amplitude(component: LadderComponent, state: int) -> complex:
    value = component.logpsi(state)
    if value.real == -math.inf:
        return 0.0j
    return cmath.exp(value)


def _fixed_m_support(m: int) -> tuple[int, ...]:
    return FeasibilityTable.build(
        n_electrons=N_ELECTRONS,
        two_q=TWO_Q,
        target_m2=2 * m,
    ).enumerate_support()


def test_exact_normalized_l2_m0_fixture_is_preserved_in_five_state_tower(
) -> None:
    tower = _exact_l2_tower()
    expected = 1.0 / math.sqrt(2.0)

    assert tuple(tower) == (-2, -1, 0, 1, 2)
    assert tower[0].m == 0
    assert _amplitude(tower[0], M0_LEFT) == pytest.approx(expected)
    assert _amplitude(tower[0], M0_RIGHT) == pytest.approx(expected)


def test_each_exact_spin2_component_has_unit_norm_and_local_l2_six() -> None:
    tower = _exact_l2_tower()

    for m, component in tower.items():
        support = _fixed_m_support(m)
        amplitudes = {
            state: _amplitude(component, state) for state in support
        }
        assert sum(abs(value) ** 2 for value in amplitudes.values()) == (
            pytest.approx(1.0, abs=1.0e-14)
        )
        assert all(value != 0.0 for value in amplitudes.values())
        residuals = [
            abs(
                local_l2(
                    state,
                    two_q=TWO_Q,
                    target_m=float(m),
                    logpsi=component.logpsi,
                )
                - 6.0
            )
            for state in support
        ]
        assert max(residuals, default=0.0) < 1.0e-12


@pytest.mark.parametrize(
    ("source_m", "direction", "expected"),
    [
        (-2, 1, 2.0),
        (-1, 1, math.sqrt(6.0)),
        (0, 1, math.sqrt(6.0)),
        (1, 1, 2.0),
        (-1, -1, 2.0),
        (0, -1, math.sqrt(6.0)),
        (1, -1, math.sqrt(6.0)),
        (2, -1, 2.0),
    ],
)
def test_spin2_ladder_coefficients_are_analytic_and_orientation_specific(
    source_m: int,
    direction: int,
    expected: float,
) -> None:
    assert spin2_ladder_coefficient(source_m, direction) == pytest.approx(
        expected,
        abs=0.0,
    )


def test_derived_components_use_inverse_sparse_ladder_neighbors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[int, int]] = []
    original = tower_module.ladder_neighbors

    def recording_neighbors(
        state: int,
        two_q: int,
        direction: int,
    ) -> dict[int, complex]:
        calls.append((state, direction))
        return original(state, two_q, direction)

    monkeypatch.setattr(tower_module, "ladder_neighbors", recording_neighbors)
    tower = _exact_l2_tower()

    assert _amplitude(tower[1], M_PLUS_ONE) != 0.0
    assert _amplitude(tower[-1], M_MINUS_ONE) != 0.0
    assert calls == [(M_PLUS_ONE, -1), (M_MINUS_ONE, 1)]


def test_exact_cancellation_remains_negative_infinity_in_logpsi() -> None:
    coefficient = 1.0 / math.sqrt(2.0)
    tower = LadderTower.from_m0(
        logpsi=_logpsi_from_amplitudes(
            {M0_LEFT: coefficient, M0_RIGHT: -coefficient}
        ),
        log_score=_zero_score(),
        n_electrons=N_ELECTRONS,
        two_q=TWO_Q,
        l=2,
    )

    observed = tower[1].logpsi(M_PLUS_ONE)

    assert observed.real == -math.inf
    assert math.isfinite(observed.imag)
    with pytest.raises(ValueError, match="score is undefined.*zero amplitude"):
        tower[1].log_score(M_PLUS_ONE)


def test_dominant_cancellation_preserves_finite_lower_log_band_and_score(
) -> None:
    n_electrons = 3
    two_q = 6
    target = (1 << 1) | (1 << 3) | (1 << 6)
    dominant_left = (1 << 0) | (1 << 3) | (1 << 6)
    dominant_right = (1 << 1) | (1 << 3) | (1 << 5)
    lower_band = (1 << 1) | (1 << 2) | (1 << 6)
    inverse = tower_module.ladder_neighbors(target, two_q, direction=-1)

    assert set(inverse) == {dominant_left, lower_band, dominant_right}
    assert inverse[dominant_left] == pytest.approx(math.sqrt(6.0))
    assert inverse[lower_band] == pytest.approx(math.sqrt(12.0))
    assert inverse[dominant_right] == pytest.approx(math.sqrt(6.0))

    dominant_log = -math.log(math.sqrt(6.0))
    lower_log = -1000.0 - math.log(math.sqrt(12.0))
    logs = {
        dominant_left: complex(dominant_log, 0.0),
        dominant_right: complex(dominant_log, math.pi),
        lower_band: complex(lower_log, 0.0),
    }
    expected_score = np.array(
        [1.25 - 0.5j, -0.75 + 0.125j],
        dtype=np.complex128,
    )
    scores = {
        dominant_left: np.zeros(2, dtype=np.complex128),
        dominant_right: np.zeros(2, dtype=np.complex128),
        lower_band: expected_score,
    }
    tower = LadderTower.from_m0(
        logpsi=lambda state: logs[state],
        log_score=lambda state: scores[state],
        n_electrons=n_electrons,
        two_q=two_q,
        l=2,
    )

    observed = tower[1].logpsi(target)

    assert observed.real == pytest.approx(
        -1000.0 - math.log(math.sqrt(6.0)),
        abs=2.0e-13,
    )
    assert math.remainder(observed.imag, 2.0 * math.pi) == pytest.approx(
        0.0,
        abs=2.0e-15,
    )
    np.testing.assert_allclose(
        tower[1].log_score(target),
        expected_score,
        rtol=0.0,
        atol=2.0e-15,
    )


def test_exact_node_is_invariant_under_nonaxial_global_phase() -> None:
    coefficient = 1.0 / math.sqrt(2.0)
    global_phase = cmath.exp(0.371j)
    tower = LadderTower.from_m0(
        logpsi=_logpsi_from_amplitudes(
            {
                M0_LEFT: coefficient * global_phase,
                M0_RIGHT: -coefficient * global_phase,
            }
        ),
        log_score=_zero_score(),
        n_electrons=N_ELECTRONS,
        two_q=TWO_Q,
        l=2,
    )

    observed = tower[1].logpsi(M_PLUS_ONE)

    assert observed.real == -math.inf
    assert math.isfinite(observed.imag)
    with pytest.raises(ValueError, match="score is undefined.*zero amplitude"):
        tower[1].log_score(M_PLUS_ONE)


def test_every_analytic_derived_log_score_parameter_matches_central_difference(
) -> None:
    model = AutoregressiveNQS.initialize(
        n_electrons=N_ELECTRONS,
        two_q=TWO_Q,
        target_m2=0,
        width=2,
        layers=2,
        seed=848,
        max_trainable_parameters=262_144,
    )
    tower = LadderTower.from_m0(
        logpsi=lambda state: model.logpsi(state, "excited"),
        log_score=lambda state: model.log_derivative(state, "excited"),
        n_electrons=N_ELECTRONS,
        two_q=TWO_Q,
        l=2,
    )
    baseline = model.flat_parameters()
    step = 2.0e-6
    cases = tuple(
        (m, _fixed_m_support(m)[0]) for m in (-2, -1, 1, 2)
    )

    try:
        for m, state in cases:
            reference = _amplitude(tower[m], state)
            assert abs(reference) > 1.0e-10
            analytic = tower[m].log_score(state)
            central = np.empty_like(analytic)
            for index in range(baseline.size):
                plus = baseline.copy()
                minus = baseline.copy()
                plus[index] += step
                minus[index] -= step
                model.set_flat_parameters(plus)
                upper = _amplitude(tower[m], state)
                model.set_flat_parameters(minus)
                lower = _amplitude(tower[m], state)
                central[index] = (upper - lower) / (2.0 * step * reference)
            model.set_flat_parameters(baseline)
            np.testing.assert_allclose(
                analytic,
                central,
                rtol=3.0e-5,
                atol=3.0e-6,
            )
    finally:
        model.set_flat_parameters(baseline)


@pytest.mark.parametrize(
    ("state", "message"),
    [
        (True, "state must be an integer"),
        (1 << 4, "outside the orbital range"),
        (1 << 3, "fixed-N"),
        (M0_LEFT, "fixed-N fixed-M"),
    ],
)
def test_component_rejects_invalid_or_wrong_sector_states(
    state: object,
    message: str,
) -> None:
    component = _exact_l2_tower()[1]

    with pytest.raises((TypeError, ValueError), match=message):
        component.logpsi(state)  # type: ignore[arg-type]


def test_tower_rejects_invalid_target_and_ladder_boundaries() -> None:
    tower = _exact_l2_tower()

    with pytest.raises(ValueError, match="target_m must be in.*-2.*2"):
        tower.component(3)
    with pytest.raises(ValueError, match="cannot raise.*M=2"):
        spin2_ladder_coefficient(2, 1)
    with pytest.raises(ValueError, match="cannot lower.*M=-2"):
        spin2_ladder_coefficient(-2, -1)
    with pytest.raises(ValueError, match="direction must be -1 or 1"):
        spin2_ladder_coefficient(0, 0)


@pytest.mark.parametrize(
    ("kwargs", "error", "message"),
    [
        ({"logpsi": None}, TypeError, "logpsi must be callable"),
        ({"log_score": None}, TypeError, "log_score must be callable"),
        ({"n_electrons": True}, TypeError, "n_electrons must be an integer"),
        ({"two_q": 2.5}, TypeError, "two_q must be an integer"),
        ({"l": 3}, ValueError, "l must be 2"),
    ],
)
def test_from_m0_fails_closed_on_invalid_construction_contract(
    kwargs: dict[str, object],
    error: type[Exception],
    message: str,
) -> None:
    arguments: dict[str, object] = {
        "logpsi": _logpsi_from_amplitudes(
            {M0_LEFT: 1.0 / math.sqrt(2.0), M0_RIGHT: 1.0 / math.sqrt(2.0)}
        ),
        "log_score": _zero_score(),
        "n_electrons": N_ELECTRONS,
        "two_q": TWO_Q,
        "l": 2,
    }
    arguments.update(kwargs)

    with pytest.raises(error, match=message):
        LadderTower.from_m0(**arguments)  # type: ignore[arg-type]
