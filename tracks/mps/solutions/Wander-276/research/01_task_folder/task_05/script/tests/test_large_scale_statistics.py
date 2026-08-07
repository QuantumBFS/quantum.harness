from __future__ import annotations

import numpy as np

from lgeth.statistics import (
    connected_form_factor,
    fit_size_models,
    matrix_bootstrap_band,
    sample_gue_spectra,
    sample_poisson_spectra,
    spectral_rigidity,
    unfold_spectra,
)


def test_simultaneous_band_contract() -> None:
    rng = np.random.default_rng(20260728700)
    curves = rng.normal(size=(40, 12))
    band = matrix_bootstrap_band(curves, 500, 20260728701)
    assert band.mean.shape == (12,)
    assert np.all(band.lower <= band.mean)
    assert np.all(band.mean <= band.upper)
    assert band.critical_value > 1.0
    groups = np.repeat(np.arange(8), 5)
    hierarchical = matrix_bootstrap_band(
        curves,
        500,
        20260728702,
        groups=groups,
    )
    assert hierarchical.units == 8
    assert hierarchical.method == "hierarchical_seed_block_bootstrap"


def test_gue_is_more_rigid_than_poisson() -> None:
    poisson = unfold_spectra(
        sample_poisson_spectra(240, 60, 20260728703),
        "ensemble_cdf",
    )
    gue = unfold_spectra(
        sample_gue_spectra(240, 60, 20260728704),
        "ensemble_cdf",
    )
    lengths = (1.0, 2.0, 3.0, 4.0)
    poisson_rigidity = spectral_rigidity(poisson, lengths)
    gue_rigidity = spectral_rigidity(gue, lengths)
    assert poisson_rigidity[-1] > gue_rigidity[-1]
    form = connected_form_factor(gue, (0.0, 0.2, 0.5, 1.0))
    assert abs(form[0]) < 1e-12
    assert np.all(np.isfinite(form))


def test_finite_size_model_selection_recovers_half_power() -> None:
    D = np.asarray([16, 32, 64, 128, 256, 512, 1024], dtype=float)
    values = 0.02 + 1.5 * D ** -0.5
    sigma = np.full_like(D, 0.003)
    fits = fit_size_models(D, values, sigma)
    assert fits["best_by_loo"] in {"D^-1/2", "free"}
    assert abs(fits["models"]["free"]["exponent"] - 0.5) < 0.05
