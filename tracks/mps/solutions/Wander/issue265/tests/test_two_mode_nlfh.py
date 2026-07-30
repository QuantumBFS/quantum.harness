from __future__ import annotations

import unittest

import numpy as np

from src.two_mode_nlfh import (
    TwoModeNoiseFaces,
    TwoModeParams,
    TwoModeState,
    conservative_two_mode_step,
    ensemble_transfer_logz,
    equilibrium_variance_sanity,
    generate_noise_panel,
    lazy_noise_panel,
    paired_error_improvement,
    simulate_two_mode,
    simulate_two_mode_ensemble,
    two_mode_flux,
)


class TwoModeNLFHTests(unittest.TestCase):
    def test_equal_couplings_diagonalize_to_opposite_burgers_modes(self) -> None:
        m = np.array([-0.2, 0.1, 0.3])
        phi = np.array([0.4, -0.1, 0.2])
        jm, jphi = two_mode_flux(
            m, phi, lambda_m=1.0, lambda_phi=1.0
        )
        up, um = m + phi, m - phi
        np.testing.assert_allclose(jm + jphi, 0.5 * up**2)
        np.testing.assert_allclose(jm - jphi, -0.5 * um**2)

    def test_conservative_step_preserves_spatial_sums_without_noise(self) -> None:
        rng = np.random.default_rng(3)
        state = TwoModeState(
            m=rng.normal(scale=0.1, size=64),
            phi=rng.normal(scale=0.1, size=64),
        )
        advanced = conservative_two_mode_step(
            state,
            dx=1.0,
            dt=1e-3,
            params=TwoModeParams(
                Dm=1.0,
                Dphi=1.0,
                lambda_m=1.0,
                lambda_phi=1.0,
            ),
            noise_faces=None,
        )
        self.assertAlmostEqual(float(advanced.m.sum()), float(state.m.sum()), places=12)
        self.assertAlmostEqual(
            float(advanced.phi.sum()), float(state.phi.sum()), places=12
        )

    def test_explicit_step_rejects_advective_cfl_violation(self) -> None:
        state = TwoModeState(
            m=np.full(8, 10.0),
            phi=np.full(8, 10.0),
        )
        with self.assertRaisesRegex(ValueError, "advective"):
            conservative_two_mode_step(
                state,
                dx=1.0,
                dt=0.1,
                params=TwoModeParams(
                    Dm=0.1,
                    Dphi=0.1,
                    lambda_m=1.0,
                    lambda_phi=1.0,
                ),
                noise_faces=None,
            )

    def test_spin_flip_equivariance_with_matched_noise(self) -> None:
        x = np.linspace(-8.0, 8.0, 64, endpoint=False)
        t = np.array([0.0, 0.001, 0.002])
        m0 = 0.1 * np.sin(2.0 * np.pi * np.arange(x.size) / x.size)
        phi0 = 0.07 * np.cos(2.0 * np.pi * np.arange(x.size) / x.size)
        rng = np.random.default_rng(7)
        noise = TwoModeNoiseFaces(
            m=rng.normal(size=(2, x.size)),
            phi=rng.normal(size=(2, x.size)),
        )
        params = TwoModeParams(
            Dm=0.8,
            Dphi=1.1,
            lambda_m=0.9,
            lambda_phi=0.6,
            chi=0.25,
        )
        result = simulate_two_mode(
            x=x,
            t=t,
            m0=m0,
            phi0=phi0,
            params=params,
            dt_internal=0.001,
            noise_faces=noise,
        )
        flipped = simulate_two_mode(
            x=x,
            t=t,
            m0=-m0,
            phi0=phi0,
            params=params,
            dt_internal=0.001,
            noise_faces=TwoModeNoiseFaces(m=-noise.m, phi=noise.phi),
        )
        np.testing.assert_allclose(flipped.m, -result.m, atol=1e-12)
        np.testing.assert_allclose(flipped.phi, result.phi, atol=1e-12)

    def test_equilibrium_gaussian_variance_sanity(self) -> None:
        audit = equilibrium_variance_sanity(
            params=TwoModeParams(
                Dm=0.8,
                Dphi=1.1,
                lambda_m=1.0,
                lambda_phi=1.0,
                chi=0.25,
            ),
            n_cells=64,
            n_ensemble=1024,
            n_steps=50,
            dt=2e-4,
            dx=1.0,
            seed=11,
        )
        self.assertLess(float(audit["m_variance_relative_error"]), 0.02)
        self.assertLess(float(audit["phi_variance_relative_error"]), 0.02)
        self.assertLess(float(audit["max_conservation_error"]), 1e-12)
        self.assertLess(abs(float(audit["magnetization_current_skewness"])), 0.05)

    def test_ensemble_observables_are_reproducible(self) -> None:
        x = np.linspace(-4.0, 4.0, 16, endpoint=False)
        t = np.array([0.0, 0.001, 0.002])
        parameters = TwoModeParams(
            Dm=0.8,
            Dphi=0.9,
            lambda_m=0.7,
            lambda_phi=0.6,
        )
        kwargs = {
            "x": x,
            "t": t,
            "m0": np.zeros_like(x),
            "phi0": np.zeros_like(x),
            "params": parameters,
            "dt_internal": 0.001,
            "n_ensemble": 8,
            "seed": 19,
        }
        first = simulate_two_mode_ensemble(**kwargs)
        second = simulate_two_mode_ensemble(**kwargs)
        np.testing.assert_allclose(first.mean_m, second.mean_m)
        np.testing.assert_allclose(first.mean_jm, second.mean_jm)
        np.testing.assert_allclose(first.cmm_origin, second.cmm_origin)
        np.testing.assert_allclose(first.jm_cumulants, second.jm_cumulants)
        np.testing.assert_allclose(
            first.jm_cumulants_time[-1], first.jm_cumulants
        )
        np.testing.assert_allclose(
            first.integrated_jm_time[:, -1], first.integrated_jm
        )

    def test_time_resolved_transfer_logz_has_exact_identities(self) -> None:
        x = np.linspace(-4.0, 4.0, 16, endpoint=False)
        t = np.array([0.0, 0.001, 0.002])
        ensemble = simulate_two_mode_ensemble(
            x=x,
            t=t,
            m0=np.zeros_like(x),
            phi0=np.zeros_like(x),
            params=TwoModeParams(
                Dm=0.8,
                Dphi=0.9,
                lambda_m=0.7,
                lambda_phi=0.6,
            ),
            dt_internal=0.001,
            n_ensemble=16,
            seed=29,
        )
        gamma = np.array([-0.4, -0.2, 0.0, 0.2, 0.4])
        logz = ensemble_transfer_logz(ensemble, gamma)
        np.testing.assert_array_equal(logz[:, 2], 0.0)
        np.testing.assert_allclose(logz[:, :2], np.conj(logz[:, -1:-3:-1]))
        np.testing.assert_allclose(logz[0], 0.0)

    def test_supplied_noise_panel_gives_exact_common_random_numbers(self) -> None:
        x = np.linspace(-4.0, 4.0, 16, endpoint=False)
        t = np.array([0.0, 0.001, 0.002])
        params = TwoModeParams(
            Dm=0.8,
            Dphi=0.9,
            lambda_m=0.7,
            lambda_phi=0.6,
        )
        panel = generate_noise_panel(
            seed=31,
            n_ensemble=4,
            n_steps=2,
            n_cells=x.size,
        )
        kwargs = {
            "x": x,
            "t": t,
            "m0": np.zeros_like(x),
            "phi0": np.zeros_like(x),
            "params": params,
            "dt_internal": 0.001,
            "n_ensemble": 4,
            "noise_panel": panel,
        }
        first = simulate_two_mode_ensemble(**kwargs, seed=1)
        second = simulate_two_mode_ensemble(**kwargs, seed=999)
        np.testing.assert_array_equal(first.mean_m, second.mean_m)
        np.testing.assert_array_equal(first.jm_cumulants, second.jm_cumulants)
        self.assertEqual(first.seed, 31)

    def test_lazy_noise_panel_replays_without_materializing_global_array(self) -> None:
        x = np.linspace(-4.0, 4.0, 16, endpoint=False)
        t = np.array([0.0, 0.001, 0.002])
        panel = lazy_noise_panel(
            seed=37,
            n_ensemble=4,
            n_steps=2,
            n_cells=x.size,
        )
        params = TwoModeParams(
            Dm=0.8,
            Dphi=0.9,
            lambda_m=0.7,
            lambda_phi=0.6,
        )
        kwargs = {
            "x": x,
            "t": t,
            "m0": np.zeros_like(x),
            "phi0": np.zeros_like(x),
            "params": params,
            "dt_internal": 0.001,
            "n_ensemble": 4,
            "seed": 999,
            "noise_panel": panel,
        }
        first = simulate_two_mode_ensemble(**kwargs)
        second = simulate_two_mode_ensemble(**kwargs)
        np.testing.assert_array_equal(first.mean_m, second.mean_m)
        self.assertFalse(hasattr(panel, "face_m"))

    def test_paired_bootstrap_reports_positive_two_mode_improvement(self) -> None:
        result = paired_error_improvement(
            np.array([0.10, 0.12, 0.09, 0.11, 0.13]),
            np.array([0.05, 0.07, 0.04, 0.06, 0.07]),
            n_replicates=1000,
            confidence=0.95,
            seed=23,
        )
        self.assertGreater(float(result["relative_improvement"]), 0.3)
        self.assertGreater(float(result["paired_ci_low"]), 0.0)


if __name__ == "__main__":
    unittest.main()
