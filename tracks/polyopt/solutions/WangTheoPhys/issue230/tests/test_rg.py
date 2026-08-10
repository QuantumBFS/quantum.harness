import numpy as np

from xxzcert.rg import build_density_guided_rg_map, verify_rg_map
from xxzcert.upper import optimize_block_state


def test_density_guided_map_is_an_isometry():
    candidate = optimize_block_state(1.0, 6)
    rg_map = build_density_guided_rg_map(candidate, block_sites=2, kept_dimension=2)
    assert verify_rg_map(rg_map)
    assert rg_map.isometry_residual < 1e-12
    assert 0 <= rg_map.discarded_weight <= 1


def test_compression_preserves_hermiticity_and_positivity():
    candidate = optimize_block_state(1.0, 6)
    rg_map = build_density_guided_rg_map(candidate, block_sites=2, kept_dimension=2)
    operator = np.diag([1.0, 2.0, 3.0, 4.0]).astype(complex)
    compressed = rg_map.compress_operator(operator)
    assert np.allclose(compressed, compressed.conj().T)
    assert np.linalg.eigvalsh(compressed)[0] >= -1e-12


def test_lifted_state_is_positive_and_trace_preserving():
    candidate = optimize_block_state(0.5, 6)
    rg_map = build_density_guided_rg_map(candidate, block_sites=2, kept_dimension=2)
    coarse = np.array([[0.7, 0.1], [0.1, 0.3]], dtype=complex)
    lifted = rg_map.lift_state(coarse)
    assert np.isclose(np.trace(lifted), 1)
    assert np.linalg.eigvalsh(lifted)[0] >= -1e-12
