from __future__ import annotations

import pytest

from src.diagonalization import EDEngine
from src.dynamics import check_time_step_convergence, evolve_pump_cycle
from src.model import ModelParameters, RiceMeleHubbardModel
from src.topology import compute_adiabatic_charge


def make_engine() -> EDEngine:
    parameters = ModelParameters(L=4, N_up=2, N_down=2)
    return EDEngine(RiceMeleHubbardModel(parameters))


def test_realtime_charge_matches_production_reference_and_preserves_norm():
    result = evolve_pump_cycle(make_engine(), period=10.0, n_steps=400)

    assert result.charge == pytest.approx(1.9872303616718463, abs=1e-9)
    assert result.maximum_norm_error < 1e-12
    assert result.norms[-1] == pytest.approx(1.0, abs=1e-12)
    assert result.final_ground_state_fidelity == pytest.approx(
        0.9149083983119761,
        abs=1e-10,
    )


def test_long_period_charge_is_closer_to_adiabatic_winding():
    engine = make_engine()
    adiabatic = compute_adiabatic_charge(engine, n_phi=40)
    short = evolve_pump_cycle(engine, period=2.0, n_steps=200)
    long = evolve_pump_cycle(engine, period=10.0, n_steps=400)

    assert abs(long.charge - adiabatic.charge) < 0.05
    assert abs(long.charge - adiabatic.charge) < abs(
        short.charge - adiabatic.charge
    )


def test_time_step_refinement_and_path_reversal_are_consistent():
    engine = make_engine()
    convergence = check_time_step_convergence(
        engine,
        period=4.0,
        steps=(100, 200),
    )
    reverse = evolve_pump_cycle(engine, period=4.0, n_steps=200, direction=-1)

    assert convergence.charge_difference < 5e-3
    assert reverse.charge == pytest.approx(-convergence.fine.charge, abs=1e-10)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"period": 0.0, "n_steps": 20},
        {"period": 1.0, "n_steps": 1},
        {"period": 1.0, "n_steps": 20, "direction": 0},
    ],
)
def test_realtime_evolution_rejects_invalid_controls(kwargs):
    with pytest.raises(ValueError):
        evolve_pump_cycle(make_engine(), **kwargs)
