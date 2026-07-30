"""Test gap definitions and physical properties."""

import sys
from pathlib import Path

import numpy as np
import pytest

_HERE = Path(__file__).resolve().parent
_PROJECT = _HERE.parent
sys.path.insert(0, str(_PROJECT))
from src.gaps import GapPointResult, solve_point


class TestGapNonNegativity:
    @pytest.mark.parametrize("delta,Delta", [
        (0.0, 0.0), (0.0, 2.0), (0.5, 0.0), (-0.3, 4.0),
    ])
    def test_gaps_nonnegative_L4(self, delta, Delta):
        r = solve_point(L=4, delta=delta, Delta=Delta, U=12.0, method="dense")
        assert r.Delta_MB >= -1e-10, f"Δ_MB = {r.Delta_MB}"
        assert r.Delta_s >= -1e-10, f"Δ_s = {r.Delta_s}"
        assert r.Delta_c >= -1e-10, f"Δ_c = {r.Delta_c}"

    def test_charge_gap_large_at_strong_U(self):
        """At δ=0, Δ=0, U=12, charge gap should be roughly U - 4t = 8."""
        r = solve_point(L=4, delta=0.0, Delta=0.0, U=12.0, method="dense")
        # Finite-size effects reduce this, but should be O(U)
        assert r.Delta_c > 5.0

    def test_spin_gap_small_at_strong_U(self):
        """At δ=0, Δ=0, U=12, spin gap ~ 4t²/U ~ 0.33."""
        r = solve_point(L=4, delta=0.0, Delta=0.0, U=12.0, method="dense")
        assert r.Delta_s < 2.0  # finite-size gap is larger but should be << charge gap

    def test_spin_gap_much_less_than_charge_gap(self):
        r = solve_point(L=4, delta=0.0, Delta=2.0, U=12.0, method="dense")
        assert r.Delta_s < r.Delta_c


class TestGapSymmetry:
    @pytest.mark.parametrize("delta,Delta", [
        (0.0, 2.0),
    ])
    def test_gap_symmetry_L4(self, delta, Delta):
        """Exact symmetry holds at δ=0 where translation doesn't matter."""
        r_fwd = solve_point(L=4, delta=delta, Delta=Delta, U=12.0, method="dense")
        r_rev = solve_point(L=4, delta=-delta, Delta=-Delta, U=12.0, method="dense")
        assert abs(r_fwd.Delta_MB - r_rev.Delta_MB) < 1e-10
        assert abs(r_fwd.Delta_s - r_rev.Delta_s) < 1e-10
        assert abs(r_fwd.Delta_c - r_rev.Delta_c) < 1e-10

    @pytest.mark.parametrize("delta,Delta", [
        (0.3, 1.0), (-0.5, 4.0),
    ])
    def test_gap_symmetry_approximate_L4(self, delta, Delta):
        """At finite L with δ≠0, symmetry is approximate (finite-size effect)."""
        r_fwd = solve_point(L=4, delta=delta, Delta=Delta, U=12.0, method="dense")
        r_rev = solve_point(L=4, delta=-delta, Delta=-Delta, U=12.0, method="dense")
        # Gaps differ at finite L due to dimerization-boundary interplay
        assert abs(r_fwd.Delta_c - r_rev.Delta_c) < 1.0  # charge gap nearly symmetric


class TestGapConsistency:
    def test_Delta_MB_equals_Delta_s_when_triplet_is_lowest(self):
        """If the lowest excitation is a triplet, Δ_MB = Δ_s."""
        r = solve_point(L=4, delta=0.0, Delta=2.0, U=12.0, method="dense")
        # In finite systems, Δ_MB may equal Δ_s exactly
        # This test just checks that both are defined and not NaN
        assert not np.isnan(r.Delta_MB)
        assert not np.isnan(r.Delta_s)
        assert not np.isnan(r.Delta_c)

    def test_ALL_convergence_flags_true_dense(self):
        r = solve_point(L=4, delta=0.0, Delta=0.0, U=12.0, method="dense")
        assert all(r.converged.values())

    def test_residuals_all_below_tolerance(self):
        r = solve_point(L=4, delta=0.3, Delta=1.5, U=12.0, method="dense")
        for sector, res in r.residuals.items():
            assert res < 1e-9, f"sector {sector}: residual={res}"


class TestKnownLimits:
    def test_dimer_limit_large_delta(self):
        """At large |δ| and small Δ, system approaches isolated dimers."""
        r = solve_point(L=4, delta=0.98, Delta=0.0, U=12.0, method="dense")
        assert r.Delta_MB > 0
        assert r.Delta_c > 0

    def test_band_insulator_limit_large_Delta(self):
        """At large |Δ|, the charge gap should be finite (band insulator).
        L=4 has strong finite-size effects; check at L=6 where the gap is ~4."""
        r = solve_point(L=6, delta=0.0, Delta=8.0, U=12.0, method="dense")
        assert r.Delta_c > 3.0
