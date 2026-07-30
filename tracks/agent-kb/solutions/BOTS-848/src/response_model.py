"""Fit and apply a small channel-response matrix from supplied anchors."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import math
from numbers import Number


_PIVOT_RELATIVE_TOLERANCE = 1.0e-12


def _decode_number(value: object, name: str) -> complex:
    if isinstance(value, Mapping):
        if set(value) != {"real", "imag"}:
            raise ValueError(f"{name} complex values require real and imag fields")
        if isinstance(value["real"], bool) or isinstance(value["imag"], bool):
            raise ValueError(f"{name} values must be numeric")
        try:
            value = complex(value["real"], value["imag"])
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"{name} values must be numeric") from exc
    elif isinstance(value, Number) and not isinstance(value, bool):
        try:
            value = complex(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"{name} values must be numeric") from exc
    else:
        raise ValueError(f"{name} values must be numeric")
    if not math.isfinite(value.real) or not math.isfinite(value.imag):
        raise ValueError(f"{name} values must be finite")
    return value


def _encode_number(value: complex) -> float | dict[str, float]:
    if not math.isfinite(value.real) or not math.isfinite(value.imag):
        raise ValueError("response values must remain finite")
    real = float(value.real)
    imag = float(value.imag)
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


def _require_finite(value: complex, name: str) -> complex:
    if not math.isfinite(value.real) or not math.isfinite(value.imag):
        raise ValueError(f"{name} must remain finite")
    return value


def _finite_sum(values, name: str) -> complex:
    total = 0.0j
    try:
        for value in values:
            total = _require_finite(total + value, name)
    except OverflowError as exc:
        raise ValueError(f"{name} must remain finite") from exc
    return total


def _stable_norm(values, name: str) -> float:
    try:
        norm = math.hypot(*(abs(value) for value in values))
    except OverflowError as exc:
        raise ValueError(f"{name} must remain finite") from exc
    if not math.isfinite(norm):
        raise ValueError(f"{name} must remain finite")
    return norm


def _validate_ridge(ridge: object) -> float:
    if isinstance(ridge, bool) or not isinstance(ridge, Number):
        raise ValueError("ridge must be a nonnegative real number")
    try:
        numeric = complex(ridge)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("ridge must be a nonnegative real number") from exc
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
        try:
            augmented[column] = [
                _require_finite(value / pivot, "response fit intermediates")
                for value in augmented[column]
            ]
        except OverflowError as exc:
            raise ValueError("response fit intermediates must remain finite") from exc
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            if factor == 0.0:
                continue
            try:
                augmented[row] = [
                    _require_finite(
                        value - factor * pivot_value,
                        "response fit intermediates",
                    )
                    for value, pivot_value in zip(augmented[row], augmented[column])
                ]
            except OverflowError as exc:
                raise ValueError("response fit intermediates must remain finite") from exc

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
    for value in errors:
        _require_finite(value, "derived errors")
    error_norm = _stable_norm(errors, "error norm")
    reference_norm = _stable_norm(reference_values, "reference norm")
    rmse = error_norm / math.sqrt(len(errors))
    if reference_norm == 0.0:
        relative_rmse = 0.0 if error_norm == 0.0 else None
    else:
        relative_rmse = error_norm / reference_norm
        if not math.isfinite(relative_rmse):
            raise ValueError("relative error metric must remain finite")
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
        channel_count = model["channel_count"]
        encoded_response = model["response_matrix"]
    except KeyError as exc:
        raise ValueError("model is missing a valid channel response") from exc
    if (
        isinstance(channel_count, bool)
        or not isinstance(channel_count, int)
        or channel_count <= 0
    ):
        raise ValueError("model channel_count must be a positive integer")
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
            _finite_sum(
                (
                    response[output][channel] * row[channel]
                    for channel in range(channel_count)
                ),
                "predicted coefficients",
            )
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
        _stable_norm(
            (row[channel] for row in input_matrix),
            "input channel norm",
        )
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
            _require_finite(
                _finite_sum(
                    (
                        row[left].conjugate() * row[right]
                        for row in normalized_inputs
                    ),
                    "response Gram matrix",
                )
                + (ridge_value if left == right else 0.0),
                "response Gram matrix",
            )
            for right in range(channel_count)
        ]
        for left in range(channel_count)
    ]
    right_hand_side = [
        [
            _finite_sum(
                (
                    input_row[channel].conjugate() * target_row[output]
                    for input_row, target_row in zip(normalized_inputs, target_matrix)
                ),
                "response right-hand side",
            )
            for output in range(channel_count)
        ]
        for channel in range(channel_count)
    ]
    normalized_coefficients = _solve_linear_system(gram, right_hand_side)
    coefficients = []
    for channel in range(channel_count):
        try:
            coefficients.append(
                [
                    _require_finite(
                        value / input_scales[channel],
                        "response coefficients",
                    )
                    for value in normalized_coefficients[channel]
                ]
            )
        except OverflowError as exc:
            raise ValueError("response coefficients must remain finite") from exc
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
