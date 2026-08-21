"""End-to-end correctness of the MPS METTS backend vs the dense reference.

With a large bond dimension (chi >= 2**(N/2)) the snake-MPS evolution is
exact (no truncation), so the MPS backend must reproduce the dense spectral
METTS energy on a single product state, and the full chain must reproduce ED
u within statistics. These are the gates that let the MPS backend scale to
10x10 with confidence.
"""
import numpy as np
import pytest

from metts_b.bridge import ed_thermodynamics, SquareLattice
from metts_b.measure import DenseBackend
from metts_b.mps_backend import MPSBackend


def test_mps_single_sample_energy_matches_dense_spectral():
    # One product state, evolve to beta/2, measure E. With chi large enough
    # that no truncation occurs, MPS Trotter (small dtau) must match the dense
    # SPECTRAL energy (exact e^{-beta H}) within Trotter error.
    Lx, Ly, h = 2, 2, 3.0
    N = Lx * Ly
    beta = 0.4
    spins = np.array([1, -1, 1, -1], dtype=int)
    # dense spectral reference (exact)
    be_sp = DenseBackend(Lx, Ly, h, evolve="spectral")
    psi_sp = be_sp.evolve(be_sp.make_product_state(spins), beta)
    E_sp, _, _ = be_sp.energy_moments(psi_sp)
    # MPS, large chi, small dtau
    mps_be = MPSBackend(Lx, Ly, h, dtau=0.01, max_bond_dim=32, trunc_tol=0.0)
    mps = mps_be.make_product_state(spins)
    mps = mps_be.evolve(mps, beta)
    E_mps, _, _ = mps_be.energy_moments(mps)
    assert abs(E_mps - E_sp) < 1e-2, (E_mps, E_sp)


def test_mps_chain_u_matches_ed():
    # Full METTS chain on 2x2 h=3.0 with the MPS backend, large chi: the
    # sample-mean u must match ED u within MC statistics + Trotter error. We
    # use dtau=0.01, where the 2nd-order Trotter energy has converged to the
    # spectral value (verified: E(dtau=0.01) == E(spectral) to ~1e-4 at this
    # beta), so the residual is MC noise + tiny chi truncation.
    from metts_b.chain import run_chain
    Lx, Ly, h = 2, 2, 3.0
    N = Lx * Ly
    beta = 0.5
    ed = ed_thermodynamics(Lx, Ly, h, beta_list=[beta])[0]
    mps_be = MPSBackend(Lx, Ly, h, dtau=0.01, max_bond_dim=32, trunc_tol=0.0)
    res = run_chain(mps_be, beta=beta, n_warmup=30, n_production=2000,
                    seed=42, dtau=0.01, evolve_mode="trotter",
                    write_traces=False)
    assert res.n_production > 0
    u = res.u
    sem = res.u_err
    assert abs(u - ed.u) < max(6 * sem, 0.005), (u, ed.u, sem)


def test_mps_collapse_yields_valid_product_state():
    # The collapse must return +/-1 spins for every site and per-site probs
    # that normalise, on the MPS backend.
    Lx, Ly, h = 2, 2, 3.0
    N = Lx * Ly
    mps_be = MPSBackend(Lx, Ly, h, dtau=0.02, max_bond_dim=32)
    mps = mps_be.make_product_state(np.array([1, 1, 1, 1], dtype=int))
    mps = mps_be.evolve(mps, 0.4)
    rng = np.random.default_rng(0)
    probs, spins, mass = mps_be.conditional_prob_and_collapse(mps, rng)
    assert probs.shape == (N, 2)
    assert np.all(probs >= -1e-10) and np.all(probs <= 1 + 1e-10)
    assert np.allclose(probs.sum(axis=1), 1.0, atol=1e-9)
    assert np.all(np.isin(spins, [-1, 1]))
    assert spins.size == N


def test_mps_3x4_chain_runs_and_approximates_ed():
    # 3x4 (N=12): ED-feasible harder check. The MPS backend must run without
    # crashing and give u close to ED. At N=12, beta=0.5 the evolved METTS
    # states need bond dim ~64 (verified: chi=64 gives max discarded weight 0
    # and matches dense-Trotter exactly; chi<64 is catastrophically lossy
    # because these typical states are genuinely highly entangled near
    # criticality -- the known 2D-METTS hardness). We use chi=64 so the test
    # checks MPS *correctness*, not the (Phase 3) chi-convergence question.
    from metts_b.chain import run_chain
    Lx, Ly, h = 3, 4, 3.0
    N = Lx * Ly
    beta = 0.5
    ed = ed_thermodynamics(Lx, Ly, h, beta_list=[beta])[0]
    mps_be = MPSBackend(Lx, Ly, h, dtau=0.02, max_bond_dim=64, trunc_tol=1e-12)
    res = run_chain(mps_be, beta=beta, n_warmup=15, n_production=400,
                    seed=55, dtau=0.02, evolve_mode="trotter",
                    write_traces=False)
    assert res.n_production > 0
    # chi=64 (no truncation) + dtau=0.02 Trotter + MC: residual is Trotter+MC
    assert abs(res.u - ed.u) < 0.03, (res.u, ed.u)
