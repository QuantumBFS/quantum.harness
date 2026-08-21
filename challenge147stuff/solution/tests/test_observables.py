import math
from core.observables import (
    ThermoResult, rel_err, within_tol, thermodynamics_from_logZ, free_energy_from_u
)


def test_rel_err_basic():
    assert rel_err(1.0, 1.0) == 0.0
    assert abs(rel_err(1.1, 1.0) - 0.1) < 1e-12
    assert rel_err(2.0, 0.0) == 2.0  # b==0 -> abs diff


def test_within_tol():
    assert within_tol(1.01, 1.0, 0.02) is True
    assert within_tol(1.05, 1.0, 0.02) is False


def test_thermo_from_logZ_free_energy_and_C():
    # two-level toy: energies 0 and 1, partition Z = 1 + e^{-beta}
    beta = 1.0
    N = 1
    Z = 1 + math.exp(-beta)
    logZ = math.log(Z)
    E_mean = (0 * 1 + 1 * math.exp(-beta)) / Z
    E2_mean = (0 * 1 + 1 * math.exp(-beta)) / Z
    r = thermodynamics_from_logZ(beta, N, logZ, E_mean, E2_mean)
    assert abs(r.f - (-logZ / (beta * N))) < 1e-12
    assert abs(r.u - E_mean / N) < 1e-12
    assert abs(r.C - beta ** 2 * (E2_mean - E_mean ** 2) / N) < 1e-12


def test_free_energy_from_u_known():
    # Traceless two-level system (N=1), energies {-1/2, +1/2} (so u(0)=0, matching
    # the traceless-TFIM assumption). Z = 2 cosh(b/2), u = -tanh(b/2)/2,
    # f = -(1/b) ln(2 cosh(b/2)). free_energy_from_u must reconstruct f from u.
    betas = [0.05 * k for k in range(1, 31)]           # 0.05 .. 1.50, step 0.05
    us = [-math.tanh(b / 2.0) / 2.0 for b in betas]
    fs = free_energy_from_u(betas, us, local_dim=2)
    for b, f in zip(betas, fs):
        f_exact = -(1.0 / b) * math.log(2.0 * math.cosh(b / 2.0))
        assert abs(f - f_exact) < 5e-3, f"b={b} f={f} exact={f_exact}"
