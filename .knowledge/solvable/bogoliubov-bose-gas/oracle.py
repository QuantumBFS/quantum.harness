"""Bogoliubov theory of the weakly-interacting dilute Bose gas (3D, hbar=1).

Within Bogoliubov theory the quadratic (post-condensate-substitution)
Hamiltonian is diagonalized exactly by a k-space Bogoliubov transformation,
giving the exact excitation spectrum of that quadratic theory:

    eps_k^0 = k^2 / (2m),           eps(k) = sqrt(eps_k^0 (eps_k^0 + 2 g n))

with g the contact coupling and n the (uniform) density. The theory itself
is the leading-order weak-coupling / dilute-gas approximation to the true
interacting Bose gas (valid for n a^3 << 1, a = m g / (4 pi) the s-wave
scattering length) -- see ORACLE.md for the tier statement.
"""
import sys
from pathlib import Path

import numpy as np
from scipy import integrate

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.cli import oracle_main  # noqa: E402


def eps_free(k, m):
    return k ** 2 / (2.0 * m)


def bogoliubov_eps(k, g, n, m):
    ek = eps_free(k, m)
    return np.sqrt(ek * (ek + 2.0 * g * n))


def v2(k, g, n, m):
    """Bogoliubov coherence factor v_k^2 = (eps_k^0 + gn - eps(k)) / (2 eps(k)).

    Naive evaluation subtracts two nearly-equal large numbers at large k
    (eps_k^0 + gn ~ eps(k)) and loses all precision there. Rationalize:
    (eps_k^0+gn)^2 - eps(k)^2 = (gn)^2 exactly, so
        eps_k^0 + gn - eps(k) = (gn)^2 / (eps_k^0 + gn + eps(k))
    which is well-conditioned for all k.
    """
    ek = eps_free(k, m)
    gn = g * n
    ebog = bogoliubov_eps(k, g, n, m)
    numerator = gn ** 2 / (ek + gn + ebog)
    return numerator / (2.0 * ebog)


def _depletion_integrand(k, g, n, m):
    if k == 0:
        # v2(0, ...) is a genuine 0/0 (numerator ~ gn, ebog -> 0); the k^2
        # prefactor kills it in the limit, so short-circuit rather than let
        # k**2 * inf evaluate to nan.
        return 0.0
    return k ** 2 * v2(k, g, n, m)


def depletion_3d(g, n, m):
    """n_ex/n = (1/n) (1/(2pi)^3) int d^3k v_k^2
    = (1/n) (1/(2 pi^2)) int_0^inf k^2 v_k^2(k) dk  (radial integral, angles
    give 4 pi). Numerically UV-convergent: v_k^2 ~ (gn)^2 m^2/k^4 at large k,
    so k^2 v_k^2 ~ 1/k^2 -- convergent but slowly on an unbounded interval,
    so map k = t/(1-t), t in [0,1) to a finite domain before quadrature."""
    def integrand_t(t):
        k = t / (1.0 - t)
        dk_dt = 1.0 / (1.0 - t) ** 2
        return _depletion_integrand(k, g, n, m) * dk_dt

    integral, _ = integrate.quad(integrand_t, 0.0, 1.0, limit=400)
    return integral / (2.0 * np.pi ** 2 * n)


def compute(g=0.1, n=1.0, m=1.0):
    """Bogoliubov dispersion, sound speed, healing length, quantum depletion."""
    gn = g * n
    sound_speed_closed = np.sqrt(gn / m)
    k_small = 1e-4 * np.sqrt(2.0 * m * gn)  # small vs. inverse healing length
    sound_speed = bogoliubov_eps(k_small, g, n, m) / k_small
    healing_length = 1.0 / np.sqrt(2.0 * m * gn)
    a = m * g / (4.0 * np.pi)  # s-wave scattering length, g = 4 pi a / m (hbar=1)
    depletion_3d_closed = (8.0 / (3.0 * np.sqrt(np.pi))) * np.sqrt(n * a ** 3)
    return {
        "sound_speed": float(sound_speed),
        "sound_speed_closed": float(sound_speed_closed),
        "healing_length": float(healing_length),
        "depletion_3d": float(depletion_3d(g, n, m)),
        "depletion_3d_closed": float(depletion_3d_closed),
    }


def self_test():
    r = compute(g=0.1, n=1.0, m=1.0)
    # anchor 1: numeric k->0 slope of eps(k) matches the closed-form sound speed
    assert abs(r["sound_speed"] - np.sqrt(0.1)) < 1e-6
    assert abs(r["sound_speed"] - r["sound_speed_closed"]) < 1e-8
    # anchor 2: numeric depletion integral matches the closed-form (8/3sqrt(pi)) sqrt(na^3)
    assert abs(r["depletion_3d"] / r["depletion_3d_closed"] - 1) < 1e-2
    # anchor 3: phonon limit -- eps(k)/k -> c as k -> 0, converging from above
    c = r["sound_speed_closed"]
    slopes = [bogoliubov_eps(k, 0.1, 1.0, 1.0) / k for k in (1e-2, 1e-3, 1e-4)]
    assert all(s > c for s in slopes)  # eps(k) = c*k*sqrt(1+(k xi/2)^2) > c*k
    assert abs(slopes[-1] - c) < abs(slopes[0] - c)  # monotone convergence


if __name__ == "__main__":
    oracle_main(compute, {"g": (float, 0.1), "n": (float, 1.0), "m": (float, 1.0)})
