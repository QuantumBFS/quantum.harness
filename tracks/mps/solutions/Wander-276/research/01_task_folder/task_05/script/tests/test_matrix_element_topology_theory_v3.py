"""Executable theory tests for the v3 manuscript derivations."""

from __future__ import annotations

from verify_matrix_element_topology_theory_v3 import (
    gauge_and_gram_check,
    periodic_unitary_chern_check,
    wick_identity_check,
)


def test_wick_coefficients_match_direct_monte_carlo() -> None:
    result = wick_identity_check(samples=8_000)
    assert result["relative_error"] < 0.065


def test_gauge_invariance_and_gram_reduction() -> None:
    result = gauge_and_gram_check()
    assert result["R4_error"] < 1e-10
    assert result["tensor_error"] < 1e-10
    assert result["gram_spectrum_error"] < 1e-10


def test_periodic_unitary_orbit_keeps_synthetic_chern() -> None:
    result = periodic_unitary_chern_check(mesh=20)
    assert result["chern_error"] < 1e-10
    assert result["minimum_branch_margin"] > 0.0
