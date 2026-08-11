import numpy as np
import pytest

from floquet_if_manybody.convergence import (
    ConvergenceCache,
    atomic_write_result,
    curve_residual,
    fingerprint,
    state_residual,
)


def test_fingerprint_is_order_independent_and_commit_sensitive():
    first = fingerprint({"alpha": 0.1, "dt": 0.2}, "abc")
    second = fingerprint({"dt": 0.2, "alpha": 0.1}, "abc")
    assert first == second
    assert first != fingerprint({"alpha": 0.1, "dt": 0.2}, "def")


def test_curve_and_state_residuals():
    grid = np.linspace(0, 1, 11)
    assert curve_residual(grid, grid, grid, grid) == 0
    assert state_residual(np.eye(2), np.eye(2)) == 0
    with pytest.raises(ValueError, match="grid"):
        curve_residual(np.arange(3.0), np.ones(3), np.arange(4.0), np.ones(4))


def test_cache_rejects_incomplete_or_wrong_key(tmp_path):
    key = fingerprint({"x": 1}, "abc")
    cache = ConvergenceCache(tmp_path)
    cache.store(key, {"value": 3})
    assert cache.load(key)["value"] == 3
    atomic_write_result(cache.path_for(key), {"fingerprint": key, "complete": False})
    with pytest.raises(ValueError, match="incomplete"):
        cache.load(key)
