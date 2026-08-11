from __future__ import annotations

from fractions import Fraction

import numpy as np
import pytest

from src.diagonalization import EDEngine
from src.dynamics import evolve_pump_cycle
from src.model import ModelParameters, RiceMeleHubbardModel
from src.topology import (
    compute_adiabatic_charge,
    compute_fhs,
    compute_fixed_twist_adiabatic_charge,
    converge_fixed_twist_adiabatic_charge,
    fixed_twist_charge_from_states,
    polarization_from_states,
    scan_chern,
    verify_gauge_invariance,
    wilson_loop_polarization,
)


def make_engine(**overrides) -> EDEngine:
    values = {"L": 4, "N_up": 2, "N_down": 2}
    values.update(overrides)
    return EDEngine(RiceMeleHubbardModel(ModelParameters(**values)))


def test_fhs_rejects_neighbor_overlap_at_threshold():
    first = np.array([1.0, 0.0], dtype=np.complex128)
    second = np.array([1e-12, np.sqrt(1.0 - 1e-24)], dtype=np.complex128)
    states = np.array([[first, first], [second, second]])
    threshold = abs(np.vdot(first, second))

    with pytest.raises(ValueError, match="overlap"):
        compute_fhs(states, overlap_threshold=threshold)


def test_fhs_is_invariant_under_independent_grid_phases():
    base = np.array([1.0, 0.25j, -0.1], dtype=np.complex128)
    base /= np.linalg.norm(base)
    states = np.broadcast_to(base, (3, 3, base.size)).copy()
    baseline = compute_fhs(states)
    rng = np.random.default_rng(20260728)
    phases = rng.uniform(0.0, 2.0 * np.pi, size=(3, 3))

    transformed = compute_fhs(states * np.exp(1j * phases)[:, :, None])

    np.testing.assert_allclose(transformed.flux, baseline.flux, atol=1e-12)
    assert transformed.chern_raw == pytest.approx(baseline.chern_raw, abs=1e-12)


def test_fhs_coordinates_are_theta_then_phi():
    size = 9
    sigma_x = np.array([[0.0, 1.0], [1.0, 0.0]], dtype=np.complex128)
    sigma_y = np.array([[0.0, -1j], [1j, 0.0]], dtype=np.complex128)
    sigma_z = np.diag([1.0, -1.0]).astype(np.complex128)
    states = np.empty((size, size, 2), dtype=np.complex128)
    for theta_index in range(size):
        theta = 2.0 * np.pi * theta_index / size
        for phi_index in range(size):
            phi = 2.0 * np.pi * phi_index / size
            hamiltonian = (
                np.sin(theta) * sigma_x
                + np.sin(phi) * sigma_y
                + (-1.0 + np.cos(theta) + np.cos(phi)) * sigma_z
            )
            _, vectors = np.linalg.eigh(hamiltonian)
            states[theta_index, phi_index] = vectors[:, 0]

    direct = compute_fhs(states)
    transposed = compute_fhs(states.swapaxes(0, 1))

    assert direct.chern_raw == pytest.approx(-1.0, abs=1e-12)
    assert transposed.chern_raw == pytest.approx(1.0, abs=1e-12)


def test_u0_chern_orientation_and_diagnostics_match_reference():
    result = scan_chern(make_engine(), n_theta=5, n_phi=5)

    assert result.fhs.chern_raw == pytest.approx(2.0, abs=1e-10)
    assert result.fhs.chern_integer == 2
    assert result.minimum_gap == pytest.approx(3.6, abs=1e-10)
    assert result.fhs.maximum_absolute_flux < np.pi - 1e-8
    assert result.maximum_residual < 1e-8
    assert verify_gauge_invariance(result, seed=20260728) < 1e-11


def test_refining_five_to_ten_reuses_all_coarse_vertices():
    engine = make_engine()

    coarse = scan_chern(engine, n_theta=5, n_phi=5)
    fine = scan_chern(engine, n_theta=10, n_phi=10)

    assert coarse.new_diagonalizations == 25
    assert fine.new_diagonalizations == 75
    assert fine.total_diagonalizations == 100
    np.testing.assert_allclose(coarse.states, fine.states[::2, ::2])


def test_reversing_path_reverses_chern_number():
    forward = scan_chern(make_engine(Delta0=3.0), n_theta=5, n_phi=5)
    reverse = scan_chern(make_engine(Delta0=-3.0), n_theta=5, n_phi=5)

    assert reverse.fhs.chern_raw == pytest.approx(
        -forward.fhs.chern_raw,
        abs=1e-10,
    )


