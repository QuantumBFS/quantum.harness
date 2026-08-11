"""Tests for the spinon-holon-pump experiment.

Covers:
  1. TwoSectorModel construction with correct dimensions
  2. Hole creation normalization and particle number
  3. U=0 control: h_j ≡ s_j (charge and spin propagate identically)
  4. Per-site measurement sums
  5. Coarse-graining correctness
  6. COM phase method on delta-function and uniform distributions
"""

import sys
from pathlib import Path

import numpy as np
import pytest

_HERE = Path(__file__).resolve().parent
_PROJECT = _HERE.parent
sys.path.insert(0, str(_PROJECT))

from src.model import TwoSectorModel  # noqa: E402
from src.hole import create_hole, create_hole_wavepacket, d_pbc  # noqa: E402
from src.evolution import compute_ground_state  # noqa: E402
from src.observables import measure_all_per_site  # noqa: E402
from src.defect import (  # noqa: E402
    compute_hole_density,
    compute_spin_defect,
    coarse_grain_two_site,
    compute_com_phase,
    compute_all_defects,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def tsm_l6_u0():
    """L=6, U=0 two-sector model (small, fast)."""
    return TwoSectorModel(L=6, U=0.0)


@pytest.fixture(scope="module")
def tsm_l6_u10():
    """L=6, U=10 two-sector model."""
    return TwoSectorModel(L=6, U=10.0)


@pytest.fixture(scope="module")
def gs_u0(tsm_l6_u0):
    """Half-filling GS at δ=0, Δ=5 (φ₀=5π/3 with R_δ=0.4)."""
    phi0 = 5.0 * np.pi / 3.0
    delta = 0.4 * np.cos(phi0)
    Delta = 5.0 + 2.1 * np.sin(phi0)
    return compute_ground_state(tsm_l6_u0.model_N, delta, Delta)


@pytest.fixture(scope="module")
def gs_u10(tsm_l6_u10):
    """Half-filling GS at U=10, φ₀=5π/3."""
    phi0 = 5.0 * np.pi / 3.0
    delta = 0.4 * np.cos(phi0)
    Delta = 5.0 + 2.1 * np.sin(phi0)
    return compute_ground_state(tsm_l6_u10.model_N, delta, Delta)


# ---------------------------------------------------------------------------
# 1. TwoSectorModel construction
# ---------------------------------------------------------------------------

class TestTwoSectorModel:
    def test_dimensions_l6(self, tsm_l6_u0):
        """L=6: half-filling = C(6,3)^2 = 400, one-hole = C(6,2)*C(6,3) = 15*20 = 300.
        L=6 -> L%4=2 -> anti-PBC -> antiperiodic=True."""
        assert tsm_l6_u0.dim_N == 400
        assert tsm_l6_u0.dim_Nm1 == 300
        assert tsm_l6_u0.antiperiodic

    def test_dimensions_l8(self):
        """L=8: half-filling = C(8,4)^2 = 4900, one-hole = C(8,3)*C(8,4) = 56*70 = 3920."""
        tsm = TwoSectorModel(L=8, U=0.0)
        assert tsm.dim_N == 4900
        assert tsm.dim_Nm1 == 3920

    def test_dimensions_l10(self):
        """L=10: half-filling = C(10,5)^2 = 63504, one-hole = C(10,4)*C(10,5) = 52920."""
        tsm = TwoSectorModel(L=10, U=0.0)
        assert tsm.dim_N == 63504
        assert tsm.dim_Nm1 == 52920

    def test_same_boundary_condition(self):
        """Both sectors must use the same boundary condition."""
        tsm = TwoSectorModel(L=10, U=0.0)
        assert tsm.model_N.antiperiodic == tsm.model_Nm1.antiperiodic

    def test_hamiltonian_at_works(self, tsm_l6_u0):
        """hamiltonian_at should return a sparse matrix of correct shape."""
        H = tsm_l6_u0.model_N.hamiltonian_at(0.0, 0.0)
        assert H.shape == (tsm_l6_u0.dim_N, tsm_l6_u0.dim_N)
        H_hole = tsm_l6_u0.model_Nm1.hamiltonian_at(0.0, 0.0)
        assert H_hole.shape == (tsm_l6_u0.dim_Nm1, tsm_l6_u0.dim_Nm1)


# ---------------------------------------------------------------------------
# 2. Hole creation
# ---------------------------------------------------------------------------

class TestHoleCreation:
    def test_create_hole_normalized(self, tsm_l6_u10, gs_u10):
        """create_hole should return a normalized state."""
        for j in range(6):
            psi_h = create_hole(tsm_l6_u10.model_N, tsm_l6_u10.model_Nm1,
                                gs_u10.state, j)
            norm = float(np.linalg.norm(psi_h))
            assert abs(norm - 1.0) < 1e-12, f"Hole at site {j} not normalized: norm={norm}"

    def test_create_hole_wavepacket_normalized(self, tsm_l6_u10, gs_u10):
        """Wavepacket should be normalized."""
        psi_wp = create_hole_wavepacket(
            tsm_l6_u10.model_N, tsm_l6_u10.model_Nm1,
            gs_u10.state, sigma=1.2, k0=0.0,
        )
        norm = float(np.linalg.norm(psi_wp))
        assert abs(norm - 1.0) < 1e-12

    def test_hole_particle_number(self, tsm_l6_u10, gs_u10):
        """Hole state should have N_up = L/2 - 1, N_down = L/2."""
        psi_wp = create_hole_wavepacket(
            tsm_l6_u10.model_N, tsm_l6_u10.model_Nm1,
            gs_u10.state, sigma=1.2, k0=0.0,
        )
        obs = measure_all_per_site(
            tsm_l6_u10.model_Nm1,
            np.array([0.0]),
            [psi_wp],
        )
        n_up_total = np.sum(obs["n_up"][0])
        n_down_total = np.sum(obs["n_down"][0])
        assert abs(n_up_total - 2.0) < 1e-10  # L/2 - 1 = 2
        assert abs(n_down_total - 3.0) < 1e-10  # L/2 = 3

    def test_wavepacket_centered(self, tsm_l6_u10, gs_u10):
        """Wavepacket at k0=0 should be centered near j0 = L/2 = 3."""
        psi_wp = create_hole_wavepacket(
            tsm_l6_u10.model_N, tsm_l6_u10.model_Nm1,
            gs_u10.state, sigma=1.2, k0=0.0,
        )
        obs = measure_all_per_site(
            tsm_l6_u10.model_Nm1,
            np.array([0.0]),
            [psi_wp],
        )
        n_hole = obs["n_total"][0]
        # Should have a deficit near site 3
        n_ref = np.ones(6)  # uniform half-filling expectation
        # Just check that n_total is not uniform (hole is localized)
        assert np.std(n_hole) > 0.01

    def test_d_pbc(self):
        """Test periodic distance function."""
        assert d_pbc(0, 5.0, 10) == 5.0
        assert d_pbc(9, 5.0, 10) == 4.0  # shorter via boundary
        assert d_pbc(0, 0.0, 10) == 0.0
        assert d_pbc(9, 0.0, 10) == 1.0  # shorter via boundary


# ---------------------------------------------------------------------------
# 3. Per-site measurements
# ---------------------------------------------------------------------------

class TestPerSiteMeasurements:
    def test_measure_all_per_site_shapes(self, tsm_l6_u10, gs_u10):
        """Check output shapes."""
        psi_wp = create_hole_wavepacket(
            tsm_l6_u10.model_N, tsm_l6_u10.model_Nm1,
            gs_u10.state,
        )
        obs = measure_all_per_site(
            tsm_l6_u10.model_Nm1,
            np.array([0.0, 1.0]),
            [psi_wp, psi_wp],
        )
        L = 6
        for key in ["n_up", "n_down", "n_total", "Sz"]:
            assert obs[key].shape == (2, L), f"{key} shape {obs[key].shape}"

    def test_n_total_is_sum(self, tsm_l6_u10, gs_u10):
        """n_total should equal n_up + n_down."""
        psi_wp = create_hole_wavepacket(
            tsm_l6_u10.model_N, tsm_l6_u10.model_Nm1,
            gs_u10.state,
        )
        obs = measure_all_per_site(
            tsm_l6_u10.model_Nm1,
            np.array([0.0]),
            [psi_wp],
        )
        np.testing.assert_allclose(
            obs["n_total"][0],
            obs["n_up"][0] + obs["n_down"][0],
            atol=1e-14,
        )

    def test_Sz_formula(self, tsm_l6_u10, gs_u10):
        """S^z should equal (n_up - n_down)/2."""
        psi_wp = create_hole_wavepacket(
            tsm_l6_u10.model_N, tsm_l6_u10.model_Nm1,
            gs_u10.state,
        )
        obs = measure_all_per_site(
            tsm_l6_u10.model_Nm1,
            np.array([0.0]),
            [psi_wp],
        )
        Sz_expected = (obs["n_up"][0] - obs["n_down"][0]) / 2.0
        np.testing.assert_allclose(obs["Sz"][0], Sz_expected, atol=1e-14)


# ---------------------------------------------------------------------------
# 4. Defect densities
# ---------------------------------------------------------------------------

class TestDefectDensities:
    def test_hole_density_sums_to_one(self, tsm_l6_u10, gs_u10):
        """h_j should sum to 1 (one missing electron)."""
        psi_wp = create_hole_wavepacket(
            tsm_l6_u10.model_N, tsm_l6_u10.model_Nm1,
            gs_u10.state,
        )
        # Half-filling reference (static, GS doesn't evolve)
        obs_N = measure_all_per_site(
            tsm_l6_u10.model_N, np.array([0.0]), [gs_u10.state],
        )
        obs_hole = measure_all_per_site(
            tsm_l6_u10.model_Nm1, np.array([0.0]), [psi_wp],
        )
        h_j = compute_hole_density(obs_N["n_total"], obs_hole["n_total"])
        assert abs(np.sum(h_j) - 1.0) < 1e-10

    def test_spin_defect_sums_to_one(self, tsm_l6_u10, gs_u10):
        """s_j should sum to 1 (one missing spin-1/2)."""
        psi_wp = create_hole_wavepacket(
            tsm_l6_u10.model_N, tsm_l6_u10.model_Nm1,
            gs_u10.state,
        )
        obs_N = measure_all_per_site(
            tsm_l6_u10.model_N, np.array([0.0]), [gs_u10.state],
        )
        obs_hole = measure_all_per_site(
            tsm_l6_u10.model_Nm1, np.array([0.0]), [psi_wp],
        )
        s_j = compute_spin_defect(obs_N["Sz"], obs_hole["Sz"])
        assert abs(np.sum(s_j) - 1.0) < 1e-10

    def test_u0_charge_spin_identity(self, tsm_l6_u0, gs_u0):
        """At U=0, hole density ≡ spin defect density (no separation).

        This is the CRITICAL pass criterion: without interactions,
        removing one spin-up electron creates identical charge and spin
        defect profiles because the many-body wavefunction factorizes.
        """
        psi_wp = create_hole_wavepacket(
            tsm_l6_u0.model_N, tsm_l6_u0.model_Nm1,
            gs_u0.state, sigma=1.2, k0=0.0,
        )
        obs_N = measure_all_per_site(
            tsm_l6_u0.model_N, np.array([0.0]), [gs_u0.state],
        )
        obs_hole = measure_all_per_site(
            tsm_l6_u0.model_Nm1, np.array([0.0]), [psi_wp],
        )

        h_j = compute_hole_density(obs_N["n_total"], obs_hole["n_total"])
        s_j = compute_spin_defect(obs_N["Sz"], obs_hole["Sz"])

        max_diff = np.max(np.abs(h_j - s_j))
        # At U=0, h_j and s_j should be identical for a single spin-up hole
        # because the spin-↓ sector is a spectator
        assert max_diff < 1e-12, f"U=0 identity violated: max|h_j - s_j| = {max_diff}"


# ---------------------------------------------------------------------------
# 5. Coarse-graining
# ---------------------------------------------------------------------------

class TestCoarseGraining:
    def test_coarse_grain_uniform(self):
        """Coarse-graining a uniform distribution should preserve uniformity."""
        density = np.ones((1, 6))
        cg = coarse_grain_two_site(density)
        assert cg.shape == (1, 3)
        np.testing.assert_allclose(cg, 2.0)

    def test_coarse_grain_sums(self):
        """Sum over cells should equal sum over sites."""
        density = np.random.rand(1, 10)
        cg = coarse_grain_two_site(density)
        assert abs(np.sum(density) - np.sum(cg)) < 1e-14


# ---------------------------------------------------------------------------
# 6. Center-of-mass
# ---------------------------------------------------------------------------

class TestCenterOfMass:
    def test_com_delta_function(self):
        """COM of a delta function should be at the correct position."""
        n_cells = 5
        for ell0 in range(n_cells):
            density = np.zeros((1, n_cells))
            density[0, ell0] = 1.0
            Z, X, width = compute_com_phase(density)
            assert abs(X[0] - ell0) < 1e-10, f"ell0={ell0}, X={X[0]}"

    def test_com_uniform_distribution(self):
        """Uniform distribution should have |Z| ≈ 0 (ill-defined COM)."""
        n_cells = 5
        density = np.full((1, n_cells), 1.0 / n_cells)
        Z, X, width = compute_com_phase(density)
        # |Z| should be tiny for uniform distribution
        assert abs(Z[0]) < 1e-14, f"|Z| = {abs(Z[0])} for uniform distribution"

    def test_com_gaussian(self):
        """COM of a Gaussian should be at the peak."""
        n_cells = 10
        ell = np.arange(n_cells, dtype=np.float64)
        mu = 3.5
        sigma = 1.0
        density = np.exp(-0.5 * ((ell - mu) / sigma) ** 2)
        density /= np.sum(density)
        density = density[None, :]  # (1, n_cells)
        Z, X, width = compute_com_phase(density)
        assert abs(X[0] - mu) < 0.2, f"COM off: expected ~{mu}, got {X[0]}"

    def test_com_periodic_wrap(self):
        """A distribution peaked near the boundary should wrap correctly."""
        n_cells = 10
        density = np.zeros((2, n_cells))
        density[0, 1] = 1.0  # near left
        density[1, 8] = 1.0  # near right
        Z, X, width = compute_com_phase(density)
        assert abs(X[0] - 1.0) < 1e-10
        # X[1] should be 8 or -2 unwrapped — the phase method returns the
        # principal value, which for a single peak at ℓ=8 is 8
        assert abs(X[1] - 8.0) < 1e-10


# ---------------------------------------------------------------------------
# 7. Integration: compute_all_defects
# ---------------------------------------------------------------------------

class TestComputeAllDefects:
    def test_output_shapes(self, tsm_l6_u10, gs_u10):
        """compute_all_defects should produce correct shapes."""
        psi_wp = create_hole_wavepacket(
            tsm_l6_u10.model_N, tsm_l6_u10.model_Nm1,
            gs_u10.state, sigma=1.2, k0=0.0,
        )
        times = np.array([0.0, 0.5, 1.0])
        states_N = [gs_u10.state] * 3
        states_hole = [psi_wp] * 3

        obs_N = measure_all_per_site(tsm_l6_u10.model_N, times, states_N)
        obs_hole = measure_all_per_site(tsm_l6_u10.model_Nm1, times, states_hole)
        defect = compute_all_defects(obs_N, obs_hole)

        assert defect.h_j.shape == (3, 6)
        assert defect.s_j.shape == (3, 6)
        assert defect.h_bar.shape == (3, 3)
        assert defect.s_bar.shape == (3, 3)
        assert defect.X_h.shape == (3,)
        assert defect.X_s.shape == (3,)
        assert defect.sum_h.shape == (3,)
        assert defect.sum_s.shape == (3,)


# ---------------------------------------------------------------------------
# 8. U=0 full evolution (smoke integration test)
# ---------------------------------------------------------------------------

class TestU0Evolution:
    def test_u0_evolution_identity(self, tsm_l6_u0, gs_u0):
        """At U=0, evolving for a short time, h_j and s_j should remain identical."""
        from src.evolution import evolve_midpoint_krylov  # noqa: E402

        phi0 = 5.0 * np.pi / 3.0
        R_delta = 0.4
        delta_fixed = R_delta * np.cos(phi0)
        Delta_fixed = 5.0 + 2.1 * np.sin(phi0)

        def delta_of_tau(tau):
            return delta_fixed

        def Delta_of_tau(tau):
            return Delta_fixed

        psi_wp = create_hole_wavepacket(
            tsm_l6_u0.model_N, tsm_l6_u0.model_Nm1,
            gs_u0.state, sigma=1.2, k0=np.pi / 2,
        )

        T = 2.0
        dt = 0.1

        ev_N = evolve_midpoint_krylov(
            tsm_l6_u0.model_N, gs_u0.state, T, dt,
            delta_of_tau, Delta_of_tau, save_interval=0.5,
        )
        ev_hole = evolve_midpoint_krylov(
            tsm_l6_u0.model_Nm1, psi_wp, T, dt,
            delta_of_tau, Delta_of_tau, save_interval=0.5,
        )

        obs_N = measure_all_per_site(tsm_l6_u0.model_N, ev_N.times, ev_N.states)
        obs_hole = measure_all_per_site(tsm_l6_u0.model_Nm1, ev_hole.times, ev_hole.states)
        defect = compute_all_defects(obs_N, obs_hole)

        max_diff = np.max(np.abs(defect.h_j - defect.s_j))
        # At U=0, the spin-↓ sector is a spectator for a spin-↑ hole,
        # so h_j and s_j should be identical at all times
        assert max_diff < 1e-12, f"U=0 h_j ≠ s_j: max diff = {max_diff}"
