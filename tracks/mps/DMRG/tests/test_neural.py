from __future__ import annotations

import unittest

import numpy as np

from vmcrg_ref.blockspin import block_majority
from vmcrg_ref.ising import IsingLattice
from vmcrg_ref.hybrid_neural import (
    HybridNeuralVMCRGOptimizer,
    LinearNeuralBiasedMetropolis,
    RobbinsMonroSGD,
    UniformIsingReference2D,
)
from vmcrg_ref.neural_energy import D4EvenLocalMLP, LocalEnergyCache, MLPGradient
from vmcrg_ref.operators import EVEN_SHAPES, OperatorBasis


def nonzero_model(seed: int = 31) -> D4EvenLocalMLP:
    model = D4EvenLocalMLP.random(radius=2, hidden=7, seed=seed)
    rng = np.random.default_rng(seed + 1)
    model.weight_out[:] = rng.normal(0.0, 0.15, model.hidden)
    return model


def nonzero_patch_model(seed: int = 51) -> D4EvenLocalMLP:
    model = D4EvenLocalMLP.random(
        radius=1, hidden=7, seed=seed, feature_mode="patch"
    )
    rng = np.random.default_rng(seed + 1)
    model.weight_out[:] = rng.normal(0.0, 0.15, model.hidden)
    return model


def nonzero_long_shell_model(seed: int = 71) -> D4EvenLocalMLP:
    model = D4EvenLocalMLP.random(
        radius=3, hidden=7, seed=seed, feature_mode="shell"
    )
    rng = np.random.default_rng(seed + 1)
    model.weight_out[:] = rng.normal(0.0, 0.15, model.hidden)
    return model


def nonzero_multiscale_model(seed: int = 81) -> D4EvenLocalMLP:
    model = D4EvenLocalMLP.random(
        radius=3, hidden=7, seed=seed, feature_mode="multiscale"
    )
    rng = np.random.default_rng(seed + 1)
    model.weight_out[:] = rng.normal(0.0, 0.15, model.hidden)
    return model


