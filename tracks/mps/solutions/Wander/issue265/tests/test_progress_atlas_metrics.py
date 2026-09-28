import numpy as np

from src.progress_atlas.metrics import normalized_even_odd_residual, profile_error


def test_profile_error_is_zero_for_equal_arrays() -> None:
    a = np.array([[1.0, 2.0]])
    result = profile_error(a, a, 0.0, np.array([True, True]))
    assert result["relative_l2"][0] == 0.0


def test_spin_flip_residual_vanishes_for_opposites() -> None:
    up = np.array([[1.0, -2.0]])
    down = -up
    result = normalized_even_odd_residual(up, down)
    assert result[0] == 0.0
