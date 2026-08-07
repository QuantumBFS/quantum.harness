import math
import numpy as np
import pytest

from scalable_v1.statistics import blocking_estimate, combine_independent, normalized_residual


def test_blocking_estimate_uses_block_means() -> None:
    values = np.arange(16, dtype=float).reshape(2, 8)
    result = blocking_estimate(values, block_size=2)
    blocks = values.reshape(2, 4, 2).mean(axis=2).ravel()
    assert result.mean == np.mean(values)
    assert result.standard_error == np.std(blocks, ddof=1) / math.sqrt(8)
    assert 0.0 < result.effective_sample_size <= 16.0


def test_complex_input_tracks_imaginary_drift() -> None:
    result = blocking_estimate(np.ones((2, 8), dtype=complex) + 2e-9j, block_size=2)
    assert result.mean == 1.0
    assert result.maximum_imaginary_part == 2e-9


def test_error_propagation_and_residual() -> None:
    assert combine_independent(3.0, 0.3, 2.0, 0.4) == (1.0, 0.5)
    assert normalized_residual(np.array([1, 2]), np.array([1, 2])) == 0.0


def test_blocking_estimate_rejects_nonfinite_values() -> None:
    with pytest.raises(ValueError, match="finite"):
        blocking_estimate(np.array([[1.0, np.nan]]), block_size=1)


def test_blocking_estimate_rejects_zero_block_size() -> None:
    with pytest.raises(ValueError, match="divisible blocks"):
        blocking_estimate(np.ones((1, 2)), block_size=0)


def test_normalized_residual_rejects_empty_inputs() -> None:
    with pytest.raises(ValueError, match="nonempty"):
        normalized_residual(np.array([]), np.array([]))


def test_normalized_residual_rejects_shape_mismatch() -> None:
    with pytest.raises(ValueError, match="same shape"):
        normalized_residual(np.ones(3), np.array(1.0))


@pytest.mark.parametrize(
    ("actual", "expected"),
    [
        (np.array([np.nan]), np.array([0.0])),
        (np.array([0.0]), np.array([np.inf])),
    ],
)
def test_normalized_residual_rejects_nonfinite_inputs(actual: np.ndarray, expected: np.ndarray) -> None:
    with pytest.raises(ValueError, match="finite"):
        normalized_residual(actual, expected)


@pytest.mark.parametrize("values", [np.empty((0, 2)), np.empty((1, 0))])
def test_blocking_estimate_rejects_empty_axes(values: np.ndarray) -> None:
    with pytest.raises(ValueError, match="nonempty"):
        blocking_estimate(values, block_size=1)


@pytest.mark.parametrize(
    "args",
    [
        (np.nan, 0.1, 0.0, 0.1),
        (0.0, 0.1, np.inf, 0.1),
        (0.0, np.nan, 0.0, 0.1),
        (0.0, 0.1, 0.0, np.inf),
    ],
)
def test_combine_independent_rejects_nonfinite_inputs(args: tuple[float, float, float, float]) -> None:
    with pytest.raises(ValueError, match="finite"):
        combine_independent(*args)


@pytest.mark.parametrize("args", [(0.0, -0.1, 0.0, 0.1), (0.0, 0.1, 0.0, -0.1)])
def test_combine_independent_rejects_negative_errors(args: tuple[float, float, float, float]) -> None:
    with pytest.raises(ValueError, match="nonnegative"):
        combine_independent(*args)


def test_scalar_estimate_characterization() -> None:
    values = np.arange(4, dtype=float).reshape(1, 4)
    result = blocking_estimate(values, block_size=2)
    blocks = values.reshape(1, 2, 2).mean(axis=2).ravel()
    expected_variance = float(np.var(values, ddof=1))
    expected_standard_error = float(np.std(blocks, ddof=1) / math.sqrt(blocks.size))
    expected_ess = min(float(values.size), expected_variance / expected_standard_error**2)
    assert result.variance == expected_variance
    assert result.effective_sample_size == expected_ess
    assert result.to_dict() == {
        "mean": float(np.mean(values)),
        "variance": expected_variance,
        "standard_error": expected_standard_error,
        "effective_sample_size": expected_ess,
        "maximum_imaginary_part": 0.0,
    }


def test_blocking_estimate_keeps_single_block() -> None:
    result = blocking_estimate(np.array([[2.0]]), block_size=1)
    assert result.standard_error == 0.0
    assert result.effective_sample_size == 1.0
