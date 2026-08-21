"""Analytic and empirical form-factor tests for the v2 expansion."""

from __future__ import annotations

import numpy as np
import pytest

from lgeth.form_factors import (
    atom_raw_decomposition,
    degenerate_energy_form_factor,
    finite_jacobi_form_factor,
    form_factor_parts,
)
from lgeth.jacobi import sample_jacobi_compression
from lgeth.statistics import unfold_spectra


def test_exact_degenerate_energy_is_raw_constant_and_connected_zero():
    times = np.linspace(0.0, 4.0, 41)
    parts = degenerate_energy_form_factor(50, times)
    assert np.allclose(parts.raw, 50.0, atol=1e-14)
    assert np.allclose(parts.disconnected, 50.0, atol=1e-14)
    assert np.allclose(parts.connected, 0.0, atol=1e-14)
    assert parts.normalization == 50


def test_form_factor_decomposition_closes():
    spectra = np.array(
        [
            [-1.0, 0.2, 0.9],
            [-0.8, 0.0, 1.1],
            [-0.7, 0.1, 0.8],
        ]
    )
    parts = form_factor_parts(
        spectra,
        np.linspace(0.0, 2.0, 9),
        phase_scale=2.0 * np.pi,
    )
    assert np.allclose(
        parts.raw,
        parts.disconnected + parts.connected,
        atol=1e-14,
    )
    assert np.all(parts.connected >= -1e-14)


def test_form_factor_rejects_invalid_inputs():
    times = np.linspace(0.0, 1.0, 5)
    for invalid in (
        np.ones(5),
        np.ones((0, 4)),
        np.ones((3, 0)),
        np.array([[0.0, np.nan]]),
    ):
        try:
            form_factor_parts(invalid, times)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid spectra were accepted")


def test_finite_jacobi_connected_starts_at_zero_and_reaches_plateau():
    result = finite_jacobi_form_factor(
        16,
        80,
        np.array([0.0, 4.0]),
        quadrature_order=256,
    )
    assert abs(result.connected_continuous[0]) < 2e-10
    assert result.connected_continuous[-1] > 0.95
    assert result.plateau_full == pytest.approx(1.0)


def test_boundary_atoms_suppress_full_connected_plateau_exactly():
    result = finite_jacobi_form_factor(
        800,
        680,
        np.array([0.0, 4.0]),
        quadrature_order=768,
    )
    assert result.interior_dimension == 560
    assert result.atom_count_each == 120
    assert np.allclose(
        result.connected_full,
        (560.0 / 800.0) * result.connected_continuous,
        atol=2e-10,
    )
    assert result.plateau_full == pytest.approx(0.7)


def test_raw_atom_decomposition_closes():
    decomposition = atom_raw_decomposition(
        np.array([[-0.4, 0.3], [-0.2, 0.6]]),
        minus_atoms=1,
        plus_atoms=1,
        times=np.linspace(0.0, 2.0, 17),
    )
    assert np.allclose(
        decomposition["full"],
        decomposition["atom_atom"]
        + decomposition["atom_continuum"]
        + decomposition["continuum_continuum"],
        atol=1e-14,
    )


def test_finite_jacobi_curve_matches_independent_monte_carlo():
    times = np.linspace(0.25, 2.5, 46)
    spectra = sample_jacobi_compression(
        r=16,
        M=80,
        samples=1500,
        seed=20260728191,
    )
    empirical = form_factor_parts(
        unfold_spectra(spectra, "ensemble_cdf"),
        times,
    ).connected
    analytic = finite_jacobi_form_factor(
        16,
        80,
        times,
        quadrature_order=256,
    ).connected_continuous
    assert np.max(np.abs(empirical - analytic)) < 0.075


def test_rank50_quadrature_is_stable_on_registered_time_window():
    times = np.linspace(0.0, 3.0, 61)
    first = finite_jacobi_form_factor(
        50,
        170,
        times,
        quadrature_order=384,
    )
    second = finite_jacobi_form_factor(
        50,
        170,
        times,
        quadrature_order=512,
    )
    assert (
        np.max(
            np.abs(
                first.connected_continuous
                - second.connected_continuous
            )
        )
        < 5e-5
    )
