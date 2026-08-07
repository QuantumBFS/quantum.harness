from __future__ import annotations

import unittest

import numpy as np

from vmcrg_ref.blockspin import block_majority, block_sums
from vmcrg_ref.candidate_operators import (
    candidate_basis_metadata,
    candidate_even_shapes,
    published_survivor_indices,
)
from vmcrg_ref.exact import exact_nearest_neighbor_moments, nearest_neighbor_spectrum
from vmcrg_ref.fast import FastMultiOperatorBiasedMetropolis
from vmcrg_ref.fixed_point import (
    bias_newton_correction,
    fixed_point_residual_report,
    newton_fixed_point_candidate,
)
from vmcrg_ref.ising import IsingLattice, nearest_neighbor_operator
from vmcrg_ref.operators import EVEN_SHAPES, ODD_SHAPES, OperatorBasis, d4_orbit
from vmcrg_ref.paper_observables import (
    covariance_matrices_from_sums,
    estimate_rg_jacobian,
    integrated_autocorrelation_time,
    normalized_connected_autocorrelation,
    scaling_dimensions,
)
from vmcrg_ref.multi import MultiOperatorBiasedMetropolis
from vmcrg_ref.sampler import BiasedMetropolis


class IsingOperatorTests(unittest.TestCase):
    def test_increment_matches_full_recomputation(self) -> None:
        rng = np.random.default_rng(7)
        lattice = IsingLattice.random(12, rng)
        before = lattice.s_nn
        for x in range(lattice.length):
            for y in range(lattice.length):
                delta = lattice.delta_s_nn(x, y)
                lattice.flip(x, y)
                after = lattice.s_nn
                lattice.flip(x, y)
                self.assertEqual(after - before, delta)

    def test_global_spin_flip_symmetry(self) -> None:
        rng = np.random.default_rng(8)
        lattice = IsingLattice.random(12, rng)
        s_nn = lattice.s_nn
        magnetization = lattice.magnetization
        flipped = IsingLattice(-lattice.spins.copy())
        self.assertEqual(flipped.s_nn, s_nn)
        self.assertEqual(flipped.magnetization, -magnetization)


class BlockSpinTests(unittest.TestCase):
    def test_majority_rule(self) -> None:
        plus = np.ones((3, 3), dtype=np.int8)
        plus.flat[:4] = -1
        minus = -plus
        self.assertEqual(int(block_majority(plus)[0, 0]), 1)
        self.assertEqual(int(block_majority(minus)[0, 0]), -1)

    def test_block_global_flip(self) -> None:
        rng = np.random.default_rng(9)
        spins = IsingLattice.random(12, rng).spins
        self.assertTrue(np.array_equal(block_majority(-spins), -block_majority(spins)))
        self.assertTrue(np.array_equal(block_sums(-spins), -block_sums(spins)))


class BiasedSamplerTests(unittest.TestCase):
    def test_effective_delta_matches_full_recomputation(self) -> None:
        rng = np.random.default_rng(10)
        sampler = BiasedMetropolis(IsingLattice.random(12, rng), 0.43, -0.2, rng)
        for x in range(12):
            for y in range(12):
                before = sampler.effective_hamiltonian
                proposal = sampler.proposal_delta(x, y)
                trial = sampler.lattice.spins.copy()
                trial[x, y] *= -1
                after = (
                    sampler.coupling * nearest_neighbor_operator(trial)
                    + sampler.bias * nearest_neighbor_operator(block_majority(trial))
                )
                expected = (
                    sampler.coupling * proposal.delta_s_micro
                    + sampler.bias * proposal.delta_s_block
                )
                self.assertAlmostEqual(after - before, expected, places=12)

    def test_cache_remains_exact(self) -> None:
        rng = np.random.default_rng(11)
        sampler = BiasedMetropolis(IsingLattice.random(12, rng), 0.43, -0.2, rng)
        for _ in range(20):
            sampler.sweep()
            sampler.assert_cache_consistent()

    def test_fixed_seed_is_reproducible(self) -> None:
        def run(seed: int) -> tuple[np.ndarray, int, int]:
            rng = np.random.default_rng(seed)
            sampler = BiasedMetropolis(IsingLattice.random(12, rng), 0.43, -0.2, rng)
            for _ in range(10):
                sampler.sweep()
            return sampler.lattice.spins.copy(), sampler.s_micro, sampler.s_block

        first = run(12)
        second = run(12)
        self.assertTrue(np.array_equal(first[0], second[0]))
        self.assertEqual(first[1:], second[1:])


