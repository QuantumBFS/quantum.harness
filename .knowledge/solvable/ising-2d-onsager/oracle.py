"""2D square-lattice classical Ising oracle: H = -J sum_<ij> s_i s_j, s = +-1.

Classical statistical model (the catalog's first). Conventions: J = 1, k_B = 1,
beta = 1/T; Z = sum_{s} exp(-beta H); free energy per site f = -T (ln Z)/N.

Exact results (thermodynamic limit): Onsager free energy (double-integral form),
internal energy (elliptic-K closed form), Yang spontaneous magnetization
(T < Tc only). Finite m x n torus: Kaufman's exact partition function, a product
over Bogoliubov angles gamma, cross-checked against brute-force enumeration over
all 2^{mn} configurations (the ground truth). All quantities returned in log
space where relevant to avoid overflow.
"""
import sys
from pathlib import Path

import numpy as np
from scipy import integrate
from scipy.special import ellipk, logsumexp

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.cli import oracle_main  # noqa: E402

J = 1.0


def tc():
    """Critical temperature, Kramers-Wannier self-dual point sinh(2J/Tc) = 1."""
    return 2.0 * J / np.log(1.0 + np.sqrt(2.0))


def lnZ_per_site(K):
    """Onsager (1/N) ln Z in the thermodynamic limit, K = beta J (double integral)."""
    c2, s2 = np.cosh(2 * K), np.sinh(2 * K)
    integrand = lambda t1, t2: np.log(c2 * c2 - s2 * (np.cos(t1) + np.cos(t2)))
    val, _ = integrate.dblquad(integrand, 0, 2 * np.pi, 0, 2 * np.pi,
                               epsabs=1e-12, epsrel=1e-12)
    return np.log(2.0) + val / (8 * np.pi ** 2)


def free_energy(T):
    """Helmholtz free energy per site f(T) = -T (ln Z)/N (thermodynamic limit)."""
    return -T * lnZ_per_site(J / T)


def internal_energy(T):
    """Onsager internal energy per site u(T) via the complete elliptic integral K.

    u = -J coth(2K) [1 + (2/pi)(2 tanh^2(2K) - 1) K(kappa^2)],
    kappa = 2 sinh(2K)/cosh^2(2K), K = beta J. At Tc the elliptic prefactor
    (2 tanh^2 - 1) vanishes, so u(Tc) = -J coth(2K_c) = -sqrt(2) J exactly.
    """
    K = J / T
    s2, c2 = np.sinh(2 * K), np.cosh(2 * K)
    kappa = 2 * s2 / (c2 * c2)
    kappa1 = 2 * np.tanh(2 * K) ** 2 - 1
    # kappa1 -> 0 at Tc kills the log-divergent K(1); take the (zero) limit there.
    term = 0.0 if abs(kappa1) < 1e-13 else (2 / np.pi) * kappa1 * ellipk(kappa * kappa)
    return -J * (c2 / s2) * (1.0 + term)


def magnetization(T):
    """Yang spontaneous magnetization m(T) = (1 - sinh(2J/T)^{-4})^{1/8}.

    Exact ONLY for T < Tc (ordered phase); identically 0 for T >= Tc.
    """
    s2 = np.sinh(2 * J / T)
    if s2 <= 1.0:
        return 0.0
    return (1.0 - s2 ** -4) ** 0.125


