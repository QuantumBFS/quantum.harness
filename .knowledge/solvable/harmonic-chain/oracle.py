"""1D harmonic (phonon) chain oracle: identical masses m on a ring, nearest-
neighbor springs of constant kappa, lattice constant a = 1, PBC.

H = sum_i [ p_i^2 / (2m) + (kappa/2) (x_i - x_{i+1})^2 ]

Normal-mode dispersion omega(k) = 2 sqrt(kappa/m) |sin(k/2)|, k = 2 pi n / L.
Exact free-boson diagonalization (Fourier + Bogoliubov-trivial, since the
chain is already harmonic/quadratic in x, p): the full spectrum is
sum_k hbar omega(k) (n_k + 1/2), hbar = 1 here.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.cli import oracle_main  # noqa: E402


def omega(k, kappa, m):
    """Phonon dispersion, lattice constant 1."""
    return 2.0 * np.sqrt(kappa / m) * np.abs(np.sin(k / 2.0))


def e0_finite(L, kappa, m):
    """Zero-point energy per site at finite L, PBC momenta k_n = 2 pi n / L."""
    k = 2.0 * np.pi * np.arange(L) / L
    return 0.5 * omega(k, kappa, m).sum() / L


def e0_thermo(kappa, m):
    """L -> inf: e0 = (1/2pi) int_0^{2pi} (1/2) omega(k) dk = (2/pi) sqrt(kappa/m)."""
    return (2.0 / np.pi) * np.sqrt(kappa / m)


def dynamical_matrix(L, kappa, m):
    """PBC spring (dynamical) matrix D such that m x'' = -D x, eigenvalues
    of D are omega(k)^2. D_ii = 2 kappa/m, D_{i,i+-1} = -kappa/m (PBC, so
    the (0, L-1) and (L-1, 0) corners are also -kappa/m)."""
    D = np.zeros((L, L))
    c = kappa / m
    for i in range(L):
        D[i, i] = 2.0 * c
        D[i, (i + 1) % L] -= c
        D[i, (i - 1) % L] -= c
    return D


def compute(L=4000, kappa=1.0, m=1.0):
    """Harmonic chain: zero-point energy and sound speed, exact."""
    return {
        "e0_per_site": e0_finite(L, kappa, m),
        "e0_thermodynamic": e0_thermo(kappa, m),
        "sound_speed": np.sqrt(kappa / m),
    }


def self_test():
    # anchor 1: finite-L zero-point sum -> thermodynamic closed form
    assert abs(compute(L=4000, kappa=1.0, m=1.0)["e0_per_site"] - 2.0 / np.pi) < 1e-6
    # anchor 2: independent path -- dynamical-matrix diagonalization vs the
    # dispersion formula, L=6
    L, kappa, m = 6, 1.0, 1.0
    D = dynamical_matrix(L, kappa, m)
    ev = np.linalg.eigvalsh(D)
    # eigvalsh resolves the exact translational zero mode only to ~1e-16
    # absolute error (matches the closed-form omega^2 there to 1e-15, see
    # below); sqrt amplifies that to ~1e-8, so clip sub-1e-10 noise before
    # taking the square root -- the omega^2 values themselves already agree
    # with the dispersion formula to atol=1e-12 with no clipping needed.
    assert np.allclose(np.sort(np.abs(ev)),
                        np.sort(4.0 * (kappa / m) * np.sin(np.pi * np.arange(L) / L) ** 2),
                        atol=1e-12)
    ev_clipped = np.where(np.abs(ev) < 1e-10, 0.0, np.abs(ev))
    w_dm = np.sqrt(ev_clipped)
    w_disp = np.sort(2.0 * np.abs(np.sin(np.pi * np.arange(L) / L)))
    assert np.allclose(np.sort(w_dm), w_disp, atol=1e-12)
    # anchor 3: sound speed = lim_{k->0} omega(k)/k = sqrt(kappa/m)
    for kappa, m in [(1.0, 1.0), (2.0, 0.5)]:
        k_small = 1e-6
        slope = omega(k_small, kappa, m) / k_small
        assert abs(slope - np.sqrt(kappa / m)) < 1e-6


if __name__ == "__main__":
    oracle_main(compute, {"L": (int, 4000), "kappa": (float, 1.0), "m": (float, 1.0)})