class ExactVariationalTests(unittest.TestCase):
    def test_uniform_target_has_zero_nearest_neighbor_moment(self) -> None:
        mean, variance = exact_nearest_neighbor_moments(4, coupling=0.0)
        self.assertAlmostEqual(mean, 0.0, places=12)
        self.assertGreater(variance, 0.0)

    def test_identity_rg_has_j_star_equal_to_minus_k(self) -> None:
        coupling = 0.4
        mean, variance = exact_nearest_neighbor_moments(4, coupling + (-coupling))
        self.assertAlmostEqual(mean, 0.0, places=12)
        self.assertGreater(variance, 0.0)

    def test_spectrum_degeneracy_is_complete(self) -> None:
        _, degeneracies = nearest_neighbor_spectrum(4)
        self.assertEqual(int(degeneracies.sum()), 2 ** 16)


class OperatorBasisTests(unittest.TestCase):
    def test_published_even_coordinates_match_supplement(self) -> None:
        expected = (
            ((0, 0), (1, 0)),
            ((0, 0), (1, 1)),
            ((0, 0), (2, 0)),
            ((0, 0), (2, 1)),
            ((0, 0), (2, 2)),
            ((0, 0), (3, 0)),
            ((0, 0), (3, 1)),
            ((0, 0), (1, 0), (0, 1), (1, 1)),
            ((0, 0), (1, 1), (2, 0), (1, -1)),
            ((0, 0), (-1, 0), (1, 0), (0, 1)),
            ((0, 0), (-1, 0), (1, 0), (-1, 1)),
            ((0, 0), (0, 1), (1, 0), (-1, 1)),
            ((0, 0), (0, 1), (1, 0), (-1, -1)),
        )
        self.assertEqual(tuple(shape.vertices for shape in EVEN_SHAPES), expected)

    def test_operator_sign_and_instance_normalization(self) -> None:
        basis = OperatorBasis(15, EVEN_SHAPES)
        all_plus = np.ones((15, 15), dtype=np.int8)
        np.testing.assert_array_equal(
            basis.values(all_plus), -np.asarray(basis.instance_counts)
        )
        np.testing.assert_array_equal(
            np.asarray(basis.instance_counts) // (15 * 15),
            np.asarray([2, 2, 2, 4, 2, 2, 4, 1, 1, 4, 8, 4, 4]),
        )

    def test_basic_d4_orbit_sizes(self) -> None:
        self.assertEqual(len(d4_orbit(((0, 0), (1, 0)))), 2)
        self.assertEqual(len(d4_orbit(((0, 0), (1, 0), (0, 1), (1, 1)))), 1)
        self.assertEqual(len(d4_orbit(((0, 0), (-1, 0), (1, 0), (0, 1)))), 4)

    def test_nearest_neighbor_matches_reference_operator(self) -> None:
        rng = np.random.default_rng(13)
        spins = IsingLattice.random(15, rng).spins
        basis = OperatorBasis(15, (EVEN_SHAPES[0],))
        self.assertEqual(int(basis.values(spins)[0]), nearest_neighbor_operator(spins))
        self.assertEqual(basis.instance_counts[0], 2 * 15 * 15)

    def test_all_even_local_deltas_match_full_recomputation(self) -> None:
        rng = np.random.default_rng(14)
        spins = IsingLattice.random(15, rng).spins
        basis = OperatorBasis(15, EVEN_SHAPES)
        before = basis.values(spins)
        for x, y in ((0, 0), (1, 7), (8, 3), (14, 14)):
            delta = basis.delta_for_flip(spins, x, y)
            trial = spins.copy()
            trial[x, y] *= -1
            np.testing.assert_array_equal(basis.values(trial) - before, delta)

    def test_parity_under_global_spin_flip(self) -> None:
        rng = np.random.default_rng(15)
        spins = IsingLattice.random(15, rng).spins
        even_basis = OperatorBasis(15, EVEN_SHAPES)
        odd_basis = OperatorBasis(15, ODD_SHAPES)
        np.testing.assert_array_equal(even_basis.values(-spins), even_basis.values(spins))
        np.testing.assert_array_equal(odd_basis.values(-spins), -odd_basis.values(spins))

    def test_packed_incidence_is_cached(self) -> None:
        basis = OperatorBasis(15, EVEN_SHAPES)
        first = basis.packed_incidence()
        second = basis.packed_incidence()
        self.assertIs(first, second)


