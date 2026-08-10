import numpy as np

from analysis.bootstrap import bootstrap_fits, hierarchical_mean_bootstrap


def synthetic_blocks():
    widths = np.arange(6, 32, 2, dtype=int)
    blocks = {}
    for width in widths:
        mean = 0.73 * width - np.pi * 0.447 / (6.0 * width) + 1.2 / width**3
        blocks[int(width)] = np.asarray(
            [[mean + stream * 1e-4 + block * 1e-5 for block in range(8)] for stream in range(4)]
        )
    return widths, blocks


def test_hierarchical_bootstrap_is_seed_reproducible():
    widths, blocks = synthetic_blocks()
    first = hierarchical_mean_bootstrap(blocks, widths, samples=50, seed=447122)
    second = hierarchical_mean_bootstrap(blocks, widths, samples=50, seed=447122)
    np.testing.assert_array_equal(first, second)


def test_bootstrap_primary_fit_centers_on_constructed_value():
    widths, blocks = synthetic_blocks()
    sigma = np.full(len(widths), 1e-3)
    fits = bootstrap_fits(blocks, widths, sigma, samples=100, seed=447122)
    assert abs(np.mean(fits["primary"]) - 0.447) < 0.01
    assert set(["primary", "lmin8", "lmin10", "extra_burnin", "double_block"]).issubset(fits)
