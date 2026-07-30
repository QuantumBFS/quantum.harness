import importlib
import unittest


def assert_matrix_close(test_case, actual, expected, places=12):
    test_case.assertEqual(len(actual), len(expected))
    for actual_row, expected_row in zip(actual, expected):
        test_case.assertEqual(len(actual_row), len(expected_row))
        for actual_value, expected_value in zip(actual_row, expected_row):
            test_case.assertAlmostEqual(actual_value.real, complex(expected_value).real, places=places)
            test_case.assertAlmostEqual(actual_value.imag, complex(expected_value).imag, places=places)


class ChannelDecompositionTests(unittest.TestCase):
    def load_api(self):
        try:
            module = importlib.import_module("src.channel_decomposition")
        except ModuleNotFoundError:
            self.fail("src.channel_decomposition has not been implemented")
        return module.decompose_operator, module.channel_weights

    def setUp(self):
        self.operator = [
            [3.0, 1.0 + 0.5j, 0.2, 0.0],
            [1.0 - 0.5j, 1.0, 0.0, -0.3j],
            [0.2, 0.0, 2.0, -0.4],
            [0.0, 0.3j, -0.4, 4.0],
        ]
        self.blocks = [[0, 1], [2, 3]]

    def test_channels_reconstruct_input_exactly(self):
        decompose_operator, _ = self.load_api()
        channels = decompose_operator(self.operator, self.blocks)
        reconstructed = [
            [
                channels["charge"][row][column]
                + channels["internal"][row][column]
                + channels["nonlocal"][row][column]
                for column in range(4)
            ]
            for row in range(4)
        ]
        assert_matrix_close(self, reconstructed, self.operator)

    def test_internal_block_has_zero_trace_on_every_site(self):
        decompose_operator, _ = self.load_api()
        internal = decompose_operator(self.operator, self.blocks)["internal"]
        for block in self.blocks:
            trace = sum(internal[index][index] for index in block)
            self.assertAlmostEqual(trace.real, 0.0, places=12)
            self.assertAlmostEqual(trace.imag, 0.0, places=12)

    def test_each_channel_is_hermitian(self):
        decompose_operator, _ = self.load_api()
        channels = decompose_operator(self.operator, self.blocks)
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

    def test_common_shift_is_pure_charge(self):
        decompose_operator, channel_weights = self.load_api()
        channels = decompose_operator([[2.0, 0.0], [0.0, 2.0]], [[0, 1]])
        weights = channel_weights(channels)
        self.assertAlmostEqual(weights["charge"], 1.0)
        self.assertAlmostEqual(weights["internal"], 0.0)
        self.assertAlmostEqual(weights["nonlocal"], 0.0)

    def test_orbital_splitting_is_pure_internal(self):
        decompose_operator, channel_weights = self.load_api()
        channels = decompose_operator([[1.0, 0.0], [0.0, -1.0]], [[0, 1]])
        weights = channel_weights(channels)
        self.assertAlmostEqual(weights["charge"], 0.0)
        self.assertAlmostEqual(weights["internal"], 1.0)
        self.assertAlmostEqual(weights["nonlocal"], 0.0)

    def test_site_blocks_must_form_a_partition(self):
        decompose_operator, _ = self.load_api()
        with self.assertRaisesRegex(ValueError, "partition"):
            decompose_operator([[1.0, 0.0], [0.0, 1.0]], [[0], [0]])

    def test_operator_must_be_hermitian(self):
        decompose_operator, _ = self.load_api()
        with self.assertRaisesRegex(ValueError, "Hermitian"):
            decompose_operator([[1.0, 2.0], [0.0, 1.0]], [[0, 1]])

    def test_basis_projection_limits_weights_to_target_subspace(self):
        decompose_operator, channel_weights = self.load_api()
        channels = decompose_operator(
            [[2.0, 0.0, 0.0], [0.0, -2.0, 0.0], [0.0, 0.0, 10.0]],
            [[0, 1], [2]],
        )
        basis_vectors = [[1.0, 0.0], [0.0, 1.0], [0.0, 0.0]]
        weights = channel_weights(channels, basis_vectors=basis_vectors)
        self.assertAlmostEqual(weights["charge"], 0.0)
        self.assertAlmostEqual(weights["internal"], 1.0)
        self.assertAlmostEqual(weights["nonlocal"], 0.0)


if __name__ == "__main__":
    unittest.main()
