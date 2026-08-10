import numpy as np

from analysis.bootstrap import hierarchical_bootstrap_means, summarize_bootstrap


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


def test_bootstrap_summary_tracks_valid_replicates_interval_and_failures():
    samples = np.linspace(0.2, 0.8, 100)
    samples[:4] = np.nan
    summary = summarize_bootstrap(samples, requested=100)
    assert summary.valid_replicates == 96
    assert summary.failure_fraction == 0.04
    assert summary.interval[0] < summary.estimate < summary.interval[1]
    assert not summary.unavailable

    samples[:6] = np.nan
    assert summarize_bootstrap(samples, requested=100).unavailable