def test_adiabatic_charge_matches_chern_and_is_gauge_invariant():
    engine = make_engine()
    result = compute_adiabatic_charge(engine, n_phi=40)
    chern = scan_chern(engine, n_theta=5, n_phi=5)

    assert result.charge == pytest.approx(chern.fhs.chern_raw, abs=1e-8)
    phases = np.exp(1j * np.linspace(0.1, 2.1, result.states.shape[0]))
    phased = polarization_from_states(
        engine.basis,
        engine.model.L,
        result.states * phases[:, None],
    )
    assert phased.charge == pytest.approx(result.charge, abs=1e-12)


def test_wilson_loop_polarization_matches_fhs_for_offset_path_and_random_gauge():
    torus = scan_chern(
        make_engine(U=1.5, Delta_center=1.2),
        n_theta=10,
        n_phi=10,
    )
    rng = np.random.default_rng(19)
    phases = np.exp(
        1j * rng.uniform(0.0, 2.0 * np.pi, size=torus.states.shape[:2])
    )

    result = wilson_loop_polarization(torus.states)
    gauged = wilson_loop_polarization(torus.states * phases[:, :, None])

    assert result.charge == pytest.approx(torus.fhs.chern_raw, abs=1e-10)
    assert gauged.charge == pytest.approx(result.charge, abs=1e-10)
    np.testing.assert_allclose(gauged.polarization, result.polarization, atol=1e-10)


def test_fixed_twist_adiabatic_charge_matches_long_period_boundary_current():
    engine = make_engine()
    result = compute_fixed_twist_adiabatic_charge(
        engine,
        n_phi=80,
        theta_fraction=Fraction(1, 256),
    )
    dynamic = evolve_pump_cycle(engine, period=50.0, n_steps=1000)
    dynamic_at_phi = np.interp(
        result.phi,
        2.0 * np.pi * dynamic.times / dynamic.period,
        dynamic.cumulative_charge,
    )

    assert result.charge == pytest.approx(dynamic.charge, abs=3e-2)
    assert np.sqrt(np.mean((result.cumulative_charge - dynamic_at_phi) ** 2)) < 3e-2


def test_fixed_twist_adiabatic_charge_is_gauge_invariant():
    result = compute_fixed_twist_adiabatic_charge(
        make_engine(),
        n_phi=40,
        theta_fraction=Fraction(1, 128),
    )
    rng = np.random.default_rng(20260729)
    phases = np.exp(
        1j * rng.uniform(0.0, 2.0 * np.pi, size=result.states.shape[:2])
    )

    gauged = fixed_twist_charge_from_states(
        result.states * phases[:, :, None],
        theta_width=result.theta_width,
    )

    np.testing.assert_allclose(
        gauged.cumulative_charge,
        result.cumulative_charge,
        atol=1e-10,
    )
    assert gauged.charge == pytest.approx(result.charge, abs=1e-10)


def test_fixed_twist_adiabatic_charge_refines_phi_and_theta_width():
    converged = converge_fixed_twist_adiabatic_charge(
        make_engine(),
        n_phi=20,
        theta_fraction=Fraction(1, 64),
        curve_tolerance=3e-2,
        max_refinements=3,
    )

    assert converged.result.n_phi >= 40
    assert converged.result.theta_fraction <= Fraction(1, 128)
    assert converged.phi_charge_error < 3e-2
    assert converged.phi_curve_max_error >= converged.phi_charge_error
    assert converged.theta_curve_error < 3e-2


def test_adiabatic_charge_refines_an_aliased_path_grid():
    result = compute_adiabatic_charge(make_engine(), n_phi=7)

    assert result.charge == pytest.approx(2.0, abs=1e-8)
    assert result.n_phi >= 28
    assert result.refinement_count >= 2
    assert result.charge_convergence_error < 1e-8


def test_adiabatic_charge_does_not_false_converge_on_two_point_grid():
    result = compute_adiabatic_charge(make_engine(), n_phi=2)

    assert result.charge == pytest.approx(2.0, abs=1e-8)
    assert result.n_phi >= 16
    assert result.refinement_count >= 3


def test_reversing_path_reverses_adiabatic_charge():
    engine = make_engine()

    forward = compute_adiabatic_charge(engine, n_phi=40, direction=1)
    reverse = compute_adiabatic_charge(engine, n_phi=40, direction=-1)

    assert reverse.charge == pytest.approx(-forward.charge, abs=1e-8)
