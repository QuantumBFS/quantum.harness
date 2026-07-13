"""Yang-Gaudin gas oracle: balanced spin-1/2 delta-repulsive fermions in 1D.

    H = -sum_i d^2/dx_i^2 + 2c sum_{i<j} delta(x_i - x_j),   c > 0

Lieb-Liniger units (hbar = 1, m = 1/2); N fermions, balanced spins (N/2 up, N/2
down), density n = N/L, gamma = c/n.  Ground-state energy per particle
E/N = n^2 e(gamma) with the universal coefficient e(gamma) computed here from the
Yang-Gaudin Bethe-ansatz integral equations [@Yang1967; @Gaudin1967].

Nested Bethe ansatz.  The balanced ground state is a spin singlet: charge
rapidities k fill a Fermi sea [-Q, Q] with density rho(k), spin rapidities fill
the WHOLE real axis (B = infinity, zero field) with density sigma(lambda).  They
obey the coupled equations

    rho(k)      = 1/(2pi) + int a1(k - lambda) sigma(lambda) dlambda,
    sigma(lambda) = int_{-Q}^{Q} a1(lambda - k) rho(k) dk
                    - int a2(lambda - lambda') sigma(lambda') dlambda',

with Lorentzian kernels a1(x) = (1/pi)(c/2)/((c/2)^2 + x^2) and
a2(x) = (1/pi) c/(c^2 + x^2) (Fourier transforms e^{-(c/2)|w|}, e^{-c|w|}).

Because the spin sea is the full line, the spin equation is a convolution and is
eliminated EXACTLY by Fourier transform:
    sigma_hat = a1_hat / (1 + a2_hat) * rho_hat,
    a1_hat^2 / (1 + a2_hat) = a2_hat / (1 + a2_hat) = 1/(1 + e^{c|w|}),
collapsing the system to a SINGLE well-conditioned equation on the compact charge
interval,

    rho(k) - int_{-Q}^{Q} R(k - k') rho(k') dk' = 1/(2pi),
    R_hat(w) = 1/(1 + e^{c|w|}),

whose real-space kernel has the closed form (digamma psi)

    R(x) = (1/(2 pi c)) Re[ psi(1 + i x/2c) - psi(1/2 + i x/2c) ].

This exact elimination of the infinite spin sea is why we solve the reduced
equation rather than truncate an infinite spin domain in a 2x2 block Nystrom
(which is ill-conditioned at small c); the block form is verified against the
reduced solver in self_test at moderate gamma.  Observables follow as for the
Lieb-Liniger card:

    n = int_{-Q}^{Q} rho dk,   E/L = int_{-Q}^{Q} k^2 rho dk,
    gamma = c/n,               e(gamma) = (E/L)/n^3 = I2 / I0^3.

Anchors (derived): gamma -> 0 free two-component gas e -> pi^2/12 with leading
first-order shift e = pi^2/12 + gamma/2; gamma -> infinity spin-incoherent
impenetrable limit e -> pi^2/3 (cross-card to tonks-girardeau); monotonicity;
solver-resolution convergence.
"""
import importlib.util
import sys
from pathlib import Path

import numpy as np
from scipy import special
from scipy.optimize import brentq

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.cli import oracle_main  # noqa: E402
from _lib import fredholm  # noqa: E402

PI = np.pi
FREE_E = PI ** 2 / 12.0   # e(gamma -> 0), two half-filled Fermi seas
TONKS_E = PI ** 2 / 3.0   # e(gamma -> infinity), spin-incoherent impenetrable


def _R_kernel(x, c):
    """Reduced spin-eliminated kernel R(x), R_hat(w) = 1/(1 + e^{c|w|})."""
    z = 1j * x / (2.0 * c)
    return (1.0 / (2.0 * PI * c)) * np.real(special.digamma(1.0 + z)
                                            - special.digamma(0.5 + z))


def _charge_solution(c, Q, n):
    """Solve the reduced charge equation on [-Q, Q]; return (I0, I2)."""
    # fredholm.solve subtracts (1/2pi) int K rho; fold the 2pi so K = 2pi R.
    kernel = lambda X, Y: 2.0 * PI * _R_kernel(X - Y, c)  # noqa: E731
    k, w, rho = fredholm.solve(kernel, B=Q, n=n)
    I0 = float(w @ rho)
    I2 = float(w @ (k ** 2 * rho))
    return I0, I2


def gamma_of_Q(c, Q, n=256):
    """gamma = c / n(Q); with c fixed, gamma decreases as Q grows."""
    I0, _ = _charge_solution(c, Q, n)
    return c / I0


def _Q_for_gamma(gamma, c=1.0, n=256):
    """Invert the monotone map gamma(Q) at fixed c for the requested gamma."""
    lo, hi = 1.0, 1.0
    while gamma_of_Q(c, lo, n) < gamma:   # smaller Q -> larger gamma
        lo /= 2.0
    while gamma_of_Q(c, hi, n) > gamma:   # larger Q -> smaller gamma
        hi *= 2.0
    return brentq(lambda Q: gamma_of_Q(c, Q, n) - gamma, lo, hi,
                  xtol=1e-12, rtol=1e-14)


def e_of_gamma(gamma, n=256):
    """Ground-state energy coefficient e(gamma), E/N = n^2 e(gamma)."""
    c = 1.0
    Q = _Q_for_gamma(gamma, c, n)
    I0, I2 = _charge_solution(c, Q, n)
    return I2 / I0 ** 3


