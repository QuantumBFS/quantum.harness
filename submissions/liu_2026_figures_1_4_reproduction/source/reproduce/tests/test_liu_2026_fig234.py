"""Physics, numerics, provenance, cache, and CLI tests for Liu Fig. 2--4."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
HARNESS_PACKAGE = ROOT / "tracks/qcs/solutions"
PACKAGE_ROOT = (
    HARNESS_PACKAGE if HARNESS_PACKAGE.exists() else Path(__file__).parents[1]
)
MODULE_PATH = PACKAGE_ROOT / "liu_2026_fig234_reproduction.py"
EXPERIMENTAL_PATH = PACKAGE_ROOT / "liu_2026_experimental_analysis.py"
EXPERIMENTAL_SPEC = importlib.util.spec_from_file_location(
    "liu_experimental", EXPERIMENTAL_PATH
)
assert (
    EXPERIMENTAL_SPEC is not None
    and EXPERIMENTAL_SPEC.loader is not None
)
experimental = importlib.util.module_from_spec(EXPERIMENTAL_SPEC)
sys.modules[EXPERIMENTAL_SPEC.name] = experimental
EXPERIMENTAL_SPEC.loader.exec_module(experimental)

SPEC = importlib.util.spec_from_file_location("liu_fig234", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
liu = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = liu
SPEC.loader.exec_module(liu)

NOISE_PATH = PACKAGE_ROOT / "liu_2026_noise_modules.py"
NOISE_SPEC = importlib.util.spec_from_file_location("liu_noise", NOISE_PATH)
assert NOISE_SPEC is not None and NOISE_SPEC.loader is not None
noise = importlib.util.module_from_spec(NOISE_SPEC)
sys.modules[NOISE_SPEC.name] = noise
NOISE_SPEC.loader.exec_module(noise)


def computational_unitary(diagonal: np.ndarray) -> np.ndarray:
    unitary = np.eye(10, dtype=np.complex128)
    unitary[np.ix_(liu.P_IDX, liu.P_IDX)] = np.diag(diagonal)
    return unitary


class PhysicsAndFidelityTests(unittest.TestCase):
    def test_01_basis_and_projector_completeness(self) -> None:
        self.assertEqual(len(liu.BASIS), 10)
        self.assertEqual(liu.P_IDX.tolist(), [0, 2, 5, 8])
        self.assertEqual(liu.Q_IDX.tolist(), [1, 3, 4, 6, 7, 9])
        self.assertEqual(set(liu.P_IDX) | set(liu.Q_IDX), set(range(10)))
        self.assertFalse(set(liu.P_IDX) & set(liu.Q_IDX))

    def test_02_hamiltonian_hermiticity_and_appendix_c_couplings(self) -> None:
        model = liu.Model()
        expected = {
            ("|0r>", "|01>"): 1.0,
            ("|r'1>", "|01>"): -1.0,
            ("|r0>", "|10>"): 1.0,
            ("|1r'>", "|10>"): -1.0,
            ("|W'>", "|00>"): -np.sqrt(2.0),
            ("|W>", "|11>"): np.sqrt(2.0),
        }
        for pair, value in expected.items():
            self.assertAlmostEqual(
                liu.SIGMA_PLUS[liu.INDEX[pair[0]], liu.INDEX[pair[1]]],
                value,
            )
        for control in (0.0, model.omega0, model.omega0 * (0.2 - 0.7j)):
            hamiltonian = liu.hamiltonian_numpy(control, model)
            self.assertLess(
                np.linalg.norm(hamiltonian - hamiltonian.conj().T), 1e-12
            )

    def test_03_detuning_sign_convention(self) -> None:
        positive = liu.hamiltonian_numpy(0.0, liu.Model(detuning_sign=1))
        negative = liu.hamiltonian_numpy(0.0, liu.Model(detuning_sign=-1))
        self.assertTrue(
            np.allclose(
                positive[liu.INDEX["|W'>"], liu.INDEX["|W'>"]],
                liu.Model().delta_r,
            )
        )
        self.assertTrue(np.allclose(positive, -negative))

    def test_04_atom_exchange_symmetry_01_10(self) -> None:
        h = liu.hamiltonian_numpy(13.0 + 2.0j)
        sector_01 = h[np.ix_([2, 3, 4], [2, 3, 4])]
        sector_10 = h[np.ix_([5, 6, 7], [5, 6, 7])]
        self.assertTrue(np.allclose(sector_01, sector_10))

    def test_05_propagator_unitarity(self) -> None:
        basis = liu.WaveformBasis()
        times = np.linspace(0.0, basis.model.duration, 101)
        midpoints = 0.5 * (times[:-1] + times[1:])
        _, _, control = basis.values_numpy(liu.seed_waveform(basis), midpoints)
        unitary = liu.propagate_piecewise_numpy(times, control)
        self.assertLess(
            np.linalg.norm(unitary.conj().T @ unitary - np.eye(10)), 1e-10
        )

    def test_06_adaptive_midpoint_grid_convergence(self) -> None:
        basis = liu.WaveformBasis()
        rows, _ = liu.grid_comparison(basis, liu.seed_waveform(basis))
        errors = np.asarray(
            [row["normalized_unitary_difference"] for row in rows]
        )
        ratios = errors[:-1] / errors[1:]
        self.assertTrue(np.all((ratios > 3.0) & (ratios < 5.0)))

    def test_07_perfect_cz_and_global_phase_invariance(self) -> None:
        exact = computational_unitary(np.asarray([1, 1, 1, -1]))
        global_phase = np.exp(0.37j) * exact
        for unitary in (exact, global_phase):
            metrics = liu.gate_metrics_numpy(unitary)
            self.assertAlmostEqual(metrics["fidelity"], 1.0, places=12)
            self.assertAlmostEqual(metrics["cz_phase_error"], 0.0, places=12)

    def test_08_known_small_phase_error_formula(self) -> None:
        epsilon = 0.03
        unitary = computational_unitary(
            np.asarray([1, 1, 1, -np.exp(1j * epsilon)])
        )
        expected = 0.7 + 0.3 * np.cos(epsilon)
        self.assertAlmostEqual(
            liu.gate_metrics_numpy(unitary)["fidelity"], expected, places=13
        )

    def test_09_known_leakage_fidelity(self) -> None:
        alpha = 0.1
        unitary = computational_unitary(np.asarray([1, 1, 1, -1]))
        rotation = np.eye(10, dtype=np.complex128)
        p = liu.INDEX["|00>"]
        q = liu.INDEX["|W'>"]
        rotation[p, p] = rotation[q, q] = np.cos(alpha)
        rotation[q, p] = np.sin(alpha)
        rotation[p, q] = -np.sin(alpha)
        unitary = rotation @ unitary
        metrics = liu.gate_metrics_numpy(unitary)
        expected = ((3 + np.cos(alpha)) ** 2 + 3 + np.cos(alpha) ** 2) / 20
        self.assertAlmostEqual(metrics["fidelity"], expected, places=13)
        self.assertAlmostEqual(metrics["leakage"][0], np.sin(alpha) ** 2)

    def test_10_local_z_conventions_are_distinct(self) -> None:
        theta = 0.23
        unitary = computational_unitary(
            np.asarray(
                [1, np.exp(1j * theta), np.exp(1j * theta),
                 -np.exp(2j * theta)]
            )
        )
        fixed = liu.gate_metrics_numpy(unitary, "fixed_standard_cz")
        equivalent = liu.gate_metrics_numpy(
            unitary, "pointwise_cz_equivalent"
        )
        nominal = liu.gate_metrics_numpy(
            unitary, "fixed_nominal_virtual_z", nominal_virtual_z=theta
        )
        self.assertLess(fixed["fidelity"], 1.0)
        self.assertAlmostEqual(equivalent["fidelity"], 1.0, places=12)
        self.assertAlmostEqual(nominal["fidelity"], 1.0, places=12)

    def test_11_branch_safe_phase_residual_rejects_false_sine_root(self) -> None:
        near_false_root = np.asarray([1, 1, 1, np.exp(1j * 1e-8)])
        residual = liu.nonlinear_phase_invariant(near_false_root)
        self.assertLess(abs(residual["sin"]), 2e-8)
        self.assertGreater(residual["one_minus_cos"], 1.9)
        ideal = liu.nonlinear_phase_invariant(np.asarray([1, 1, 1, -1]))
        self.assertAlmostEqual(ideal["one_minus_cos"], 0.0)

    def test_12_no_silent_probability_clipping(self) -> None:
        invalid = computational_unitary(np.asarray([1.01, 1, 1, -1]))
        with self.assertRaises(FloatingPointError):
            liu.gate_metrics_numpy(invalid)

    def test_13_population_definition_sums_01_channels(self) -> None:
        basis = liu.WaveformBasis()
        times = np.linspace(0.0, basis.model.duration, 41)
        trajectory = liu.propagate_adaptive(
            liu.make_control_interpolant(basis, liu.seed_waveform(basis)),
            times=times,
        )
        populations = liu.rydberg_populations_from_trajectory(trajectory)
        total = (
            populations["P01_to_0r_diagnostic"]
            + populations["P01_to_rprime1_diagnostic"]
        )
        self.assertTrue(
            np.allclose(populations["P01_total_rydberg"], total)
        )
        p10 = (
            abs(
                trajectory[
                    :, liu.INDEX["|r0>"], liu.INDEX["|10>"]
                ]
            )
            ** 2
            + abs(
                trajectory[
                    :, liu.INDEX["|1r'>"], liu.INDEX["|10>"]
                ]
            )
            ** 2
        )
        self.assertTrue(np.allclose(populations["P01_total_rydberg"], p10))

    def test_14_intensity_amplitude_square_root(self) -> None:
        self.assertAlmostEqual(liu.intensity_to_amplitude_ratio(1.21), 1.1)
        with self.assertRaises(ValueError):
            liu.intensity_to_amplitude_ratio(-0.1)

    def test_14b_source_constrained_envelope_and_phase_bins(self) -> None:
        basis = liu.SourceConstrainedPhaseBasis(n_coefficients=400)
        edge = 10.0 / basis.model.delta_r
        self.assertAlmostEqual(basis.edge_duration, edge)
        times = np.asarray(
            [
                0.0,
                0.5 * edge,
                edge,
                0.5 * basis.model.duration,
                basis.model.duration - edge,
                basis.model.duration,
            ]
        )
        phase = np.linspace(-0.2, 0.4, basis.n_free)
        amplitude, sampled_phase, _ = basis.values_numpy(phase, times)
        self.assertTrue(
            np.allclose(
                amplitude,
                [0.0, np.sqrt(0.5), 1.0, 1.0, 1.0, 0.0],
                atol=1e-13,
            )
        )
        self.assertAlmostEqual(sampled_phase[0], phase[0])
        self.assertAlmostEqual(sampled_phase[-1], phase[-1])
        self.assertEqual(basis.n_amplitude_free, 0)
        self.assertEqual(basis.n_phase_free, 400)

    def test_14c_source_configuration_is_explicit_not_digitized(self) -> None:
        path = PACKAGE_ROOT / "liu_2026_fig3_source_constrained_config.json"
        config = liu.load_config(path, "standard")
        self.assertEqual(config.optimizer.backend, "source_phase")
        self.assertEqual(config.optimizer.coefficients_per_channel, 400)
        self.assertEqual(
            config.optimizer.robustness_objective, "common_alpha_s11"
        )
        self.assertEqual(config.optimizer.edge_adiabatic_factor, 10.0)


@unittest.skipUnless(liu.JAX_AVAILABLE, "JAX is optional")
class JaxAndHessianTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.basis = liu.WaveformBasis()
        cls.variables = liu.seed_waveform(cls.basis)

    def test_15_jax_numpy_propagator_agreement(self) -> None:
        count = 51
        times = np.linspace(0.0, self.basis.model.duration, count)
        midpoints = 0.5 * (times[:-1] + times[1:])
        _, _, controls = self.basis.values_numpy(self.variables, midpoints)
        numpy_unitary = liu.propagate_piecewise_numpy(times, controls)
        jax_unitary = np.asarray(
            liu.propagate_piecewise_jax(
                liu.jnp.asarray(controls),
                self.basis.model.duration / (count - 1),
            )
        )
        self.assertLess(
            liu.normalized_unitary_difference(numpy_unitary, jax_unitary),
            1e-10,
        )

    def test_16_amplitude_derivative_finite_difference_vs_jvp(self) -> None:
        kernels = liu.JaxControlKernels(self.basis, nodes=51)
        diagnostics = np.asarray(
            kernels.robustness_diagnostics(liu.jnp.asarray(self.variables))
        )
        epsilon = 1e-5
        phases = []
        for scale in (1.0 - epsilon, 1.0 + epsilon):
            unitary = np.asarray(
                kernels.unitary(liu.jnp.asarray(self.variables), scale)
            )
            phases.append(
                liu.gate_metrics_numpy(unitary)["cz_phase_error"]
            )
        derivative = np.angle(
            np.exp(1j * (phases[1] - phases[0]))
        ) / (2.0 * epsilon)
        self.assertAlmostEqual(derivative, diagnostics[3], delta=1e-5)

    def test_16b_common_alpha_source_backend_shapes_are_finite(self) -> None:
        optimizer = liu.OptimizerConfig(
            backend="source_phase",
            robustness_objective="common_alpha_s11",
            coefficients_per_channel=40,
            coarse_nodes=41,
            fine_nodes=81,
            regularizer_nodes=81,
        )
        config = liu.RunConfig(optimizer=optimizer)
        basis = liu.make_basis(config)
        variables = liu.generic_seed_waveform(basis)
        kernels = liu.JaxControlKernels(
            basis, nodes=41, optimizer_config=optimizer
        )
        residual = np.asarray(
            kernels.robust_residual(liu.jnp.asarray(variables))
        )
        jacobian = np.asarray(
            kernels.robust_residual_jacobian(liu.jnp.asarray(variables))
        )
        self.assertEqual(residual.shape, (70,))
        self.assertEqual(jacobian.shape, (70, 40))
        self.assertTrue(np.all(np.isfinite(jacobian)))

    def test_17_channel_hessian_matches_direct_autodiff_small_grid(self) -> None:
        result = liu.hessian_at_resolution(
            self.basis, self.variables, n_bins=6, nodes=41
        )
        direct = liu.direct_autodiff_infidelity_hessian(result)
        relative = np.linalg.norm(direct - result["hessian"]) / np.linalg.norm(
            direct
        )
        self.assertLess(relative, 1e-8)

    def test_18_hessian_principal_mode_finite_difference(self) -> None:
        result = liu.hessian_at_resolution(
            self.basis, self.variables, n_bins=6, nodes=41
        )
        rows = liu.hessian_finite_difference_checks(result, [3e-4, 1e-3])
        principal = [
            row["relative_error"]
            for row in rows
            if row["kind"] == "principal"
            and row["mode"] <= 3
            and np.isfinite(row["relative_error"])
        ]
        self.assertLess(min(principal), 0.01)

    def test_19_rank_10_stable_two_resolutions(self) -> None:
        ranks = [
            liu.hessian_at_resolution(
                self.basis, self.variables, n_bins=bins, nodes=41
            )["channel_rank"]
            for bins in (6, 8)
        ]
        self.assertEqual(ranks, [10, 10])

    def test_20_appendix_c_hessian_prefactors(self) -> None:
        jacobian = np.zeros((10, 10))
        jacobian[:10, :10] = np.eye(10)
        components = liu.appendix_c_hessian_components(jacobian)
        self.assertAlmostEqual(components["alpha00"][0, 0], 0.5)
        self.assertAlmostEqual(components["alpha00"][4, 4], 0.5)
        self.assertAlmostEqual(components["alpha01"][1, 1], 1.0)
        self.assertAlmostEqual(components["alpha01"][6, 6], 1.0)
        self.assertAlmostEqual(components["alpha11"][3, 3], 0.5)
        self.assertAlmostEqual(components["theta"][8, 8], 0.4)
        self.assertAlmostEqual(components["theta"][9, 9], 0.3)
        self.assertAlmostEqual(components["theta"][8, 9], -0.2)


class SerializationCliAndProvenanceTests(unittest.TestCase):
    def test_21_synthetic_plant_serialization_quantities_are_consistent(self) -> None:
        config = liu.AOMConfig(case="small")
        model = liu.Model(omega0=1.0, duration=0.16)
        ideal = np.linspace(0.2, 1.0, 16) * np.exp(
            1j * np.linspace(0.0, 0.7, 16)
        )
        before_command = ideal.copy()
        after_command = ideal + 0.01 * abs(ideal) * (1.0 - 0.3j)
        before_output = liu.aom_plant(before_command, 0.01, config)
        after_output = liu.aom_plant(after_command, 0.01, config)
        before_coefficients, before_residual = (
            liu.additive_output_coefficients(
                before_output,
                ideal,
                abs(ideal),
                0.01,
                config.ridge_projection,
                omega0=model.omega0,
            )
        )
        after_coefficients, after_residual = (
            liu.additive_output_coefficients(
                after_output,
                ideal,
                abs(ideal),
                0.01,
                config.ridge_projection,
                omega0=model.omega0,
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.npz"
            np.savez_compressed(
                path,
                bin_centers_us=(np.arange(16) + 0.5) * 0.01,
                ideal=ideal,
                command=before_command,
                before_output=before_output,
                after_command=after_command,
                after_output=after_output,
                before_output_distortion_coefficients=before_coefficients,
                remaining_output_distortion_coefficients=after_coefficients,
                before_unrepresented_additive_residual=before_residual,
                after_unrepresented_additive_residual=after_residual,
            )
            validation = liu.validate_synthetic_waveform_archive(
                path, model, config
            )
        self.assertTrue(validation["all"])

    def test_22_cli_mwe_needs_no_run_json_or_jax(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            environment = os.environ.copy()
            environment["LIU_DISABLE_JAX"] = "1"
            result = subprocess.run(
                [
                    sys.executable,
                    str(MODULE_PATH),
                    "--mwe",
                    "--quick",
                    "--run-dir",
                    directory,
                ],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((Path(directory) / "run.json").exists())
            self.assertTrue(
                (Path(directory) / "data/mwe_summary.json").exists()
            )
            metadata = json.loads(
                (Path(directory) / "run_metadata.json").read_text()
            )
            self.assertFalse(metadata["jax_available"])

    def test_23_cache_hash_mismatch_is_rejected(self) -> None:
        basis = liu.WaveformBasis()
        config = liu.RunConfig()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "waveform.npz"
            liu.save_waveform(
                path,
                basis,
                liu.seed_waveform(basis),
                "test",
                liu.PROVENANCE["synthetic"],
                config,
            )
            changed = liu.RunConfig(
                model=liu.ModelConfig(duration_us=0.56)
            )
            with self.assertRaises(RuntimeError):
                liu.load_waveform_variables(path, expected_config=changed)
            with np.load(path) as archive:
                contents = {name: archive[name] for name in archive.files}
            contents["code_version"] = np.asarray("deliberately-stale")
            np.savez_compressed(path, **contents)
            self.assertFalse(liu.waveform_cache_matches(path, config))
            with self.assertRaises(RuntimeError):
                liu.load_waveform_variables(path, expected_config=config)

    def test_24_example_config_schema_and_profile_are_enforced(self) -> None:
        example = PACKAGE_ROOT / "liu_2026_fig234_config.example.json"
        config = liu.load_config(example, "quick")
        self.assertEqual(config.model.basis_size, 10)
        self.assertEqual(config.optimizer.regularizer_nodes, 401)
        self.assertEqual(config.optimizer.backend, "spline")
        self.assertEqual(
            config.optimizer.robustness_objective, "channel_root"
        )
        self.assertEqual(config.hessian.convention, "paper_lab_iq")
        with self.assertRaises(ValueError):
            liu.load_config(example, "standard")

    def test_25_provenance_vocabulary_and_contract_are_stable(self) -> None:
        self.assertEqual(
            set(liu.PROVENANCE),
            {
                "analytic",
                "exact",
                "equivalent",
                "digitized",
                "synthetic",
                "experimental",
                "reported",
                "unavailable",
            },
        )
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            (run_dir / "data").mkdir()
            # The script path is resolved relative to repository cwd.
            prior = Path.cwd()
            try:
                import os

                os.chdir(ROOT)
                contract = liu.write_experimental_contract(run_dir)
            finally:
                os.chdir(prior)
            self.assertFalse(
                contract["synthetic_points_generated_for_experimental_panels"]
            )
            self.assertEqual(len(contract["contracts"]), 10)
            self.assertEqual(
                len(contract["microscopic_input_contracts"]), 8
            )

    def test_26_optional_full_model_and_lindblad_invariants(self) -> None:
        parameters = noise.FullModelParameters(
            blockade_rr=100.0,
            blockade_rrprime=90.0,
            blockade_rprimerprime=80.0,
        )
        hamiltonian = noise.full_two_atom_hamiltonian(
            12.0 + 3.0j, parameters, doppler_shifts=(0.2, -0.1)
        )
        self.assertLess(
            np.linalg.norm(hamiltonian - hamiltonian.conj().T), 1e-12
        )
        density = np.eye(16, dtype=np.complex128) / 16.0
        derivative = noise.lindblad_rhs(hamiltonian, ())(
            0.0, density.reshape(-1)
        ).reshape(16, 16)
        self.assertLess(abs(np.trace(derivative)), 1e-12)

    def test_27_input_in_manifest_runs_all_panels_as_synthetic(self) -> None:
        manifest = PACKAGE_ROOT / "input.in"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "manifest-results"
            plot_dir = Path(directory) / "manifest-figs"
            result = subprocess.run(
                [
                    sys.executable,
                    str(EXPERIMENTAL_PATH),
                    "--input-in",
                    str(manifest),
                    "--output-dir",
                    str(output),
                    "--plot-dir",
                    str(plot_dir),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(
                (output / "manifest_summary.json").read_text()
            )
            self.assertEqual(summary["schema_version"], 2)
            self.assertEqual(len(summary["panels"]), 10)
            self.assertTrue(summary["synthetic_points_generated"])
            self.assertFalse(summary["experimental_points_generated"])
            self.assertEqual(
                summary["physical_model"]["atom"]["state_labels"]["qubit"],
                ["0", "1"],
            )
            self.assertEqual(
                summary["physical_model"]["atom"]["state_labels"]["rydberg"],
                ["r", "rprime"],
            )
            self.assertEqual(
                summary["physical_model"]["missing_input_count"], 8
            )
            self.assertTrue(
                (output / "physical_model_inputs.json").exists()
            )
            self.assertTrue(
                (
                    plot_dir
                    / "diagnostics"
                    / "input_manifest_overview.png"
                ).exists()
            )
            self.assertTrue(
                (
                    plot_dir
                    / "paper_layout"
                    / "figure2_paper_layout_synthetic.png"
                ).exists()
            )
            self.assertTrue(
                (
                    plot_dir
                    / "paper_layout"
                    / "figure4_paper_layout_synthetic.png"
                ).exists()
            )
            self.assertEqual(len(list(plot_dir.rglob("*.png"))), 13)
            imaging = json.loads(
                (output / "fig2a_imaging.json").read_text()
            )
            self.assertEqual(
                sorted(set(imaging["fit"]["prepared_states"])), ["0", "1"]
            )
            intensity = json.loads(
                (output / "fig4d_intensity.json").read_text()
            )
            self.assertIn(
                "power",
                intensity["fit"]["AR::pointwise_cz_equivalent"][
                    "directions"
                ]["positive"],
            )

    def test_28_microscopic_csv_contract_and_v1_compatibility(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            waveform = root / "waveform.csv"
            waveform.write_text(
                "time_us,amplitude_rad_per_us,phase_rad\n"
                "0.0,0.0,0.0\n0.55,0.0,0.0\n",
                encoding="utf-8",
            )
            manifest = json.loads(
                (PACKAGE_ROOT / "input.in").read_text(encoding="utf-8")
            )
            manifest["physical_model"]["microscopic_inputs"][
                "pulse_waveform"
            ] = {
                "source": "csv",
                "path": "waveform.csv",
                "provenance": "unit-test calibration",
            }
            path = root / "input.in"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            loaded = experimental.load_manifest(path)
            summary = experimental.validate_physical_model(loaded, path)
            self.assertEqual(summary["supplied_input_count"], 1)
            self.assertEqual(summary["missing_input_count"], 7)
            self.assertEqual(
                summary["microscopic_inputs"]["pulse_waveform"]["rows"], 2
            )
            self.assertFalse(
                summary["microscopic_inputs"]["pulse_waveform"][
                    "consumed_by_current_hessian"
                ]
            )

            legacy = root / "legacy.in"
            legacy.write_text(
                json.dumps({"schema_version": 1, "panels": {}}),
                encoding="utf-8",
            )
            self.assertEqual(
                experimental.load_manifest(legacy)["schema_version"], 1
            )

    def test_29_microscopic_csv_rejects_missing_columns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "bad.csv").write_text(
                "time_us,phase_rad\n0.0,0.0\n", encoding="utf-8"
            )
            manifest = json.loads(
                (PACKAGE_ROOT / "input.in").read_text(encoding="utf-8")
            )
            manifest["physical_model"]["microscopic_inputs"][
                "pulse_waveform"
            ] = {"source": "csv", "path": "bad.csv"}
            path = root / "input.in"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(
                ValueError, "amplitude_rad_per_us"
            ):
                experimental.load_manifest(path)

    def test_30_figure1_panel_g_is_mechanistic_reconstruction(self) -> None:
        source = (
            PACKAGE_ROOT / "liu_2026_fig1_reproduction.py"
        ).read_text(encoding="utf-8")
        self.assertIn("def panel_g(", source)
        self.assertIn('for letter in "abcdefghi"', source)
        self.assertIn("panel (g) is a mechanistic reconstruction", source)


if __name__ == "__main__":
    unittest.main()