class CandidateOperatorTests(unittest.TestCase):
    def test_both_reconstructions_have_expected_structure(self) -> None:
        axis = candidate_even_shapes("axis5")
        generic = candidate_even_shapes("generic43")
        self.assertEqual(len(axis), 26)
        self.assertEqual(len(generic), 26)
        self.assertEqual(sum(len(shape.vertices) == 2 for shape in axis), 13)
        self.assertEqual(sum(len(shape.vertices) == 4 for shape in axis), 13)
        self.assertEqual(axis[:12], generic[:12])
        self.assertNotEqual(axis[12], generic[12])
        self.assertEqual(axis[13:], generic[13:])

    def test_candidate_basis_contains_exactly_all_published_survivors(self) -> None:
        for pair_tie in ("axis5", "generic43"):
            shapes = candidate_even_shapes(pair_tie)
            indices = published_survivor_indices(shapes)
            self.assertEqual(len(indices), 13)
            metadata = candidate_basis_metadata(pair_tie)
            self.assertEqual(
                sum(item["evidence"] == "published_retained" for item in metadata),
                13,
            )

    def test_all_candidate_local_deltas_match_full_recomputation(self) -> None:
        rng = np.random.default_rng(19)
        spins = IsingLattice.random(15, rng).spins
        for pair_tie in ("axis5", "generic43"):
            basis = OperatorBasis(15, candidate_even_shapes(pair_tie))
            before = basis.values(spins)
            for x, y in ((0, 0), (7, 11), (14, 14)):
                delta = basis.delta_for_flip(spins, x, y)
                trial = spins.copy()
                trial[x, y] *= -1
                np.testing.assert_array_equal(basis.values(trial) - before, delta)

    def test_compiled_candidate_sampler_matches_reference(self) -> None:
        shapes = candidate_even_shapes("axis5")
        rng = np.random.default_rng(20)
        initial = IsingLattice.random(15, rng).spins.copy()
        couplings = np.zeros(len(shapes))
        couplings[0] = 0.436
        bias = np.linspace(-0.01, 0.001, len(shapes))
        micro_basis = OperatorBasis(15, shapes)
        block_basis = OperatorBasis(15, shapes)
        reference = MultiOperatorBiasedMetropolis(
            IsingLattice(initial.copy()),
            couplings,
            bias,
            np.random.default_rng(21),
            shapes,
            block_size=1,
            micro_basis=micro_basis,
            block_basis=block_basis,
        )
        compiled = FastMultiOperatorBiasedMetropolis(
            IsingLattice(initial.copy()),
            couplings,
            bias,
            np.random.default_rng(21),
            shapes,
            block_size=1,
            micro_basis=micro_basis,
            block_basis=block_basis,
        )
        reference.sweep()
        compiled.sweep()
        np.testing.assert_array_equal(compiled.lattice.spins, reference.lattice.spins)
        np.testing.assert_array_equal(compiled.micro_values, reference.micro_values)
        np.testing.assert_array_equal(compiled.block_values, reference.block_values)
        compiled.assert_cache_consistent()