def _block_e(gamma, n=160, Bs_fac=12.0):
    """Reference solve via the explicit 2x2 block Nystrom (finite spin cutoff).

    Built directly from fredholm.nodes_weights for both sectors -- the coupled
    form the reduced equation is derived from.  Reliable only at moderate gamma
    (the finite spin cutoff Bs is ill-conditioned as c -> 0); used purely to
    cross-check the reduced solver, not for production values.
    """
    c = 1.0
    Q = _Q_for_gamma(gamma, c, n)
    Bs = Bs_fac * max(Q, c)
    k, wk = fredholm.nodes_weights(Q, n)
    lam, wl = fredholm.nodes_weights(Bs, n)

    def a1(x):
        return (1.0 / PI) * (c / 2.0) / ((c / 2.0) ** 2 + x ** 2)

    def a2(x):
        return (1.0 / PI) * c / (c ** 2 + x ** 2)

    A1_ks = a1(k[:, None] - lam[None, :]) * wl[None, :]
    A1_sk = a1(lam[:, None] - k[None, :]) * wk[None, :]
    A2_ss = a2(lam[:, None] - lam[None, :]) * wl[None, :]
    I = np.eye(n)
    M = np.block([[I, -A1_ks], [-A1_sk, I + A2_ss]])
    rhs = np.concatenate([np.full(n, 1.0 / (2.0 * PI)), np.zeros(n)])
    sol = np.linalg.solve(M, rhs)
    rho = sol[:n]
    I0 = wk @ rho
    I2 = wk @ (k ** 2 * rho)
    return I2 / I0 ** 3


def compute(gamma=1.0, n=256):
    """Yang-Gaudin balanced-fermion ground-state energy coefficient e(gamma)."""
    e = e_of_gamma(gamma, n)
    return {
        "gamma": float(gamma),
        "e_gamma": float(e),
        "energy_per_particle_over_n2": float(e),  # E/N = n^2 * e(gamma)
        "e_free_limit": float(FREE_E),             # e(gamma -> 0) = pi^2/12
        "e_tonks_limit": float(TONKS_E),           # e(gamma -> inf) = pi^2/3
    }


def _load_tonks():
    path = Path(__file__).resolve().parents[1] / "tonks-girardeau" / "oracle.py"
    spec = importlib.util.spec_from_file_location("oracle_tonks_girardeau", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def self_test():
    # anchor 1: WEAK coupling.  The bare free value is e(0) = pi^2/12 (two half-
    # filled Fermi seas, density n/2 each: E/L = 2*(1/2pi) int_{-pi n/2}^{pi n/2}
    # k^2 dk = pi^2 n^3/12).  First-order perturbation in the contact coupling
    # shifts opposite spins only (Pauli kills same-spin contact): E_int/N =
    # 2c*(n/2)^2/n = gamma n^2/2 -> e = pi^2/12 + gamma/2.  Check the DERIVED
    # two-term form at gamma = 0.05 (the raw pi^2/12 is only the gamma -> 0 limit;
    # at gamma = 0.05 the true e is ~3% above it, exactly the +gamma/2 shift).
    gw = 0.05
    e_weak = FREE_E + gw / 2.0
    assert abs(e_of_gamma(gw) / e_weak - 1.0) < 5e-3, (e_of_gamma(gw), e_weak)
    # the bare free value pi^2/12 is recovered once the derived first-order shift
    # gamma/2 is removed (asserting the raw pi^2/12 at gamma=0.05 would be wrong
    # by the +3% shift; the raw value is only the strict gamma -> 0 limit):
    assert abs((e_of_gamma(gw) - gw / 2.0) - FREE_E) / FREE_E < 3e-3
    assert e_of_gamma(gw) > FREE_E  # repulsion raises E above the free gas

    # anchor 2 (CROSS-CARD): STRONG coupling e -> pi^2/3, the spinless Tonks-
    # Girardeau value.  At gamma = 1000 within 2% (cross-loaded, not duplicated).
    tonks = _load_tonks()
    e_strong = e_of_gamma(1000.0)
    assert abs(e_strong / tonks.LL_UNITS_E - 1.0) < 2e-2, (e_strong, tonks.LL_UNITS_E)
    assert abs(TONKS_E - tonks.LL_UNITS_E) < 1e-12  # same constant on both cards

    # anchor 3: e(gamma) monotone increasing, bounded in (pi^2/12, pi^2/3).
    gammas = [0.05, 0.5, 5.0, 50.0, 500.0]
    es = [e_of_gamma(x) for x in gammas]
    assert all(b > a for a, b in zip(es, es[1:])), es
    assert FREE_E < es[0] and es[-1] < TONKS_E

    # anchor 4: solver-resolution convergence n = 128 vs 256.
    assert abs(e_of_gamma(1.0, 128) - e_of_gamma(1.0, 256)) < 1e-8

    # anchor 5: the explicit 2x2 block Nystrom agrees with the reduced solver at
    # moderate gamma (both built on fredholm nodes/weights), validating the
    # Fourier elimination of the spin sea.
    assert abs(_block_e(1.0) / e_of_gamma(1.0) - 1.0) < 1e-2


if __name__ == "__main__":
    oracle_main(compute, {"gamma": (float, 1.0), "n": (int, 256)})
