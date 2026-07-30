"""Fit and apply a small channel-response matrix from supplied anchors."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import math
from numbers import Number


_PIVOT_RELATIVE_TOLERANCE = 1.0e-12
_REAL_TOLERANCE = 1.0e-14


def _decode_number(value: object, name: str) -> complex:
    if isinstance(value, Mapping):
        if set(value) != {"real", "imag"}:
            raise ValueError(f"{name} complex values require real and imag fields")
        try:
            value = complex(value["real"], value["imag"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} values must be numeric") from exc
    elif isinstance(value, Number):
        value = complex(value)
    else:
        raise ValueError(f"{name} values must be numeric")
    if not math.isfinite(value.real) or not math.isfinite(value.imag):
        raise ValueError(f"{name} values must be finite")
    return value


def _encode_number(value: complex) -> float | dict[str, float]:
    real = 0.0 if abs(value.real) <= _REAL_TOLERANCE else float(value.real)
    imag = 0.0 if abs(value.imag) <= _REAL_TOLERANCE else float(value.imag)
    if imag == 0.0:
        return real
    return {"real": real, "imag": imag}


def _as_numeric_matrix(
    values: object,
    name: str,
    expected_columns: int | None = None,
) -> list[list[complex]]:
    if (
        not isinstance(values, Sequence)
        or isinstance(values, (str, bytes))
        or not values
    ):
        raise ValueError(f"{name} must be a nonempty matrix")

    matrix: list[list[complex]] = []
    columns = expected_columns
    for row_index, row in enumerate(values):
        if (
            not isinstance(row, Sequence)
            or isinstance(row, (str, bytes))
            or not row
        ):
            raise ValueError(f"{name} row {row_index} must be nonempty")
        if columns is None:
            columns = len(row)
        if len(row) != columns:
            raise ValueError(f"{name} rows must have the same channel count")
        matrix.append(
            [
                _decode_number(value, f"{name}[{row_index}]")
                for value in row
            ]
        )
    return matrix


def _validate_ridge(ridge: object) -> float:
    if isinstance(ridge, bool) or not isinstance(ridge, Number):
        raise ValueError("ridge must be a nonnegative real number")
    numeric = complex(ridge)
    if numeric.imag != 0.0 or not math.isfinite(numeric.real) or numeric.real < 0.0:
        raise ValueError("ridge must be a nonnegative real number")
    return float(numeric.real)


def _solve_linear_system(
    matrix: list[list[complex]],
    right_hand_side: list[list[complex]],
) -> list[list[complex]]:
    size = len(matrix)
    output_count = len(right_hand_side[0])
    augmented = [matrix[row][:] + right_hand_side[row][:] for row in range(size)]
    matrix_scale = max(abs(value) for row in matrix for value in row)
    if matrix_scale == 0.0:
        raise ValueError("unregularized response fit is singular; add anchors or ridge")
    pivot_tolerance = _PIVOT_RELATIVE_TOLERANCE * matrix_scale

    for column in range(size):
        pivot_row = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        pivot = augmented[pivot_row][column]
        if abs(pivot) <= pivot_tolerance:
            raise ValueError("unregularized response fit is singular; add anchors or ridge")
        augmented[column], augmented[pivot_row] = augmented[pivot_row], augmented[column]

        pivot = augmented[column][column]
        augmented[column] = [value / pivot for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            if factor == 0.0:
                continue
            augmented[row] = [
                value - factor * pivot_value
                for value, pivot_value in zip(augmented[row], augmented[column])
            ]

    return [row[size : size + output_count] for row in augmented]


def error_metrics(
    predicted: Sequence[Sequence[object]],
    reference: Sequence[Sequence[object]],
) -> dict[str, float | None]:
    """Return absolute and reference-normalized errors for coefficient matrices."""

    predicted_matrix = _as_numeric_matrix(predicted, "predicted")
    reference_matrix = _as_numeric_matrix(
        reference,
        "reference",
        expected_columns=len(predicted_matrix[0]),
    )
    if len(predicted_matrix) != len(reference_matrix):
        raise ValueError("predicted and reference must contain the same number of samples")

    errors = [
        predicted_value - reference_value
        for predicted_row, reference_row in zip(predicted_matrix, reference_matrix)
        for predicted_value, reference_value in zip(predicted_row, reference_row)
    ]
    reference_values = [value for row in reference_matrix for value in row]
    error_norm_squared = sum(abs(value) ** 2 for value in errors)
    reference_norm_squared = sum(abs(value) ** 2 for value in reference_values)
    rmse = math.sqrt(error_norm_squared / len(errors))
    if reference_norm_squared == 0.0:
        relative_rmse = 0.0 if error_norm_squared == 0.0 else None
    else:
        relative_rmse = math.sqrt(error_norm_squared / reference_norm_squared)
    return {
        "rmse": rmse,
        "relative_rmse": relative_rmse,
        "max_abs_error": max(abs(value) for value in errors),
    }


def predict_coefficients(
    model: Mapping[str, object],
    inputs: Sequence[Sequence[object]],
) -> list[list[complex]]:
    """Apply a fitted channel-response matrix to coefficient vectors."""

    try:
        channel_count = int(model["channel_count"])
        encoded_response = model["response_matrix"]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("model is missing a valid channel response") from exc
    response = _as_numeric_matrix(
        encoded_response,
        "response_matrix",
        expected_columns=channel_count,
    )
    if len(response) != channel_count:
        raise ValueError("response_matrix must be square in channel space")
    input_matrix = _as_numeric_matrix(inputs, "inputs", expected_columns=channel_count)
    return [
        [
            sum(response[output][channel] * row[channel] for channel in range(channel_count))
            for output in range(channel_count)
        ]
        for row in input_matrix
    ]


def fit_response_matrix(
    inputs: Sequence[Sequence[object]],
    targets: Sequence[Sequence[object]],
    ridge: Number = 0.0,
) -> dict[str, object]:
    """Fit ``target = response_matrix @ input`` from declared anchors."""

    ridge_value = _validate_ridge(ridge)
    input_matrix = _as_numeric_matrix(inputs, "inputs")
    channel_count = len(input_matrix[0])
    target_matrix = _as_numeric_matrix(
        targets,
        "targets",
        expected_columns=channel_count,
    )
    if len(input_matrix) != len(target_matrix):
        raise ValueError("inputs and targets must contain the same number of anchors")

    input_scales = [
        math.sqrt(sum(abs(row[channel]) ** 2 for row in input_matrix))
        for channel in range(channel_count)
    ]
    if any(scale == 0.0 for scale in input_scales):
        raise ValueError("every input channel must be excited by at least one anchor")
    normalized_inputs = [
        [value / input_scales[channel] for channel, value in enumerate(row)]
        for row in input_matrix
    ]

    gram = [
        [
            sum(row[left].conjugate() * row[right] for row in normalized_inputs)
            + (ridge_value if left == right else 0.0)
            for right in range(channel_count)
        ]
        for left in range(channel_count)
    ]
    right_hand_side = [
        [
            sum(
                input_row[channel].conjugate() * target_row[output]
                for input_row, target_row in zip(normalized_inputs, target_matrix)
            )
            for output in range(channel_count)
        ]
        for channel in range(channel_count)
    ]
    normalized_coefficients = _solve_linear_system(gram, right_hand_side)
    coefficients = [
        [value / input_scales[channel] for value in normalized_coefficients[channel]]
        for channel in range(channel_count)
    ]
    response = [
        [coefficients[input_channel][output] for input_channel in range(channel_count)]
        for output in range(channel_count)
    ]
    encoded_response = [[_encode_number(value) for value in row] for row in response]
    model: dict[str, object] = {
        "response_matrix": encoded_response,
        "channel_count": channel_count,
        "anchor_count": len(input_matrix),
        "ridge": ridge_value,
        "ridge_basis": "column-normalized",
        "input_scales": input_scales,
    }
    training_prediction = predict_coefficients(model, input_matrix)
    model["training_metrics"] = error_metrics(training_prediction, target_matrix)
    return model