class MultiOperatorSamplerTests(unittest.TestCase):
    def test_vector_effective_delta_and_caches(self) -> None:
        rng = np.random.default_rng(16)
        shapes = EVEN_SHAPES
        couplings = np.zeros(len(shapes))
        couplings[0] = 0.436
        bias = np.linspace(-0.2, 0.02, len(shapes))
        sampler = MultiOperatorBiasedMetropolis(
            IsingLattice.random(24, rng), couplings, bias, rng, shapes
        )
        for x, y in ((0, 0), (7, 11), (23, 23)):
            before = sampler.effective_hamiltonian
            proposal = sampler.proposal_delta(x, y)
            trial = sampler.lattice.spins.copy()
            trial[x, y] *= -1
            trial_blocks = block_majority(trial)
            after = float(
                np.dot(couplings, sampler.micro_basis.values(trial))
                + np.dot(bias, sampler.block_basis.values(trial_blocks))
            )
            expected = float(
                np.dot(couplings, proposal.delta_micro)
                + np.dot(bias, proposal.delta_block)
            )
            self.assertAlmostEqual(after - before, expected, places=10)

        sampler.sweep()
        sampler.assert_cache_consistent()

    def test_compiled_sampler_matches_reference_trajectory(self) -> None:
        initial_rng = np.random.default_rng(17)
        initial_spins = IsingLattice.random(24, initial_rng).spins.copy()
        couplings = np.zeros(len(EVEN_SHAPES))
        couplings[0] = 0.436
        bias = np.linspace(-0.02, 0.002, len(EVEN_SHAPES))
        micro_basis = OperatorBasis(24, EVEN_SHAPES)
        block_basis = OperatorBasis(8, EVEN_SHAPES)
        reference = MultiOperatorBiasedMetropolis(
            IsingLattice(initial_spins.copy()), couplings, bias,
            np.random.default_rng(18), EVEN_SHAPES,
            micro_basis=micro_basis, block_basis=block_basis,
        )
        compiled = FastMultiOperatorBiasedMetropolis(
            IsingLattice(initial_spins.copy()), couplings, bias,
            np.random.default_rng(18), EVEN_SHAPES,
            micro_basis=micro_basis, block_basis=block_basis,
        )
        for _ in range(3):
            reference.sweep()
            compiled.sweep()
            np.testing.assert_array_equal(
                compiled.lattice.spins, reference.lattice.spins
            )
            np.testing.assert_array_equal(compiled.micro_values, reference.micro_values)
            np.testing.assert_array_equal(compiled.block_values, reference.block_values)
            compiled.assert_cache_consistent()

    def test_compiled_moment_measurement_matches_explicit_sampling(self) -> None:
        initial_rng = np.random.default_rng(30)
        initial_spins = IsingLattice.random(12, initial_rng).spins.copy()
        shapes = (*EVEN_SHAPES, *ODD_SHAPES)
        couplings = np.zeros(len(shapes))
        couplings[0] = 0.436
        bias = np.zeros(len(shapes))
        micro_basis = OperatorBasis(12, shapes)
        block_basis = OperatorBasis(4, shapes)
        measured = FastMultiOperatorBiasedMetropolis(
            IsingLattice(initial_spins.copy()),
            couplings,
            bias,
            np.random.default_rng(31),
            shapes,
            micro_basis=micro_basis,
            block_basis=block_basis,
        )
        explicit = FastMultiOperatorBiasedMetropolis(
            IsingLattice(initial_spins.copy()),
            couplings,
            bias,
            np.random.default_rng(31),
            shapes,
            micro_basis=micro_basis,
            block_basis=block_basis,
        )
        actual = measured.measure_moments(measurements=4, sweeps_between=2)
        micro_values = []
        block_values = []
        for _ in range(4):
            explicit.run_sweeps(2)
            micro_values.append(explicit.micro_values.copy())
            block_values.append(explicit.block_values.copy())
        micro = np.asarray(micro_values, dtype=float)
        block = np.asarray(block_values, dtype=float)
        expected = (
            micro.sum(axis=0),
            block.sum(axis=0),
            micro.T @ block,
            block.T @ block,
        )
        for actual_value, expected_value in zip(actual, expected):
            np.testing.assert_array_equal(actual_value, expected_value)
        np.testing.assert_array_equal(measured.lattice.spins, explicit.lattice.spins)
        measured.assert_cache_consistent()

    def test_compiled_observable_series_matches_explicit_sampling(self) -> None:
        initial_rng = np.random.default_rng(32)
        initial_spins = IsingLattice.random(12, initial_rng).spins.copy()
        couplings = np.zeros(len(EVEN_SHAPES))
        couplings[0] = 0.436
        bias = np.zeros(len(EVEN_SHAPES))
        micro_basis = OperatorBasis(12, EVEN_SHAPES)
        block_basis = OperatorBasis(4, EVEN_SHAPES)
        measured = FastMultiOperatorBiasedMetropolis(
            IsingLattice(initial_spins.copy()), couplings, bias,
            np.random.default_rng(33), EVEN_SHAPES,
            micro_basis=micro_basis, block_basis=block_basis,
        )
        explicit = FastMultiOperatorBiasedMetropolis(
            IsingLattice(initial_spins.copy()), couplings, bias,
            np.random.default_rng(33), EVEN_SHAPES,
            micro_basis=micro_basis, block_basis=block_basis,
        )
        actual = measured.nearest_neighbor_product_series(5, sweeps_between=1)
        expected = []
        for _ in range(5):
            explicit.run_sweeps(1)
            expected.append(
                (explicit.micro_values[0] / micro_basis.instance_counts[0])
                * (explicit.block_values[0] / block_basis.instance_counts[0])
            )
        np.testing.assert_allclose(actual, expected, rtol=0.0, atol=0.0)
        np.testing.assert_array_equal(measured.lattice.spins, explicit.lattice.spins)

    def test_compiled_odd_moment_series_matches_explicit_sampling(self) -> None:
        shapes = (*EVEN_SHAPES, *ODD_SHAPES)
        odd_index = len(EVEN_SHAPES)
        initial_rng = np.random.default_rng(35)
        initial_spins = IsingLattice.random(12, initial_rng).spins.copy()
        couplings = np.zeros(len(shapes))
        couplings[0] = 0.436
        bias = np.zeros(len(shapes))
        micro_basis = OperatorBasis(12, shapes)
        block_basis = OperatorBasis(4, shapes)
        measured = FastMultiOperatorBiasedMetropolis(
            IsingLattice(initial_spins.copy()), couplings, bias,
            np.random.default_rng(36), shapes,
            micro_basis=micro_basis, block_basis=block_basis,
        )
        explicit = FastMultiOperatorBiasedMetropolis(
            IsingLattice(initial_spins.copy()), couplings, bias,
            np.random.default_rng(36), shapes,
            micro_basis=micro_basis, block_basis=block_basis,
        )
        actual_cross, actual_square = measured.odd_magnetization_moment_series(
            odd_index, 5, sweeps_between=1
        )
        expected_cross = []
        expected_square = []
        for _ in range(5):
            explicit.run_sweeps(1)
            micro_value = (
                explicit.micro_values[odd_index]
                / micro_basis.instance_counts[odd_index]
            )
            block_value = (
                explicit.block_values[odd_index]
                / block_basis.instance_counts[odd_index]
            )
            expected_cross.append(micro_value * block_value)
            expected_square.append(block_value * block_value)
        np.testing.assert_allclose(actual_cross, expected_cross, rtol=0.0, atol=0.0)
        np.testing.assert_allclose(actual_square, expected_square, rtol=0.0, atol=0.0)
        np.testing.assert_array_equal(measured.lattice.spins, explicit.lattice.spins)