class NeuralEnergyTests(unittest.TestCase):
    def test_uniform_reference_has_exact_shape_support_and_log_probability(self) -> None:
        reference = UniformIsingReference2D()
        spins = reference.sample(np.random.default_rng(30), samples=5, length=4)
        self.assertEqual(spins.shape, (5, 4, 4))
        self.assertEqual(spins.dtype, np.int8)
        self.assertTrue(np.all((spins == -1) | (spins == 1)))
        np.testing.assert_allclose(
            reference.log_probability(spins),
            np.full(5, -16.0 * np.log(2.0)),
        )

    def test_exact_lattice_symmetries(self) -> None:
        rng = np.random.default_rng(33)
        spins = IsingLattice.random(9, rng).spins
        for model in (
            nonzero_model(),
            nonzero_patch_model(),
            nonzero_multiscale_model(),
        ):
            reference = model.energy(spins)
            self.assertAlmostEqual(model.energy(-spins), reference, places=12)
            self.assertAlmostEqual(model.energy(np.rot90(spins)), reference, places=12)
            self.assertAlmostEqual(model.energy(np.fliplr(spins)), reference, places=12)
            self.assertAlmostEqual(
                model.energy(np.roll(spins, shift=(2, -3), axis=(0, 1))),
                reference,
                places=12,
            )

    def test_local_delta_matches_full_recomputation(self) -> None:
        rng = np.random.default_rng(34)
        spins = IsingLattice.random(9, rng).spins
        for model in (
            nonzero_model(),
            nonzero_patch_model(),
            nonzero_multiscale_model(),
        ):
            cache = LocalEnergyCache(model, spins)
            before = model.energy(spins)
            for x, y in ((0, 0), (2, 7), (8, 8)):
                proposal = cache.proposal(x, y)
                trial = spins.copy()
                trial[x, y] *= -1
                self.assertAlmostEqual(
                    model.energy(trial) - before, proposal.delta_energy, places=11
                )

    def test_local_cache_stays_exact_after_commits(self) -> None:
        rng = np.random.default_rng(35)
        spins = IsingLattice.random(9, rng).spins
        model = nonzero_model()
        cache = LocalEnergyCache(model, spins)
        for x, y in ((0, 0), (3, 4), (8, 8), (1, 6)):
            proposal = cache.proposal(x, y)
            cache.commit(proposal)
            spins[x, y] *= -1
            cache.assert_consistent()

    def test_large_shell_cache_uses_exact_direct_evaluation(self) -> None:
        rng = np.random.default_rng(73)
        spins = IsingLattice.random(9, rng).spins
        model = nonzero_long_shell_model()
        cache = LocalEnergyCache(model, spins)
        self.assertIsNone(cache.lookup_table)
        before = model.energy(spins)
        proposal = cache.proposal(4, 5)
        trial = spins.copy()
        trial[4, 5] *= -1
        self.assertAlmostEqual(
            model.energy(trial) - before, proposal.delta_energy, places=11
        )
        cache.commit(proposal)
        spins[4, 5] *= -1
        cache.assert_consistent()

    def test_multiscale_features_preserve_inner_sites_and_pool_outer_shells(self) -> None:
        model = nonzero_multiscale_model()
        self.assertEqual(model.n_features, 16)
        np.testing.assert_array_equal(model.shell_counts[:9], np.ones(9, dtype=int))
        self.assertEqual(model.feature_permutations.shape, (8, 16))
        self.assertGreater(model.lookup_size, LocalEnergyCache.MAX_LOOKUP_STATES)

    def test_manual_gradient_matches_finite_difference(self) -> None:
        rng = np.random.default_rng(36)
        spins = IsingLattice.random(7, rng).spins
        model = nonzero_model()
        gradient = model.gradient(spins)
        epsilon = 1e-6

        checks = (
            (model.weight_in, gradient.weight_in, (2, 4)),
            (model.bias_hidden, gradient.bias_hidden, (3,)),
            (model.weight_out, gradient.weight_out, (5,)),
        )
        for parameter, analytic, index in checks:
            original = float(parameter[index])
            parameter[index] = original + epsilon
            plus = model.energy(spins)
            parameter[index] = original - epsilon
            minus = model.energy(spins)
            parameter[index] = original
            numeric = (plus - minus) / (2.0 * epsilon)
            self.assertAlmostEqual(float(analytic[index]), numeric, places=6)

    def test_patch_manual_gradient_matches_finite_difference(self) -> None:
        rng = np.random.default_rng(53)
        spins = IsingLattice.random(7, rng).spins
        model = nonzero_patch_model()
        gradient = model.gradient(spins)
        epsilon = 1e-6
        original = float(model.weight_in[2, 4])
        model.weight_in[2, 4] = original + epsilon
        plus = model.energy(spins)
        model.weight_in[2, 4] = original - epsilon
        minus = model.energy(spins)
        model.weight_in[2, 4] = original
        self.assertAlmostEqual(
            float(gradient.weight_in[2, 4]),
            (plus - minus) / (2.0 * epsilon),
            places=6,
        )

    def test_nonfinite_neural_parameters_are_rejected(self) -> None:
        model = nonzero_patch_model(54)
        bad_output = model.weight_out.copy()
        bad_output[0] = np.nan
        with self.assertRaisesRegex(ValueError, "finite"):
            D4EvenLocalMLP(
                model.radius,
                model.hidden,
                model.weight_in,
                model.bias_hidden,
                bad_output,
                feature_mode=model.feature_mode,
            )


