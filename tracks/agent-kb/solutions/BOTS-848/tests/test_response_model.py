import importlib
import json
import math
import unittest


def decode_number(value):
    if isinstance(value, dict):
        return complex(value["real"], value["imag"])
    return complex(value)


def assert_matrix_close(test_case, actual, expected, places=10):
    test_case.assertEqual(len(actual), len(expected))
    for actual_row, expected_row in zip(actual, expected):
        test_case.assertEqual(len(actual_row), len(expected_row))
        for actual_value, expected_value in zip(actual_row, expected_row):
            actual_number = decode_number(actual_value)
            expected_number = complex(expected_value)
            test_case.assertAlmostEqual(actual_number.real, expected_number.real, places=places)
            test_case.assertAlmostEqual(actual_number.imag, expected_number.imag, places=places)


class ResponseModelTests(unittest.TestCase):
    def load_api(self):
        try:
            module = importlib.import_module("src.response_model")
        except ModuleNotFoundError:
            self.fail("src.response_model has not been implemented")
        return module.fit_response_matrix, module.predict_coefficients, module.error_metrics

    def test_identity_response_is_recovered(self):
        fit_response_matrix, predict_coefficients, _ = self.load_api()
        inputs = [[1, 0], [0, 1], [1, 1]]
        model = fit_response_matrix(inputs, inputs)

        assert_matrix_close(self, model["response_matrix"], [[1, 0], [0, 1]])
        assert_matrix_close(self, predict_coefficients(model, [[2, -1]]), [[2, -1]])
        self.assertEqual(model["channel_count"], 2)
        self.assertEqual(model["anchor_count"], 3)
        self.assertEqual(model["ridge"], 0.0)

    def test_off_diagonal_response_predicts_held_out_vector(self):
        fit_response_matrix, predict_coefficients, _ = self.load_api()
        inputs = [[1, 0], [0, 1], [1, 1]]
        targets = [[2, 0.5], [1, 3], [3, 3.5]]

        model = fit_response_matrix(inputs, targets)

        assert_matrix_close(self, model["response_matrix"], [[2, 1], [0.5, 3]])
        assert_matrix_close(self, predict_coefficients(model, [[2, -1]]), [[3, -2]])

    def test_complex_response_model_is_json_serializable(self):
        fit_response_matrix, predict_coefficients, _ = self.load_api()
        model = fit_response_matrix(
            [[1, 0], [0, 1]],
            [[1j, 0], [0, 1]],
        )

        json.dumps(model)
        self.assertEqual(model["response_matrix"][0][0], {"real": 0.0, "imag": 1.0})
        assert_matrix_close(self, predict_coefficients(model, [[2, 3]]), [[2j, 3]])

    def test_error_metrics_report_absolute_and_relative_error(self):
        _, _, error_metrics = self.load_api()
        metrics = error_metrics([[2.0, 0.0]], [[1.0, 0.0]])

        self.assertAlmostEqual(metrics["rmse"], math.sqrt(0.5))
        self.assertAlmostEqual(metrics["relative_rmse"], 1.0)
        self.assertAlmostEqual(metrics["max_abs_error"], 1.0)

    def test_zero_reference_has_defined_relative_error_behavior(self):
        _, _, error_metrics = self.load_api()
        exact = error_metrics([[0.0]], [[0.0]])
        inexact = error_metrics([[1.0]], [[0.0]])

        self.assertEqual(exact["relative_rmse"], 0.0)
        self.assertIsNone(inexact["relative_rmse"])

    def test_invalid_training_data_are_rejected(self):
        fit_response_matrix, _, _ = self.load_api()
        invalid_cases = (
            ([], [], 0.0),
            ([[1, 2], [3]], [[1, 2], [3, 4]], 0.0),
            ([[1, "bad"]], [[1, 2]], 0.0),
            ([[{"real": "bad", "imag": 0}, 0]], [[1, 2]], 0.0),
            ([[1, 0]], [[1, 0], [0, 1]], 0.0),
            ([[1, 0]], [[1]], 0.0),
            ([[1, 0]], [[1, 0]], -1.0),
            ([[1, 0]], [[1, 0]], "bad"),
            ([[1, 0], [0, 1]], [[1, 0], [0, 1]], True),
        )

        for inputs, targets, ridge in invalid_cases:
            with self.subTest(inputs=inputs, targets=targets, ridge=ridge):
                with self.assertRaises(ValueError):
                    fit_response_matrix(inputs, targets, ridge=ridge)

    def test_singular_unregularized_fit_fails_explicitly(self):
        fit_response_matrix, _, _ = self.load_api()
        with self.assertRaisesRegex(ValueError, "singular"):
            fit_response_matrix(
                [[1, 1], [2, 2]],
                [[1, 1], [2, 2]],
            )

    def test_positive_ridge_regularizes_rank_deficient_fit(self):
        fit_response_matrix, predict_coefficients, _ = self.load_api()
        model = fit_response_matrix(
            [[1, 1], [2, 2]],
            [[1, 1], [2, 2]],
            ridge=1.0e-6,
        )

        prediction = predict_coefficients(model, [[3, 3]])
        self.assertAlmostEqual(prediction[0][0].real, 3.0, places=5)
        self.assertAlmostEqual(prediction[0][1].real, 3.0, places=5)

    def test_fit_does_not_depend_on_the_absolute_coefficient_unit(self):
        fit_response_matrix, predict_coefficients, _ = self.load_api()
        scale = 1.0e-8
        model = fit_response_matrix(
            [[scale, 0.0], [0.0, scale]],
            [[2.0 * scale, 0.5 * scale], [scale, 3.0 * scale]],
        )

        assert_matrix_close(self, model["response_matrix"], [[2.0, 1.0], [0.5, 3.0]])
        assert_matrix_close(
            self,
            predict_coefficients(model, [[2.0 * scale, -scale]]),
            [[3.0 * scale, -2.0 * scale]],
        )

    def test_fit_handles_channels_with_different_coefficient_scales(self):
        fit_response_matrix, _, _ = self.load_api()
        small = 1.0e-8
        model = fit_response_matrix(
            [[1.0, 0.0], [0.0, small]],
            [[2.0, 0.5], [small, 3.0 * small]],
        )

        assert_matrix_close(self, model["response_matrix"], [[2.0, 1.0], [0.5, 3.0]])

    def test_prediction_shape_must_match_fitted_channels(self):
        fit_response_matrix, predict_coefficients, _ = self.load_api()
        model = fit_response_matrix([[1, 0], [0, 1]], [[1, 0], [0, 1]])

        with self.assertRaisesRegex(ValueError, "channel"):
            predict_coefficients(model, [[1, 2, 3]])


if __name__ == "__main__":
    unittest.main()
