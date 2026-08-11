import numpy as np
from numpy.testing import assert_allclose

from floquet_if_manybody.backends.finite_memory import FiniteMemoryBackend
from floquet_if_manybody.config import BathConfig


def test_zero_bath_matches_unitary_evolution():
    h = np.array([[0, 0.4], [0.4, 0]], dtype=complex)
    coupling = np.diag([1, -1]).astype(complex)
    rho0 = np.array([[1, 0], [0, 0]], dtype=complex)
    dt = 0.05
    result = FiniteMemoryBackend().run(
        lambda _time: h, coupling, rho0, BathConfig(alpha=0), dt, 10, 2
    )
    unitary = expm_for_test(h, 10 * dt)
    assert_allclose(result.density_matrices[-1], unitary @ rho0 @ unitary.conj().T, atol=1e-12)
    assert result.diagnostics["trace_error"] < 1e-12


def expm_for_test(hamiltonian, time):
    from scipy.linalg import expm

    return expm(-1j * hamiltonian * time)