def partition_function_finite(m, n, beta):
    """Kaufman's exact ln Z for the m x n Ising torus (PBC both directions).

    Z = (1/2)(2 sinh 2K)^{mn/2} (Z1 + Z2 + Z3 + Z4), K = beta J, with
        Z1 = prod_r 2 cosh((m/2) gamma_{2r+1}),  Z2 = prod_r 2 sinh((m/2) gamma_{2r+1}),
        Z3 = prod_r 2 cosh((m/2) gamma_{2r}),    Z4 = prod_r 2 sinh((m/2) gamma_{2r}),
    r = 0..n-1, and cosh(gamma_l) = cosh(2K) coth(2K) - cos(pi l / n). The l = 0
    (even) branch takes the signed value gamma_0 = 2K + ln tanh(K) = 2(K - K*),
    negative for T > Tc, which enters the Z4 sinh product. Returned in log space.
    """
    K = beta * J
    s2, c2 = np.sinh(2 * K), np.cosh(2 * K)
    base = c2 * (c2 / s2)  # cosh(2K) coth(2K)

    def gammas(parity):
        ell = 2 * np.arange(n) + parity
        g = np.arccosh(np.maximum(base - np.cos(np.pi * ell / n), 1.0))
        if parity == 0:
            g[0] = 2 * K + np.log(np.tanh(K))  # signed gamma_0 branch
        return g

    def logprod(g, kind):
        x = 0.5 * m * g
        ax = np.abs(x)
        if kind == "cosh":  # log(2 cosh x)
            return (ax + np.log1p(np.exp(-2 * ax))).sum(), 1.0
        # log|2 sinh x|, sign = prod sign(x)
        return (ax + np.log1p(-np.exp(-2 * ax))).sum(), float(np.prod(np.sign(x)))

    go, ge = gammas(1), gammas(0)
    terms = [logprod(go, "cosh"), logprod(go, "sinh"),
             logprod(ge, "cosh"), logprod(ge, "sinh")]
    logs = np.array([t[0] for t in terms])
    signs = np.array([t[1] for t in terms])
    comb = logsumexp(logs, b=signs)
    return np.log(0.5) + 0.5 * m * n * np.log(2 * s2) + comb


def _enumerate_lnZ(m, n, beta):
    """Ground-truth ln Z by direct sum over all 2^{mn} spin configurations."""
    N = m * n
    bits = (np.arange(2 ** N)[:, None] >> np.arange(N)[None, :]) & 1
    s = (1 - 2 * bits).reshape(-1, m, n)
    bond = ((s * np.roll(s, -1, axis=2)).sum(axis=(1, 2))
            + (s * np.roll(s, -1, axis=1)).sum(axis=(1, 2)))
    return logsumexp(beta * J * bond)


def compute(T=2.0, L=4):
    """2D Ising exact quantities: thermodynamic-limit statics + finite L x L torus ln Z."""
    return {
        "tc": tc(),
        "free_energy": free_energy(T),
        "magnetization": magnetization(T),
        "internal_energy": internal_energy(T),
        "logZ_finite": partition_function_finite(L, L, 1.0 / T),
    }


def self_test():
    # anchor 1: critical temperature closed form
    assert abs(tc() - 2.269185314213022) < 1e-12
    # anchor 2: Kaufman ln Z == brute-force enumeration (the ground truth);
    # the asymmetric (3, 4) torus exercises the m/n role assignment
    for m, n in [(3, 3), (4, 4)]:
        for beta in [0.2, 0.4406868, 1.0]:
            k = partition_function_finite(m, n, beta)
            e = _enumerate_lnZ(m, n, beta)
            assert abs(k - e) <= 1e-10 * abs(e), (m, n, beta, k, e)
    k = partition_function_finite(3, 4, 0.4406868)
    e = _enumerate_lnZ(3, 4, 0.4406868)
    assert abs(k - e) <= 1e-10 * abs(e), (3, 4, k, e)
    # anchor 3: internal energy at criticality equals -sqrt(2) exactly
    assert abs(internal_energy(tc()) + np.sqrt(2.0)) < 1e-10
    # anchor 4: free-energy consistency, u = f - T df/dT vs elliptic closed form
    T0, dT = 3.0, 1e-4
    dfdT = (free_energy(T0 + dT) - free_energy(T0 - dT)) / (2 * dT)
    assert abs((free_energy(T0) - T0 * dfdT) - internal_energy(T0)) < 1e-6
    # magnetization regime guard: zero at/above Tc, ordered below
    assert magnetization(tc() * 1.01) == 0.0
    assert abs(magnetization(2.0) - 0.911319377877496) < 1e-12


if __name__ == "__main__":
    oracle_main(compute, {"T": (float, 2.0), "L": (int, 4)})