class NeuralSamplerTests(unittest.TestCase):
    def test_identity_block_transform_has_exact_zero_linear_effective_energy(self) -> None:
        rng = np.random.default_rng(91)
        couplings = np.linspace(0.03, -0.01, len(EVEN_SHAPES))
        model = D4EvenLocalMLP.random(
            radius=3, hidden=7, seed=92, feature_mode="multiscale"
        )
        sampler = LinearNeuralBiasedMetropolis(
            IsingLattice.random(15, rng),
            couplings,
            -couplings,
            model,
            rng,
            EVEN_SHAPES,
            block_size=1,
            compiled=True,
        )
        np.testing.assert_array_equal(sampler.block_spins, sampler.lattice.spins)
        self.assertAlmostEqual(sampler.effective_hamiltonian, 0.0, places=12)

    def test_hybrid_delta_matches_full_recomputation(self) -> None:
        rng = np.random.default_rng(61)
        model = nonzero_patch_model(62)
        couplings = np.linspace(0.03, -0.01, len(EVEN_SHAPES))
        linear_bias = np.linspace(-0.02, 0.005, len(EVEN_SHAPES))
        sampler = LinearNeuralBiasedMetropolis(
            IsingLattice.random(15, rng),
            couplings,
            linear_bias,
            model,
            rng,
            EVEN_SHAPES,
            compiled=False,
        )
        before = sampler.effective_hamiltonian
        for x, y in ((0, 0), (7, 4), (14, 14)):
            proposal = sampler.proposal_delta(x, y)
            trial = sampler.lattice.spins.copy()
            trial[x, y] *= -1
            trial_block = block_majority(trial)
            after = (
                couplings @ sampler.micro_basis.values(trial)
                + linear_bias @ sampler.block_basis.values(trial_block)
                + model.energy(trial_block)
            )
            expected = (
                couplings @ proposal.delta_micro
                + linear_bias @ proposal.delta_linear_bias
                + proposal.delta_neural_bias
            )
            self.assertAlmostEqual(after - before, expected, places=10)

    def test_compiled_hybrid_matches_reference_trajectory(self) -> None:
        initial_rng = np.random.default_rng(63)
        initial = IsingLattice.random(15, initial_rng).spins.copy()
        couplings = np.linspace(0.03, -0.01, len(EVEN_SHAPES))
        linear_bias = np.linspace(-0.02, 0.005, len(EVEN_SHAPES))
        micro_basis = OperatorBasis(15, EVEN_SHAPES)
        block_basis = OperatorBasis(5, EVEN_SHAPES)
        reference = LinearNeuralBiasedMetropolis(
            IsingLattice(initial.copy()),
            couplings,
            linear_bias,
            nonzero_patch_model(64),
            np.random.default_rng(65),
            EVEN_SHAPES,
            compiled=False,
            micro_basis=micro_basis,
            block_basis=block_basis,
        )
        compiled = LinearNeuralBiasedMetropolis(
            IsingLattice(initial.copy()),
            couplings,
            linear_bias,
            nonzero_patch_model(64),
            np.random.default_rng(65),
            EVEN_SHAPES,
            compiled=True,
            micro_basis=micro_basis,
            block_basis=block_basis,
        )
        reference.run_sweeps(2)
        compiled.run_sweeps(2)
        np.testing.assert_array_equal(compiled.lattice.spins, reference.lattice.spins)
        np.testing.assert_array_equal(compiled.block_spins, reference.block_spins)
        np.testing.assert_array_equal(compiled.micro_values, reference.micro_values)
        np.testing.assert_array_equal(compiled.block_values, reference.block_values)
        np.testing.assert_allclose(
            compiled.bias_cache.density, reference.bias_cache.density, atol=1e-12
        )
        compiled.assert_cache_consistent()

    def test_compiled_long_shell_matches_reference_trajectory(self) -> None:
        initial_rng = np.random.default_rng(74)
        initial = IsingLattice.random(21, initial_rng).spins.copy()
        couplings = np.linspace(0.03, -0.01, len(EVEN_SHAPES))
        linear_bias = np.zeros(len(EVEN_SHAPES))
        micro_basis = OperatorBasis(21, EVEN_SHAPES)
        block_basis = OperatorBasis(7, EVEN_SHAPES)
        reference = LinearNeuralBiasedMetropolis(
            IsingLattice(initial.copy()),
            couplings,
            linear_bias,
            nonzero_long_shell_model(75),
            np.random.default_rng(76),
            EVEN_SHAPES,
            compiled=False,
            micro_basis=micro_basis,
            block_basis=block_basis,
        )
        compiled = LinearNeuralBiasedMetropolis(
            IsingLattice(initial.copy()),
            couplings,
            linear_bias,
            nonzero_long_shell_model(75),
            np.random.default_rng(76),
            EVEN_SHAPES,
            compiled=True,
            micro_basis=micro_basis,
            block_basis=block_basis,
        )
        reference.run_sweeps(1)
        compiled.run_sweeps(1)
        np.testing.assert_array_equal(compiled.lattice.spins, reference.lattice.spins)
        np.testing.assert_array_equal(compiled.block_spins, reference.block_spins)
        np.testing.assert_array_equal(compiled.micro_values, reference.micro_values)
        np.testing.assert_array_equal(compiled.block_values, reference.block_values)
        np.testing.assert_allclose(
            compiled.bias_cache.density, reference.bias_cache.density, atol=1e-11
        )
        compiled.assert_cache_consistent()

    def test_compiled_multiscale_matches_reference_trajectory(self) -> None:
        initial_rng = np.random.default_rng(84)
        initial = IsingLattice.random(21, initial_rng).spins.copy()
        couplings = np.linspace(0.03, -0.01, len(EVEN_SHAPES))
        linear_bias = np.zeros(len(EVEN_SHAPES))
        micro_basis = OperatorBasis(21, EVEN_SHAPES)
        block_basis = OperatorBasis(7, EVEN_SHAPES)
        reference = LinearNeuralBiasedMetropolis(
            IsingLattice(initial.copy()), couplings, linear_bias,
            nonzero_multiscale_model(85), np.random.default_rng(86),
            EVEN_SHAPES, compiled=False, micro_basis=micro_basis,
            block_basis=block_basis,
        )
        compiled = LinearNeuralBiasedMetropolis(
            IsingLattice(initial.copy()), couplings, linear_bias,
            nonzero_multiscale_model(85), np.random.default_rng(86),
            EVEN_SHAPES, compiled=True, micro_basis=micro_basis,
            block_basis=block_basis,
        )
        reference.run_sweeps(1)
        compiled.run_sweeps(1)
        np.testing.assert_array_equal(compiled.lattice.spins, reference.lattice.spins)
        np.testing.assert_array_equal(compiled.block_spins, reference.block_spins)
        np.testing.assert_array_equal(compiled.micro_values, reference.micro_values)
        np.testing.assert_array_equal(compiled.block_values, reference.block_values)
        np.testing.assert_allclose(
            compiled.bias_cache.density, reference.bias_cache.density, atol=1e-11
        )
        compiled.assert_cache_consistent()


