"""Lieb-Liniger gas oracle: delta-repulsive bosons in 1D (continuum Bethe ansatz).

    H = -sum_i d^2/dx_i^2 + 2c sum_{i<j} delta(x_i - x_j),   c > 0

Lieb-Liniger units: hbar = 1, m = 1/2 (so the kinetic term is -d^2/dx^2 and each
rapidity k contributes k^2 to the energy).  Density n = N/L, dimensionless
coupling gamma = c/n.  The ground-state energy per particle is

    E/N = n^2 e(gamma),

with e(gamma) a universal dimensionless function computed here from the Lieb
integral equation [@LiebLiniger1963].

Thermodynamic-limit Bethe ansatz.  The ground-state rapidities fill a symmetric
sea [-q, q] with density rho(k) obeying

    rho(k) = 1/(2pi) + (1/2pi) int_{-q}^{q} 2c/(c^2 + (k-k')^2) rho(k') dk' .

Rescaling k = q x, lambda = c/q, g(x) = rho(qx) maps this onto the fixed interval
[-1, 1]:

    g(x) - (1/2pi) int_{-1}^{1} 2 lambda/(lambda^2 + (x-y)^2) g(y) dy = 1/(2pi),

solved by the shared Nystrom routine `_lib.fredholm.solve`.  The physical
observables follow from g by the standard scaling chain

    gamma = lambda / I0,     e(gamma) = I2 / I0^3,
    I0 = int_{-1}^{1} g dx,  I2 = int_{-1}^{1} x^2 g dx

(derivation: n = q I0, E/L = q^3 I2, gamma = c/n, e = (E/L)/n^3).  gamma is
monotone increasing in lambda, so e(gamma) is obtained by inverting gamma(lambda)
for the requested gamma.

Anchors (all derived, see self_test): strong coupling e -> (pi^2/3)(1 - 4/gamma
+ 12/gamma^2) (Tonks-Girardeau limit); weak coupling e -> gamma - (4/3pi)
gamma^{3/2}; monotonicity; solver-resolution convergence.
"""
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import brentq

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.cli import oracle_main  # noqa: E402
from _lib import fredholm  # noqa: E402

PI = np.pi
TONKS_E = PI ** 2 / 3.0  # e(gamma -> infinity), the impenetrable-boson value


def _scaled_solution(lmbda, n):
    """Solve the rescaled Lieb equation on [-1, 1]; return (I0, I2)."""
    kernel = lambda X, Y: 2.0 * lmbda / (lmbda ** 2 + (X - Y) ** 2)  # noqa: E731
    x, w, g = fredholm.solve(kernel, B=1.0, n=n)
    I0 = float(w @ g)
    I2 = float(w @ (x ** 2 * g))
    return I0, I2


def gamma_of_lambda(lmbda, n=256):
    """gamma = lambda / int_{-1}^{1} g dx  (monotone increasing in lambda)."""
    I0, _ = _scaled_solution(lmbda, n)
    return lmbda / I0


def _lambda_for_gamma(gamma, n=256):
    """Invert the monotone map gamma(lambda) for the requested gamma."""
    lo, hi = 1e-3, 1e-3
    # expand the bracket until it straddles the target
    while gamma_of_lambda(lo, n) > gamma:
        lo /= 10.0
    while gamma_of_lambda(hi, n) < gamma:
        hi *= 10.0
    return brentq(lambda lm: gamma_of_lambda(lm, n) - gamma, lo, hi,
                  xtol=1e-13, rtol=1e-14)


def e_of_gamma(gamma, n=256):
    """Ground-state energy coefficient e(gamma), E/N = n^2 e(gamma)."""
    lmbda = _lambda_for_gamma(gamma, n)
    I0, I2 = _scaled_solution(lmbda, n)
    return I2 / I0 ** 3


def compute(gamma=1.0, n=256):
    """Lieb-Liniger ground-state energy coefficient e(gamma) via the Lieb equation."""
    e = e_of_gamma(gamma, n)
    return {
        "gamma": float(gamma),
        "e_gamma": float(e),
        "energy_per_particle_over_n2": float(e),  # E/N = n^2 * e(gamma)
        "e_tonks_limit": float(TONKS_E),           # e(gamma -> inf) = pi^2/3
    }


def self_test():
    # anchor 1: STRONG coupling.  Derived Bogoliubov/Tonks expansion
    #   e(gamma) = (pi^2/3)(1 - 4/gamma + 12/gamma^2 + ...).
    g = 1000.0
    e_strong = TONKS_E * (1.0 - 4.0 / g + 12.0 / g ** 2)
    assert abs(e_of_gamma(g) / e_strong - 1.0) < 1e-3, (e_of_gamma(g), e_strong)

    # anchor 2: WEAK coupling.  Derived expansion e(gamma) = gamma - (4/3pi) gamma^{3/2}.
    gw = 0.01
    e_weak = gw - (4.0 / (3.0 * PI)) * gw ** 1.5
    assert abs(e_of_gamma(gw) / e_weak - 1.0) < 1e-2, (e_of_gamma(gw), e_weak)

    # anchor 3: e(gamma) monotone increasing across four decades.
    gammas = [0.05, 0.5, 5.0, 50.0, 500.0]
    es = [e_of_gamma(x) for x in gammas]
    assert all(b > a for a, b in zip(es, es[1:])), es

    # anchor 4: e(gamma) < pi^2/3 for all finite gamma, approaching it from below.
    assert es[-1] < TONKS_E and e_of_gamma(5000.0) < TONKS_E

    # anchor 5: solver-resolution convergence n = 128 vs 256.
    assert abs(e_of_gamma(1.0, 128) - e_of_gamma(1.0, 256)) < 1e-8


if __name__ == "__main__":
    oracle_main(compute, {"gamma": (float, 1.0), "n": (int, 256)})