class PaperObservableTests(unittest.TestCase):
    def test_covariance_sufficient_statistics_match_numpy(self) -> None:
        micro = np.asarray([[1.0, 2.0], [3.0, -1.0], [2.0, 4.0]])
        block = np.asarray([[2.0, 0.0], [-1.0, 3.0], [4.0, 1.0]])
        a, b = covariance_matrices_from_sums(
            len(micro),
            micro.sum(axis=0),
            block.sum(axis=0),
            micro.T @ block,
            block.T @ block,
        )
        expected_a = micro.T @ block / len(micro) - np.outer(
            micro.mean(axis=0), block.mean(axis=0)
        )
        expected_b = block.T @ block / len(block) - np.outer(
            block.mean(axis=0), block.mean(axis=0)
        )
        np.testing.assert_allclose(a, expected_a)
        np.testing.assert_allclose(b, expected_b)

    def test_rg_jacobian_matrix_orientation(self) -> None:
        b = np.asarray([[4.0, 1.0], [1.0, 3.0]])
        transformation = np.asarray([[3.0, 0.2], [0.0, 0.5]])
        a = transformation.T @ b
        estimate = estimate_rg_jacobian(a, b)
        np.testing.assert_allclose(estimate.transformation, transformation)
        self.assertAlmostEqual(estimate.leading_eigenvalue, 3.0)
        self.assertLess(estimate.equation_relative_residual, 1e-14)

    def test_exact_ising_scaling_dimensions(self) -> None:
        result = scaling_dimensions(3.0, 3.0 ** (15.0 / 8.0))
        self.assertAlmostEqual(result["y_t"], 1.0)
        self.assertAlmostEqual(result["y_h"], 15.0 / 8.0)
        self.assertAlmostEqual(result["nu"], 1.0)
        self.assertAlmostEqual(result["eta"], 0.25)
        self.assertAlmostEqual(result["beta"], 0.125)
        self.assertAlmostEqual(result["gamma"], 1.75)
        self.assertAlmostEqual(result["alpha"], 0.0)

    def test_autocorrelation_and_initial_positive_window(self) -> None:
        rng = np.random.default_rng(34)
        series = rng.normal(size=256)
        acf = normalized_connected_autocorrelation(series, 20)
        self.assertAlmostEqual(float(acf[0]), 1.0)
        self.assertGreaterEqual(integrated_autocorrelation_time(acf), 0.5)


