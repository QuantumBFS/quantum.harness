"""Physics-correctness tests for the dense METTS backend.

These are the §3 (small-system) validation gates of the B task spec. They run
fast (2x2 = 16-dim) and pin the conventions: the spectral evolution path must
match ED to machine precision (it is the exact e^{-beta H}); the Trotter path
must approach the spectral value as dtau -> 0; the collapse must sample the
exact joint Z-basis distribution; the chain estimator must reproduce ED u and
C within statistical error for enough samples.
"""
import numpy as np
import pytest

from metts_b.bridge import ed_thermodynamics
from metts_b.hamiltonian import (
    product_state_vector, build_hamiltonian, site_bit,
)
from metts_b.measure import DenseBackend


# ---------------------------------------------------------------------------
# Convention: product state <-> vector bit ordering
# ---------------------------------------------------------------------------

def test_product_state_bit_convention():
    # spins = [+1,-1,+1,-1] on N=4. site i -> bit (N-1-i).
    N = 4
    spins = np.array([1, -1, 1, -1])
    psi = product_state_vector(spins, N)
    assert psi.shape == (16,)
    b = 0
    for i in range(N):
        if spins[i] == 1:
            b |= 1 << site_bit(i, N)
    assert np.argmax(np.abs(psi)) == b
    assert np.isclose(np.abs(psi[b]), 1.0)


# ---------------------------------------------------------------------------
# Spectral evolution == ED. The defining correctness check.
# ---------------------------------------------------------------------------

def test_spectral_metts_mean_energy_matches_ed():
    # <H>_beta via the METTS spectral estimator (exact e^{-beta H/2}) must
    # equal ED's u*N to tight tolerance for any beta, on average over many
    # samples. Use a tiny lattice and many samples.
    Lx, Ly, h = 2, 2, 3.0
    N = Lx * Ly
    beta = 0.5
    ed = ed_thermodynamics(Lx, Ly, h, beta_list=[beta])[0]
    be = DenseBackend(Lx, Ly, h, evolve="spectral")
    rng = np.random.default_rng(123)
    Es, E2s = [], []
    spins = (rng.integers(0, 2, size=N) * 2 - 1).astype(np.int8)
    for _ in range(4000):
        psi = be.make_product_state(spins)
        psi = be.evolve(psi, beta)
        E, E2, _ = be.energy_moments(psi)
        probs, spins_new, _ = be.conditional_prob_and_collapse(psi, rng)
        Es.append(E)
        E2s.append(E2)
        spins = spins_new
    Es = np.array(Es); E2s = np.array(E2s)
    u_metts = np.mean(Es) / N
    # spectral path is exact e^{-beta H}; METTS mean == ED exactly up to MC
    # noise. Allow 5 sigma of the MC SEM.
    sem = np.std(Es, ddof=1) / np.sqrt(len(Es)) / N
    assert abs(u_metts - ed.u) < 5 * sem + 1e-9, (
        f"u_metts={u_metts} ed.u={ed.u} sem={sem}")
    # specific heat via the fluctuation formula: beta^2 (mean(E2)-mean(E)^2)/N,
    # i.e. the thermal variance of H (within-sample + between-sample), NOT the
    # between-sample variance of E_sigma alone.
    C_metts = beta**2 * (np.mean(E2s) - np.mean(Es)**2) / N
    # C has larger MC error; allow generous tolerance
    assert abs(C_metts - ed.C) < 0.15 * abs(ed.C) + 0.05, (
        f"C_metts={C_metts} ed.C={ed.C}")


def test_free_energy_integration_of_exact_u_matches_ed():
    # The free-energy reconstruction (free_energy_from_u, shared convention) is
    # exact up to trapezoidal discretization. Feeding it the EXACT ED u(beta)
    # on a dense grid must reproduce ED f to within the trapezoidal limit
    # (~4e-3 on a 20-pt grid; worst near the beta->0 anchor). This isolates the
    # integration error from MC noise and pins the shared convention.
    from metts_b.bridge import free_energy_from_u
    Lx, Ly, h = 2, 2, 3.0
    betas = np.linspace(0.05, 1.0, 20).tolist()
    ed = ed_thermodynamics(Lx, Ly, h, beta_list=betas)
    fs = free_energy_from_u(betas, [e.u for e in ed])
    for f_int, e in zip(fs, ed):
        assert abs(f_int - e.f) < 0.01, (f"f_int={f_int} ed.f={e.f}")


