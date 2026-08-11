import numpy as np

from floquet_if_manybody.backends.floquet_markov import FloquetMarkovBackend
from floquet_if_manybody.config import BathConfig


def test_markov_result_is_trace_preserving_and_labeled():
    h = np.array([[0.5, 0.2], [0.2, -0.5]], dtype=complex)
    s = np.diag([1, -1]).astype(complex)
    result = FloquetMarkovBackend().run(
        lambda _time: h, s, BathConfig(alpha=0.01), 2 * np.pi, 64, 2
    )
    assert result.method == "floquet_markov"
    assert result.diagnostics["trace_error"] < 1e-12
    assert result.diagnostics["minimum_population"] >= -1e-12
