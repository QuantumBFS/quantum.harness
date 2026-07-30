import importlib
import unittest


def assert_matrix_close(test_case, actual, expected, places=12):
    test_case.assertEqual(len(actual), len(expected))
    for actual_row, expected_row in zip(actual, expected):
        test_case.assertEqual(len(actual_row), len(expected_row))
        for actual_value, expected_value in zip(actual_row, expected_row):
            test_case.assertAlmostEqual(actual_value.real, complex(expected_value).real, places=places)
            test_case.assertAlmostEqual(actual_value.imag, complex(expected_value).imag, places=places)


VALID_KERNELS = {
    "global_charge": 1.0,
    "site_charge": 1.0,
    "internal": 1.0,
    "nonlocal": 1.0,
}


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
        corrected = correct_operator(operator, [[0, 1]], VALID_KERNELS)
        assert_matrix_close(self, corrected, operator)

    def test_each_channel_can_receive_a_distinct_real_kernel(self):
        correct_operator = self.load_api()
        corrected = correct_operator(
            [
                [3.0, 1.0, 0.5, 0.0],
                [1.0, 1.0, 0.0, 0.2],
                [0.5, 0.0, -1.0, 2.0],
                [0.0, 0.2, 2.0, 1.0],
            ],
            [[0, 1], [2, 3]],
            {"global_charge": 2.0, "site_charge": 3.0, "internal": 4.0, "nonlocal": 5.0},
        )
        assert_matrix_close(
            self,
            corrected,
            [
                [9.0, 4.0, 2.5, 0.0],
                [4.0, 1.0, 0.0, 1.0],
                [2.5, 0.0, -5.0, 8.0],
                [0.0, 1.0, 8.0, 3.0],
            ],
        )

    def test_all_and_only_four_known_channel_kernels_are_required(self):
        correct_operator = self.load_api()
        with self.assertRaisesRegex(ValueError, "kernels"):
            correct_operator(
                [[1.0, 0.0], [0.0, 1.0]],
                [[0, 1]],
                {"global_charge": 1.0, "site_charge": 1.0, "internal": 1.0},
            )
        with self.assertRaisesRegex(ValueError, "kernels"):
            correct_operator(
                [[1.0, 0.0], [0.0, 1.0]],
                [[0, 1]],
                dict(VALID_KERNELS, spin=1.0),
            )

    def test_kernels_must_be_finite_real_scalars_and_not_booleans(self):
        correct_operator = self.load_api()
        invalid_values = (True, 1.0 + 0.0j, float("nan"), float("inf"), -float("inf"), "1.0")
        for invalid in invalid_values:
            with self.subTest(invalid=invalid):
                kernels = dict(VALID_KERNELS, global_charge=invalid)
                with self.assertRaisesRegex(ValueError, "finite real scalar"):
                    correct_operator([[1.0, 0.0], [0.0, 1.0]], [[0, 1]], kernels)

    def test_finite_inputs_must_not_overflow_the_corrected_operator(self):
        correct_operator = self.load_api()
        kernels = dict(VALID_KERNELS, global_charge=2.0)

        with self.assertRaisesRegex(ValueError, "finite"):
            correct_operator([[1.0e308]], [[0]], kernels)


if __name__ == "__main__":
    unittest.main()