class FixedPointTests(unittest.TestCase):
    def test_bias_newton_correction_cancels_linearized_mean(self) -> None:
        covariance = np.array([[4.0, 1.0], [1.0, 3.0]])
        mean = np.array([0.2, -0.1])
        estimate = bias_newton_correction(
            mean, covariance, maximum_correction=1.0
        )
        np.testing.assert_allclose(estimate.predicted_mean, 0.0, atol=1e-14)

    def test_newton_step_solves_linear_fixed_point_exactly(self) -> None:
        jacobian = np.diag([2.0, 0.25])
        true_fixed_point = np.array([0.4, -0.2])
        offset = true_fixed_point - jacobian @ true_fixed_point
        point = np.array([0.3, 0.1])
        mapped = jacobian @ point + offset
        estimate = newton_fixed_point_candidate(
            point, mapped, jacobian, maximum_correction=1.0
        )
        np.testing.assert_allclose(estimate.candidate, true_fixed_point, atol=1e-14)
        np.testing.assert_allclose(estimate.predicted_residual, 0.0, atol=1e-14)

    def test_complete_vector_residual_requires_both_gates(self) -> None:
        candidate = np.array([1.0, 0.5])
        passing = fixed_point_residual_report(
            candidate, candidate + np.array([5e-4, 4e-4])
        )
        failing = fixed_point_residual_report(
            candidate, candidate + np.array([2e-3, 0.0])
        )
        self.assertEqual(passing["status"], "PASS")
        self.assertEqual(failing["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
