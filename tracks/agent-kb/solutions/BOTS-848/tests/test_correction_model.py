import importlib
import unittest


def assert_matrix_close(test_case, actual, expected, places=12):
    for actual_row, expected_row in zip(actual, expected):
        for actual_value, expected_value in zip(actual_row, expected_row):
            test_case.assertAlmostEqual(actual_value.real, complex(expected_value).real, places=places)
            test_case.assertAlmostEqual(actual_value.imag, complex(expected_value).imag, places=places)


class CorrectionModelTests(unittest.TestCase):
    def load_api(self):
        try:
            module = importlib.import_module("src.correction_model")
        except ModuleNotFoundError:
            self.fail("src.correction_model has not been implemented")
        return module.correct_operator

    def test_identity_kernels_recover_dfpt_operator(self):
        correct_operator = self.load_api()
        operator = [[3.0, 0.2], [0.2, 1.0]]
        corrected = correct_operator(
            operator,
            [[0, 1]],
            {"charge": 1.0, "internal": 1.0, "nonlocal": 1.0},
        )
        assert_matrix_close(self, corrected, operator)

    def test_each_channel_can_receive_a_distinct_kernel(self):
        correct_operator = self.load_api()
        corrected = correct_operator(
            [[3.0, 0.0], [0.0, 1.0]],
            [[0, 1]],
            {"charge": 0.5, "internal": 2.0, "nonlocal": 1.0},
        )
        assert_matrix_close(self, corrected, [[3.0, 0.0], [0.0, -1.0]])

    def test_all_and_only_known_channel_kernels_are_required(self):
        correct_operator = self.load_api()
        with self.assertRaisesRegex(ValueError, "kernels"):
            correct_operator(
                [[1.0, 0.0], [0.0, 1.0]],
                [[0, 1]],
                {"charge": 1.0, "internal": 1.0},
            )
        with self.assertRaisesRegex(ValueError, "kernels"):
            correct_operator(
                [[1.0, 0.0], [0.0, 1.0]],
                [[0, 1]],
                {
                    "charge": 1.0,
                    "internal": 1.0,
                    "nonlocal": 1.0,
                    "spin": 1.0,
                },
            )


if __name__ == "__main__":
    unittest.main()
