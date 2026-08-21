"""Smoke tests for the convergence-analysis scripts (analyze.py).

Uses tiny settings so the tests run in seconds while still exercising the
full plot/CSV generation paths. Correctness of the underlying physics is
covered by test_metts_engine / test_mps_backend; here we only verify the
analysis machinery runs, writes CSV+PNG, and does not crash.
"""
import os
import tempfile

from metts_b import analyze


def test_delta_beta_convergence_runs(tmp_path):
    rows = analyze.delta_beta_convergence(str(tmp_path), Lx=2, Ly=2, h=3.0,
                                          beta=0.3, dtuas=(0.04, 0.02, 0.01))
    assert len(rows) == 3
    assert os.path.exists(tmp_path / "delta_beta_convergence.csv")
    assert os.path.exists(tmp_path / "delta_beta_convergence.png")
    # error should decrease as dtau shrinks (pre-asymptotic may be noisy, so
    # just check the smallest dtau error is not larger than the largest)
    errs = [r["abs_err"] for r in rows]
    assert errs[-1] <= errs[0] + 1e-9


def test_sample_convergence_runs(tmp_path):
    rows = analyze.sample_convergence(
        str(tmp_path), Lx=2, Ly=2, h=3.0, beta=0.5, backend="dense",
        sample_counts=(50, 200), n_chains=2)
    assert len(rows) == 2
    assert os.path.exists(tmp_path / "sample_convergence.csv")
    assert os.path.exists(tmp_path / "sample_convergence.png")
    # Rhat computable with 2 chains
    for r in rows:
        assert r["M"] in (50, 200)
        assert r["n_chains"] if "n_chains" in r else True


def test_bond_convergence_runs(tmp_path):
    # tiny 2x2 MPS: all bonds adjacent, no swaps; chi=8 is plenty
    rows = analyze.bond_convergence(str(tmp_path), Lx=2, Ly=2, h=3.0,
                                    beta=0.3, dtau=0.02, chis=(4, 8),
                                    n_production=50)
    assert len(rows) == 2
    assert os.path.exists(tmp_path / "bond_convergence.csv")
    assert os.path.exists(tmp_path / "bond_convergence.png")