class NeuralOptimizerTests(unittest.TestCase):
    def test_robbins_monro_schedule_and_plain_sgd_update(self) -> None:
        model = D4EvenLocalMLP.random(
            radius=1, hidden=3, seed=53, feature_mode="patch"
        )
        gradient = MLPGradient(
            np.ones_like(model.weight_in),
            np.ones_like(model.bias_hidden),
            np.ones_like(model.weight_out),
        )
        before = model.weight_in.copy()
        optimizer = RobbinsMonroSGD(
            initial_learning_rate=0.02,
            decay_scale=10.0,
            decay_power=0.75,
        )
        first_rate = optimizer.update(model, gradient)
        self.assertEqual(first_rate, 0.02)
        np.testing.assert_allclose(model.weight_in, before - 0.02)
        expected_second = 0.02 / (1.0 + 1.0 / 10.0) ** 0.75
        self.assertAlmostEqual(optimizer.learning_rate, expected_second)
        second_rate = optimizer.update(model, gradient)
        self.assertAlmostEqual(second_rate, expected_second)
        self.assertLess(second_rate, first_rate)

    def test_gradient_accumulation_counts_every_sampling_block(self) -> None:
        model = D4EvenLocalMLP.random(
            radius=1, hidden=3, seed=54, feature_mode="patch"
        )
        optimizer = HybridNeuralVMCRGOptimizer(
            15,
            np.zeros(len(EVEN_SHAPES)),
            np.zeros(len(EVEN_SHAPES)),
            model,
            EVEN_SHAPES,
            walkers=2,
            seed=55,
            parallel_walkers=False,
        )
        records = optimizer.run(
            steps=2,
            sweeps_per_step=1,
            learning_rate=0.02,
            target_samples=2,
            optimizer_name="robbins_monro_sgd",
            gradient_accumulation_steps=3,
            decay_scale=10.0,
            decay_power=0.75,
        )
        self.assertEqual(len(records), 2)
        self.assertLess(records[1].learning_rate, records[0].learning_rate)
        expected_attempts = 2 * 3 * 15 * 15
        self.assertTrue(
            all(sampler.attempted == expected_attempts for sampler in optimizer.samplers)
        )

    def test_invalid_reference_samples_are_rejected(self) -> None:
        class InvalidReference:
            name = "invalid_zero_spins"

            def sample(self, rng, samples, length):
                return np.zeros((samples, length, length), dtype=np.int8)

            def log_probability(self, spins):
                return np.zeros(spins.shape[0], dtype=np.float64)

        optimizer = HybridNeuralVMCRGOptimizer(
            15,
            np.zeros(len(EVEN_SHAPES)),
            np.zeros(len(EVEN_SHAPES)),
            D4EvenLocalMLP.random(1, 5, seed=55, feature_mode="patch"),
            EVEN_SHAPES,
            walkers=2,
            seed=56,
            parallel_walkers=False,
            reference_distribution=InvalidReference(),
        )
        with self.assertRaisesRegex(ValueError, "only -1 and \+1"):
            optimizer.run(1, 1, 0.001, target_samples=2)

    def test_hybrid_parallel_walkers_match_sequential_walkers(self) -> None:
        couplings = np.zeros(len(EVEN_SHAPES))
        couplings[0] = 0.3
        linear_bias = -couplings
        sequential_model = D4EvenLocalMLP.random(
            radius=1, hidden=5, seed=66, feature_mode="patch"
        )
        parallel_model = sequential_model.copy()
        sequential = HybridNeuralVMCRGOptimizer(
            15,
            couplings,
            linear_bias,
            sequential_model,
            EVEN_SHAPES,
            walkers=2,
            seed=67,
            parallel_walkers=False,
        )
        parallel = HybridNeuralVMCRGOptimizer(
            15,
            couplings,
            linear_bias,
            parallel_model,
            EVEN_SHAPES,
            walkers=2,
            seed=67,
            parallel_walkers=True,
        )
        first = sequential.run(2, 1, 0.001, target_samples=4)
        second = parallel.run(
            2,
            1,
            0.001,
            target_samples=4,
            optimizer_name="adam",
            gradient_accumulation_steps=1,
        )
        np.testing.assert_array_equal(parallel_model.weight_in, sequential_model.weight_in)
        np.testing.assert_array_equal(
            parallel_model.bias_hidden, sequential_model.bias_hidden
        )
        np.testing.assert_array_equal(
            parallel_model.weight_out, sequential_model.weight_out
        )
        np.testing.assert_array_equal(
            [record.gradient_norm for record in second],
            [record.gradient_norm for record in first],
        )

if __name__ == "__main__":
    unittest.main()
