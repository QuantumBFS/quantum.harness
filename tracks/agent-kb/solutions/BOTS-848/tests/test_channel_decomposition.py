import importlib
import itertools
import math
import unittest


EXPECTED_CHANNELS = ("global_charge", "site_charge", "internal", "nonlocal")


def assert_matrix_close(test_case, actual, expected, places=12):
    test_case.assertEqual(len(actual), len(expected))
    for actual_row, expected_row in zip(actual, expected):
        test_case.assertEqual(len(actual_row), len(expected_row))
        for actual_value, expected_value in zip(actual_row, expected_row):
            test_case.assertAlmostEqual(actual_value.real, complex(expected_value).real, places=places)
            test_case.assertAlmostEqual(actual_value.imag, complex(expected_value).imag, places=places)


def frobenius_inner(left, right):
    return sum(
        complex(left[row][column]).conjugate() * complex(right[row][column])
        for row in range(len(left))
        for column in range(len(left))
    )


class ChannelDecompositionTests(unittest.TestCase):
    def load_module(self):
        try:
            return importlib.import_module("src.channel_decomposition")
        except ModuleNotFoundError:
            self.fail("src.channel_decomposition has not been implemented")

    def setUp(self):
        self.operator = [
            [3.0, 1.0 + 0.5j, 0.2, 0.0],
            [1.0 - 0.5j, 1.0, 0.0, -0.3j],
            [0.2, 0.0, 2.0, -0.4],
            [0.0, 0.3j, -0.4, 4.0],
        ]
        self.blocks = [[0, 1], [2, 3]]

    def test_channel_names_are_exact(self):
        module = self.load_module()
        self.assertEqual(module.CHANNELS, EXPECTED_CHANNELS)
        self.assertEqual(
            tuple(module.decompose_operator(self.operator, self.blocks)),
            EXPECTED_CHANNELS,
        )

    def test_channels_reconstruct_input_exactly(self):
        module = self.load_module()
        channels = module.decompose_operator(self.operator, self.blocks)
        reconstructed = [
            [
                sum(channels[name][row][column] for name in EXPECTED_CHANNELS)
                for column in range(4)
            ]
            for row in range(4)
        ]
        assert_matrix_close(self, reconstructed, self.operator)

    def test_global_and_site_charge_follow_trace_definitions(self):
        module = self.load_module()
        channels = module.decompose_operator(self.operator, self.blocks)
        assert_matrix_close(
            self,
            channels["global_charge"],
            [[2.5, 0.0, 0.0, 0.0], [0.0, 2.5, 0.0, 0.0], [0.0, 0.0, 2.5, 0.0], [0.0, 0.0, 0.0, 2.5]],
        )
        assert_matrix_close(
            self,
            channels["site_charge"],
            [[-0.5, 0.0, 0.0, 0.0], [0.0, -0.5, 0.0, 0.0], [0.0, 0.0, 0.5, 0.0], [0.0, 0.0, 0.0, 0.5]],
        )

    def test_global_trace_average_is_dimension_weighted_for_unequal_blocks(self):
        module = self.load_module()
        channels = module.decompose_operator(
            [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 4.0]],
            [[0, 1], [2]],
        )

        assert_matrix_close(
            self,
            channels["global_charge"],
            [[2.0, 0.0, 0.0], [0.0, 2.0, 0.0], [0.0, 0.0, 2.0]],
        )
        assert_matrix_close(
            self,
            channels["site_charge"],
            [[-1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, 2.0]],
        )

    def test_internal_block_has_zero_trace_on_every_site(self):
        module = self.load_module()
        internal = module.decompose_operator(self.operator, self.blocks)["internal"]
        for block in self.blocks:
            trace = sum(internal[index][index] for index in block)
            self.assertAlmostEqual(trace.real, 0.0, places=12)
            self.assertAlmostEqual(trace.imag, 0.0, places=12)

    def test_channels_are_pairwise_frobenius_orthogonal(self):
        module = self.load_module()
        channels = module.decompose_operator(self.operator, self.blocks)
        for left, right in itertools.combinations(EXPECTED_CHANNELS, 2):
            with self.subTest(left=left, right=right):
                inner = frobenius_inner(channels[left], channels[right])
                self.assertAlmostEqual(inner.real, 0.0, places=12)
                self.assertAlmostEqual(inner.imag, 0.0, places=12)

    def test_each_channel_is_hermitian(self):
        module = self.load_module()
        channels = module.decompose_operator(self.operator, self.blocks)
        for matrix in channels.values():
            for row in range(len(matrix)):
                for column in range(len(matrix)):
                    self.assertAlmostEqual(
                        matrix[row][column].real,
                        matrix[column][row].conjugate().real,
                        places=12,
                    )
                    self.assertAlmostEqual(
                        matrix[row][column].imag,
                        matrix[column][row].conjugate().imag,
                        places=12,
                    )

    def test_global_identity_is_pure_global_charge(self):
        module = self.load_module()
        channels = module.decompose_operator(
            [[2.0, 0.0, 0.0, 0.0], [0.0, 2.0, 0.0, 0.0], [0.0, 0.0, 2.0, 0.0], [0.0, 0.0, 0.0, 2.0]],
            [[0, 1], [2, 3]],
        )
        weights = module.channel_weights(channels)
        self.assertAlmostEqual(weights["global_charge"], 1.0)
        self.assertAlmostEqual(weights["site_charge"], 0.0)
        self.assertAlmostEqual(weights["internal"], 0.0)
        self.assertAlmostEqual(weights["nonlocal"], 0.0)

    def test_nonzero_weights_are_invariant_to_tiny_global_scale(self):
        module = self.load_module()
        reference = module.channel_weights(
            module.decompose_operator([[1.0, 0.0], [0.0, 1.0]], [[0], [1]])
        )
        tiny = module.channel_weights(
            module.decompose_operator(
                [[1.0e-200, 0.0], [0.0, 1.0e-200]], [[0], [1]]
            )
        )

        self.assertEqual(tiny, reference)
        self.assertEqual(tiny["global_charge"], 1.0)

    def test_large_finite_common_shift_is_decomposed_without_overflow(self):
        module = self.load_module()
        channels = module.decompose_operator(
            [[1.0e308, 0.0], [0.0, 1.0e308]],
            [[0, 1]],
        )

        assert_matrix_close(
            self,
            channels["global_charge"],
            [[1.0e308, 0.0], [0.0, 1.0e308]],
            places=0,
        )
        self.assertEqual(module.channel_weights(channels)["global_charge"], 1.0)

    def test_large_finite_complex_channel_uses_component_scaling(self):
        module = self.load_module()
        value = complex(1.7e308, 1.7e308)
        channels = module.decompose_operator(
            [[0.0, value], [value.conjugate(), 0.0]],
            [[0, 1]],
        )

        weights = module.channel_weights(channels)
        self.assertEqual(weights["internal"], 1.0)

    def test_nonfinite_derived_channel_is_rejected_at_decomposition(self):
        module = self.load_module()
        with self.assertRaisesRegex(ValueError, "finite"):
            module.decompose_operator(
                [
                    [1.7e308, 0.0, 0.0],
                    [0.0, -1.7e308, 0.0],
                    [0.0, 0.0, -1.7e308],
                ],
                [[0, 1, 2]],
            )

    def test_opposite_site_shifts_are_pure_site_charge(self):
        module = self.load_module()
        channels = module.decompose_operator(
            [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, -1.0, 0.0], [0.0, 0.0, 0.0, -1.0]],
            [[0, 1], [2, 3]],
        )
        weights = module.channel_weights(channels)
        self.assertAlmostEqual(weights["global_charge"], 0.0)
        self.assertAlmostEqual(weights["site_charge"], 1.0)
        self.assertAlmostEqual(weights["internal"], 0.0)
        self.assertAlmostEqual(weights["nonlocal"], 0.0)

    def test_orbital_splitting_is_pure_internal(self):
        module = self.load_module()
        channels = module.decompose_operator([[1.0, 0.0], [0.0, -1.0]], [[0, 1]])
        weights = module.channel_weights(channels)
        self.assertAlmostEqual(weights["global_charge"], 0.0)
        self.assertAlmostEqual(weights["site_charge"], 0.0)
        self.assertAlmostEqual(weights["internal"], 1.0)
        self.assertAlmostEqual(weights["nonlocal"], 0.0)

    def test_site_blocks_must_form_a_partition(self):
        module = self.load_module()
        with self.assertRaisesRegex(ValueError, "partition"):
            module.decompose_operator([[1.0, 0.0], [0.0, 1.0]], [[0], [0]])

    def test_nonhermitian_bloch_q_operator_is_rejected_with_clear_guidance(self):
        module = self.load_module()
        invalid_operators = (
            [[1.0, 2.0], [0.0, 1.0]],
            [[1.0e-200, 1.0e-201], [0.0, 1.0e-200]],
        )
        for operator in invalid_operators:
            with self.subTest(operator=operator):
                with self.assertRaisesRegex(
                    ValueError, "standing-wave/real-space Hermitian"
                ):
                    module.decompose_operator(operator, [[0, 1]])

    def test_operator_matrix_entries_must_be_finite_numeric_non_booleans(self):
        module = self.load_module()
        for invalid in (True, float("nan"), float("inf"), -float("inf")):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "finite numeric"):
                    module.decompose_operator([[invalid, 0.0], [0.0, 1.0]], [[0, 1]])

    def test_channel_matrix_entries_must_be_finite_numeric_non_booleans(self):
        module = self.load_module()
        for invalid in (True, float("nan"), float("inf"), -float("inf")):
            with self.subTest(invalid=invalid):
                channels = {name: [[0.0]] for name in EXPECTED_CHANNELS}
                channels["global_charge"] = [[invalid]]
                with self.assertRaisesRegex(ValueError, "finite numeric"):
                    module.channel_weights(channels)

    def test_basis_vector_entries_must_be_finite_numeric_non_booleans(self):
        module = self.load_module()
        channels = module.decompose_operator([[1.0, 0.0], [0.0, 1.0]], [[0, 1]])
        for invalid in (True, float("nan"), float("inf"), -float("inf")):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "finite numeric"):
                    module.channel_weights(channels, basis_vectors=[[invalid], [0.0]])

    def test_basis_projection_limits_weights_to_target_subspace(self):
        module = self.load_module()
        channels = module.decompose_operator(
            [[2.0, 0.0, 0.0], [0.0, -2.0, 0.0], [0.0, 0.0, 0.0]],
            [[0, 1], [2]],
        )
        basis_vectors = [[1.0, 0.0], [0.0, 1.0], [0.0, 0.0]]
        weights = module.channel_weights(channels, basis_vectors=basis_vectors)
        self.assertAlmostEqual(weights["global_charge"], 0.0)
        self.assertAlmostEqual(weights["site_charge"], 0.0)
        self.assertAlmostEqual(weights["internal"], 1.0)
        self.assertAlmostEqual(weights["nonlocal"], 0.0)

    def test_nonfinite_projected_channel_is_rejected(self):
        module = self.load_module()
        channels = {name: [[0.0, 0.0], [0.0, 0.0]] for name in EXPECTED_CHANNELS}
        channels["global_charge"] = [
            [1.0e308, 1.0e308],
            [1.0e308, 1.0e308],
        ]
        component = 1.0 / math.sqrt(2.0)

        with self.assertRaisesRegex(ValueError, "finite numeric"):
            module.channel_weights(
                channels,
                basis_vectors=[[component], [component]],
            )


if __name__ == "__main__":
    unittest.main()
