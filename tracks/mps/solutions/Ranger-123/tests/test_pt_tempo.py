import numpy as np
import pytest

from floquet_if_manybody.backends.pt_tempo import PtTempoBackend
from floquet_if_manybody.config import BathConfig

oqupy = pytest.importorskip("oqupy")
if np.lib.NumpyVersion(np.__version__) >= "2.0.0":
    pytest.skip("OQuPy 0.5 requires NumPy <2", allow_module_level=True)


def test_pt_tempo_short_run_is_labeled_and_trace_preserving():
    h = np.array([[0, 0.5], [0.5, 0]], dtype=complex)
    s = np.diag([1, -1]).astype(complex)
    rho = np.array([[1, 0], [0, 0]], dtype=complex)
    run = PtTempoBackend().run(
        lambda _time: h,
        s,
        rho,
        BathConfig(alpha=0.01),
        dt=0.1,
        steps=6,
        memory_steps=2,
        epsrel=1e-5,
    )
    assert run.result.method == "pt_tempo"
    assert run.result.diagnostics["trace_error"] < 1e-3
    assert run.result.metadata["spectral_density_convention"].startswith(
        "OQuPy alpha divided"
    )
