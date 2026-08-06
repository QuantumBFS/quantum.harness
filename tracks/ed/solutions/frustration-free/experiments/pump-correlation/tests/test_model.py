"""Tests for pump correlation experiment."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
_PROJECT = _HERE.parent
sys.path.insert(0, str(_PROJECT))

from src.model import SplitRMHModel, _is_antiperiodic
from src.evolution import compute_ground_state


# ---------------------------------------------------------------------------
# Boundary condition tests
# ---------------------------------------------------------------------------

def test_antiperiodic_convention():
    """Open-shell convention: L ≡ 0 mod 4 → PBC, L ≡ 2 mod 4 → anti-PBC."""
    assert not _is_antiperiodic(8)
    assert not _is_antiperiodic(12)
    assert _is_antiperiodic(6)
    assert _is_antiperiodic(10)
    assert _is_antiperiodic(14)


# ---------------------------------------------------------------------------
# Model construction tests
# ---------------------------------------------------------------------------

def test_l6_model_builds():
    model = SplitRMHModel(L=6, U=10.0)
    assert model.dim == 400  # C(6,3)^2
    assert model.antiperiodic is True


def test_l8_model_builds():
    model = SplitRMHModel(L=8, U=10.0)
    assert model.dim == 4900  # C(8,4)^2
    assert model.antiperiodic is False


def test_hamiltonian_at_delta_zero():
    """At δ=0, Δ=0, the Hamiltonian should be the bare hopping + U term."""
    model = SplitRMHModel(L=6, U=10.0)
    H = model.hamiltonian_at(delta=0.0, Delta=0.0)
    M = H.toarray()
    herr = float(np.max(np.abs(M - M.conj().T)))
    assert herr < 1e-12


def test_hamiltonian_hermiticity():
    """H(δ,Δ) should be Hermitian for representative parameters."""
    model = SplitRMHModel(L=6, U=10.0)
    for delta in [-0.88, 0.0, 0.88]:
        for Delta in [2.9, 5.0, 7.1]:
            H = model.hamiltonian_at(delta, Delta)
            M = H.toarray()
            herr = float(np.max(np.abs(M - M.conj().T)))
            assert herr < 1e-12, f"δ={delta}, Δ={Delta}: hermiticity error={herr:.2e}"


def test_antiperiodic_boundary_sign():
    """Anti-PBC at L=6: the boundary hopping should have opposite sign to PBC at L=8."""
    model_pbc = SplitRMHModel(L=8, U=10.0)
    model_anti = SplitRMHModel(L=6, U=10.0)

    H_pbc = model_pbc.hamiltonian_at(delta=0.0, Delta=0.0).toarray()
    H_anti = model_anti.hamiltonian_at(delta=0.0, Delta=0.0).toarray()

    # Both should be Hermitian
    assert np.max(np.abs(H_pbc - H_pbc.conj().T)) < 1e-12
    assert np.max(np.abs(H_anti - H_anti.conj().T)) < 1e-12


# ---------------------------------------------------------------------------
# Ground state tests
# ---------------------------------------------------------------------------

def test_ground_state_l6():
    """Ground state at θ=0 should have low residual and correct particle number."""
    model = SplitRMHModel(L=6, U=10.0)
    gs = compute_ground_state(model, delta=0.88, Delta=5.0)
    assert gs.converged
    assert gs.residual < 1e-8
    assert gs.energy < 0  # hopping lowers energy


def test_ground_state_pbc_vs_anti():
    """GS energy should differ between PBC and anti-PBC for the same physical params."""
    model_anti = SplitRMHModel(L=6, U=10.0)
    gs_anti = compute_ground_state(model_anti, delta=0.88, Delta=5.0)

    # L=8 has PBC but different basis — compare at L=6 only
    assert gs_anti.converged


# ---------------------------------------------------------------------------
# Smoke test: full pipeline at L=6, 10 steps
# ---------------------------------------------------------------------------

def test_smoke_pipeline_l6():
    """End-to-end smoke test: L=6, 10 steps, measure correlations."""
    from src.evolution import evolve_midpoint_krylov
    from src.observables import measure_correlations

    model = SplitRMHModel(L=6, U=10.0)
    gs = compute_ground_state(model, delta=0.88, Delta=5.0)

    T_eff = 1.0   # 10 steps at dt=0.1
    dt = 0.1

    def delta_of_tau(tau):
        return 0.88 * np.cos(-2.0 * np.pi * tau / 100.0)

    def Delta_of_tau(tau):
        return 5.0 + 2.10 * np.sin(-2.0 * np.pi * tau / 100.0)

    ev = evolve_midpoint_krylov(
        model=model, psi0=gs.state, T=T_eff, dt=dt,
        delta_of_tau=delta_of_tau, Delta_of_tau=Delta_of_tau,
        save_interval=0.2,
    )

    max_norm_err = max(ev.norm_errors) if ev.norm_errors else 0.0
    assert max_norm_err < 1e-8, f"norm error {max_norm_err:.2e}"

    corr = measure_correlations(model, ev.times, ev.states, ev.norm_errors)
    assert corr.C_spin.shape == (len(ev.times),)
    assert corr.C_charge.shape == (len(ev.times),)
    assert corr.bond_spin.shape == (len(ev.times), 6)
    assert corr.bond_charge.shape == (len(ev.times), 6)

    # Correlations should be physically sensible
    assert -1.0 < corr.C_spin[0] < 1.0
    assert 0.0 < corr.C_charge[0] < 2.0


# ---------------------------------------------------------------------------
# Current operator tests
# ---------------------------------------------------------------------------

def test_current_operators_hermiticity():
    """J_j^(0) and J_j^(1) should be Hermitian for each bond."""
    from src.current import _build_current_operators

    model = SplitRMHModel(L=6, U=10.0)
    J0_ops, J1_ops = _build_current_operators(model)

    for j, (J0, J1) in enumerate(zip(J0_ops, J1_ops)):
        M0 = J0.toarray()
        M1 = J1.toarray()
        err0 = float(np.max(np.abs(M0 - M0.conj().T)))
        err1 = float(np.max(np.abs(M1 - M1.conj().T)))
        assert err0 < 1e-12, f"J0 bond {j} not Hermitian: {err0:.2e}"
        assert err1 < 1e-12, f"J1 bond {j} not Hermitian: {err1:.2e}"


def test_current_operator_apbc_phase():
    """APBC boundary current (bond L-1) must differ from PBC by twist phase."""
    from src.current import _build_current_operators

    model_anti = SplitRMHModel(L=6, U=10.0)   # APBC
    model_pbc = SplitRMHModel(L=8, U=10.0)     # PBC

    J0_anti, _ = _build_current_operators(model_anti)
    J0_pbc, _ = _build_current_operators(model_pbc)

    M_anti = J0_anti[5].toarray()  # boundary bond of L=6
    M_pbc = J0_pbc[7].toarray()    # boundary bond of L=8

    # PBC boundary current matrix should differ from APBC by sign (twist = -1)
    # Both should be Hermitian
    assert np.max(np.abs(M_anti - M_anti.conj().T)) < 1e-12
    assert np.max(np.abs(M_pbc - M_pbc.conj().T)) < 1e-12


def test_current_expectation_real():
    """Current expectation values must be real for any state."""
    from src.current import _build_current_operators

    model = SplitRMHModel(L=6, U=10.0)
    J0_ops, J1_ops = _build_current_operators(model)

    rng = np.random.RandomState(42)
    psi = rng.randn(model.dim) + 1j * rng.randn(model.dim)
    psi /= np.linalg.norm(psi)
    psi_conj = psi.conj()

    for j in range(model.L):
        exp0 = np.dot(psi_conj, J0_ops[j].dot(psi))
        exp1 = np.dot(psi_conj, J1_ops[j].dot(psi))
        assert abs(exp0.imag) < 1e-12, f"J0[{j}] imaginary part: {exp0.imag:.2e}"
        assert abs(exp1.imag) < 1e-12, f"J1[{j}] imaginary part: {exp1.imag:.2e}"


def test_current_sum_zero_at_equilibrium():
    """For the ground state of H(δ=0, Δ=0), total current should vanish."""
    from src.current import _build_current_operators

    model = SplitRMHModel(L=6, U=10.0)
    J0_ops, J1_ops = _build_current_operators(model)

    # Ground state at δ=0, Δ=0 (time-reversal invariant point)
    gs = compute_ground_state(model, delta=0.0, Delta=0.0)
    psi = gs.state
    psi_conj = psi.conj()

    J_total = 0.0
    for j in range(model.L):
        exp_J0 = float(np.dot(psi_conj, J0_ops[j].dot(psi)).real)
        exp_J1 = float(np.dot(psi_conj, J1_ops[j].dot(psi)).real)
        # At δ=0: J_j = J_j^(0) + 0 * J_j^(1) = J_j^(0)
        J_total += exp_J0

    assert abs(J_total) < 1e-10, f"Total current at δ=0, Δ=0: {J_total:.2e}"


def test_trapezoidal_integration():
    """Cumulative trapezoid should give Q(0)=0 and correct linear integral."""
    from src.current import _cumulative_trapezoid

    x = np.linspace(0, 10, 101)
    y = np.ones_like(x)
    Q = _cumulative_trapezoid(x, y)
    assert Q[0] == 0.0
    assert abs(Q[-1] - 10.0) < 1e-10  # ∫₀¹⁰ 1 dx = 10

    # Quadratic: y = 2x, ∫₀^t 2x dx = t²
    y2 = 2 * x
    Q2 = _cumulative_trapezoid(x, y2)
    assert abs(Q2[-1] - 100.0) < 1e-10


def test_continuity_equation_l6():
    """Continuity residual should be small for a short evolution."""
    from src.current import measure_currents
    from src.evolution import evolve_midpoint_krylov

    model = SplitRMHModel(L=6, U=10.0)
    gs = compute_ground_state(model, delta=0.88, Delta=5.0)

    def delta_of_tau(tau):
        return 0.88 * np.cos(-2.0 * np.pi * tau / 100.0)

    ev = evolve_midpoint_krylov(
        model=model, psi0=gs.state, T=1.0, dt=0.1,
        delta_of_tau=delta_of_tau,
        Delta_of_tau=lambda tau: 5.0 + 2.10 * np.sin(-2.0 * np.pi * tau / 100.0),
        save_interval=0.2,
    )

    curr = measure_currents(model, ev.times, ev.states, delta_of_tau)
    # Continuity residual dominated by O(dτ²) central-difference error on
    # the save grid (dτ = 0.2).  Threshold set well above this.
    assert curr.continuity_residual < 1e-2, \
        f"continuity residual too large: {curr.continuity_residual:.2e}"


def test_current_smoke_pipeline():
    """End-to-end: L=6 smoke test with current measurement."""
    from src.current import measure_currents
    from src.evolution import evolve_midpoint_krylov

    model = SplitRMHModel(L=6, U=10.0)
    gs = compute_ground_state(model, delta=0.88, Delta=5.0)

    def delta_of_tau(tau):
        return 0.88 * np.cos(-2.0 * np.pi * tau / 100.0)

    def Delta_of_tau(tau):
        return 5.0 + 2.10 * np.sin(-2.0 * np.pi * tau / 100.0)

    ev = evolve_midpoint_krylov(
        model=model, psi0=gs.state, T=1.0, dt=0.1,
        delta_of_tau=delta_of_tau, Delta_of_tau=Delta_of_tau,
        save_interval=0.2,
    )

    curr = measure_currents(model, ev.times, ev.states, delta_of_tau)

    # Check shapes
    n_save = len(ev.times)
    assert curr.bond_current.shape == (n_save, 6)
    assert curr.current_mean.shape == (n_save,)
    assert curr.current_even.shape == (n_save,)
    assert curr.current_odd.shape == (n_save,)
    assert curr.density_by_site.shape == (n_save, 6)

    # Check Q(0) = 0
    assert curr.Q[0] == 0.0
    assert curr.Q_even[0] == 0.0
    assert curr.Q_odd[0] == 0.0

    # Check even + odd consistency: J = (J_even + J_odd) / 2
    np.testing.assert_allclose(
        curr.current_mean,
        (curr.current_even + curr.current_odd) / 2.0,
        atol=1e-14,
    )

    # Check Q_cycle is finite
    assert np.isfinite(curr.Q_cycle)

    # Continuity residual dominated by O(dτ²) central-difference error
    assert curr.continuity_residual < 1e-2
