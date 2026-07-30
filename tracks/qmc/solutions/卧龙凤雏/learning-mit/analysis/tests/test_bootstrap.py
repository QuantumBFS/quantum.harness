import numpy as np

from analysis.bootstrap import hierarchical_bootstrap_means


def test_hierarchical_bootstrap_resamples_streams_then_complete_blocks():
    groups = {
        8: (
            np.array([1.0, 1.2, 0.8]),
            np.array([2.0, 2.2, 1.8]),
        ),
        12: (
            np.array([3.0, 3.2, 2.8]),
            np.array([4.0, 4.2, 3.8]),
        ),
    }
    samples = hierarchical_bootstrap_means(groups, samples=300, seed=122)

    assert samples.shape == (300, 2)
    assert np.allclose(samples.mean(axis=0), [1.5, 3.5], atol=0.12)
    assert np.all(np.diag(np.cov(samples, rowvar=False)) > 0)
    assert not np.allclose(samples[:, 0], samples[:, 1])
