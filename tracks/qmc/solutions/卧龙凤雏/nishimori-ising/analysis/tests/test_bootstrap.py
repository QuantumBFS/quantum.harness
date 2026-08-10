import numpy as np

from analysis.bootstrap import hierarchical_central_charge_bootstrap


def test_joint_width_bootstrap_is_deterministic_and_preserves_shared_fluctuations():
    widths = np.array([4, 6, 8, 10, 12, 14], dtype=float)
    base = 1.2 + np.pi * 0.464 / (6.0 * widths**2) - 0.2 / widths**4
    tensor = np.empty((4, 12, len(widths)))
    for replica in range(tensor.shape[0]):
        for block in range(tensor.shape[1]):
            shared = (replica - 1.5) * 2.0e-4 + (block - 5.5) * 1.0e-5
            tensor[replica, block] = base + shared / widths**2

    first = hierarchical_central_charge_bootstrap(
        tensor, widths, minimum_width=4, samples=128, seed=991
    )
    second = hierarchical_central_charge_bootstrap(
        tensor, widths, minimum_width=4, samples=128, seed=991
    )
    assert np.array_equal(first, second)
    assert first.shape == (128,)
    assert np.std(first, ddof=1) > 0.0