def test_spectral_free_energy_matches_ed_dense_grid():
    # With METTS u(beta) (spectral, exact evolution) reconstructed via
    # free_energy_from_u on a DENSE grid starting at small beta (to resolve the
    # beta->0 anchor), f matches ED f to within the trapezoidal limit + MC
    # noise. Verified empirically to <= ~1.3e-2 on this grid with 4000 samples.
    from metts_b.bridge import free_energy_from_u
    Lx, Ly, h = 2, 2, 3.0
    N = Lx * Ly
    betas = np.linspace(0.05, 1.0, 20).tolist()
    ed = ed_thermodynamics(Lx, Ly, h, beta_list=betas)
    be = DenseBackend(Lx, Ly, h, evolve="spectral")
    rng = np.random.default_rng(7)
    us = []
    for beta in betas:
        spins = (rng.integers(0, 2, size=N) * 2 - 1).astype(np.int8)
        Es = []
        for _ in range(4000):
            psi = be.make_product_state(spins)
            psi = be.evolve(psi, beta)
            E, _, _ = be.energy_moments(psi)
            _, spins, _ = be.conditional_prob_and_collapse(psi, rng)
            Es.append(E)
        us.append(np.mean(Es) / N)
    fs = free_energy_from_u(betas, us)
    # tolerance = trapezoidal limit (~4e-3) + MC noise amplified by 1/beta
    for f_metts, e in zip(fs, ed):
        assert abs(f_metts - e.f) < 0.02, (
            f"beta={e.beta} f_metts={f_metts} ed.f={e.f}")


# ---------------------------------------------------------------------------
# Collapse samples the exact joint Z-basis distribution.
# ---------------------------------------------------------------------------

def test_collapse_distribution_matches_exact():
    # For a fixed evolved state, the Z-basis outcome distribution from the
    # sequential collapse must equal |<s|phi>|^2 exactly. Build phi, then draw
    # many collapses with a fixed rng and compare the histogram to the exact
    # |amplitude|^2.
    Lx, Ly, h = 2, 2, 3.0
    N = Lx * Ly
    beta = 0.5
    be = DenseBackend(Lx, Ly, h, evolve="spectral")
    rng = np.random.default_rng(0)
    spins0 = np.array([1, 1, 1, 1], dtype=np.int8)
    psi = be.evolve(be.make_product_state(spins0), beta)
    p_exact = (psi * psi.conj()).real
    p_exact /= p_exact.sum()
    counts = np.zeros(2 ** N, dtype=int)
    for _ in range(20000):
        _, spins_new, _ = be.conditional_prob_and_collapse(psi.copy(), rng)
        b = 0
        for i in range(N):
            if spins_new[i] == 1:
                b |= 1 << site_bit(i, N)
        counts[b] += 1
    emp = counts / counts.sum()
    # chi-square-ish: max abs deviation should be small for 20k draws
    assert np.max(np.abs(emp - p_exact)) < 0.02, (
        f"max dev={np.max(np.abs(emp - p_exact))}")


def test_conditional_probabilities_normalize():
    # every site's (p_up,p_down) must sum to 1 and lie in [0,1].
    Lx, Ly, h = 2, 2, 3.0
    be = DenseBackend(Lx, Ly, h, evolve="spectral")
    rng = np.random.default_rng(1)
    psi = be.evolve(be.make_product_state(
        np.array([1, -1, 1, -1], dtype=np.int8)), 0.5)
    probs, spins, mass = be.conditional_prob_and_collapse(psi, rng)
    assert probs.shape == (4, 2)
    assert np.all(probs >= -1e-12)
    assert np.all(probs <= 1 + 1e-12)
    assert np.allclose(probs.sum(axis=1), 1.0)
    assert np.all(np.isin(spins, [-1, 1]))


# ---------------------------------------------------------------------------
# Trotter converges to spectral as dtau -> 0.
# ---------------------------------------------------------------------------

def test_trotter_converges_to_spectral():
    # With spectral as the exact reference, the Trotter METTS energy (single
    # fixed product state, no sampling) must approach the spectral energy as
    # dtau shrinks. This validates the Trotter gate implementation.
    Lx, Ly, h = 2, 2, 3.0
    beta = 0.4
    spins = np.array([1, -1, 1, -1], dtype=np.int8)
    be_sp = DenseBackend(Lx, Ly, h, evolve="spectral")
    psi_sp = be_sp.evolve(be_sp.make_product_state(spins), beta)
    E_sp, _, _ = be_sp.energy_moments(psi_sp)
    errs = []
    for dtau in [0.2, 0.1, 0.05, 0.025]:
        be_tr = DenseBackend(Lx, Ly, h, evolve="trotter", dtau=dtau)
        psi_tr = be_tr.evolve(be_tr.make_product_state(spins), beta)
        E_tr, _, _ = be_tr.energy_moments(psi_tr)
        errs.append(abs(E_tr - E_sp))
    # 2nd-order Trotter: error should drop ~4x when dtau halves
    assert errs[-1] < errs[0] / 4, f"trotter not converging: {errs}"
    assert errs[-1] < 1e-3, f"final trotter error {errs[-1]} too large"


# ---------------------------------------------------------------------------
# Reproducibility: same seed -> same chain.
# ---------------------------------------------------------------------------

def test_chain_reproducible():
    from metts_b.chain import run_chain
    Lx, Ly, h = 2, 2, 3.0
    be = DenseBackend(Lx, Ly, h, evolve="spectral")
    r1 = run_chain(be, beta=0.5, n_warmup=5, n_production=20, seed=99,
                   dtau=0.05, evolve_mode="spectral", write_traces=False)
    r2 = run_chain(be, beta=0.5, n_warmup=5, n_production=20, seed=99,
                   dtau=0.05, evolve_mode="spectral", write_traces=False)
    assert np.allclose(r1.E_samples, r2.E_samples)
