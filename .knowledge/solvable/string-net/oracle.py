"""Levin-Wen string-net oracle: quantum dimensions + doubled anyon count / GSD.

A Levin-Wen string-net model is built from an input unitary fusion category:
simple objects (string types) i with fusion rules i x j = sum_k N^k_ij k. The
exactly solvable commuting-projector Hamiltonian H = -sum_v Q_v - sum_p B_p has
a ground state that is a weighted loop/string-net gas, and realizes the DOUBLED
(Drinfeld-center) topological phase of the input category.

This script computes, from the fusion tensor N^k_ij alone:
  * the quantum dimension d_i of each simple object as the Perron-Frobenius
    (largest) eigenvalue of the fusion matrix (N_i)_{jk} = N^k_ij;
  * the total quantum dimension squared D^2 = sum_i d_i^2;
  * the number of anyons of the doubled theory and the torus GSD.

For a modular (multiplicity-free) input category the Drinfeld double has
(#simple objects)^2 anyon types, and the torus GSD equals that count. This
counting is stated here only for the two multiplicity-free inputs shipped
(fibonacci, ising), where it is verified; the safe exact claim is the g=1
(torus) count (see ORACLE.md).

PARTIAL (P) oracle: the quantum dimensions, D^2, doubled anyon count and torus
GSD are exact, but the F-symbols / full Levin-Wen plaquette Hamiltonian and the
explicit string-net ground-state wavefunction are exact-but-NOT-built here.

Fibonacci: {1, tau}, tau x tau = 1 + tau, d_tau = phi = (1+sqrt5)/2, GSD = 4
(doubled Fibonacci, DFib). Ising: {1, sigma, psi}, sigma x sigma = 1 + psi,
sigma x psi = sigma, psi x psi = 1, d_sigma = sqrt2, GSD = 9 [@LevinWen2005].
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.cli import oracle_main  # noqa: E402


def _fibonacci():
    """Objects (1, tau); fusion tau x tau = 1 + tau."""
    labels = ["1", "tau"]
    N = np.zeros((2, 2, 2))  # N[i,j,k] = N^k_{ij}
    # 1 is the unit: 1 x x = x x 1 = x
    for x in range(2):
        N[0, x, x] = 1
        N[x, 0, x] = 1
    N[1, 1, 0] = 1  # tau x tau contains 1
    N[1, 1, 1] = 1  # tau x tau contains tau
    return labels, N


def _ising():
    """Objects (1, sigma, psi); sigma^2 = 1 + psi, sigma psi = sigma, psi^2 = 1."""
    labels = ["1", "sigma", "psi"]
    N = np.zeros((3, 3, 3))
    for x in range(3):
        N[0, x, x] = 1
        N[x, 0, x] = 1
    N[1, 1, 0] = 1  # sigma x sigma -> 1
    N[1, 1, 2] = 1  # sigma x sigma -> psi
    N[1, 2, 1] = 1  # sigma x psi -> sigma
    N[2, 1, 1] = 1  # psi x sigma -> sigma
    N[2, 2, 0] = 1  # psi x psi -> 1
    return labels, N


CATEGORIES = {"fibonacci": _fibonacci, "ising": _ising}


def quantum_dimensions(N):
    """d_i = Perron-Frobenius (largest) eigenvalue of fusion matrix (N_i)_{jk}."""
    dims = []
    for i in range(N.shape[0]):
        Ni = N[i]  # (Ni)_{jk} = N^k_{ij}, a nonnegative matrix
        eig = np.linalg.eigvals(Ni)
        dims.append(float(np.max(eig.real)))
    return dims


def compute(category="fibonacci"):
    """String-net quantum dimensions + doubled anyon count / torus GSD."""
    if category not in CATEGORIES:
        raise ValueError(f"unknown category {category!r}; choose from {sorted(CATEGORIES)}")
    labels, N = CATEGORIES[category]()
    dims = quantum_dimensions(N)
    n_simple = len(labels)
    n_anyons_doubled = n_simple ** 2  # Drinfeld double of a multiplicity-free input
    return {
        "n_simple": n_simple,                              # #simple objects (string types)
        "d_max": max(dims),                                # largest quantum dimension
        "total_quantum_dim_sq": float(sum(d * d for d in dims)),  # D^2 = sum_i d_i^2
        "n_anyons_doubled": n_anyons_doubled,              # #anyons of doubled theory = n_simple^2
        "gsd_torus": n_anyons_doubled,                     # torus GSD = #anyons
    }


def self_test():
    phi = (1.0 + np.sqrt(5.0)) / 2.0
    # ---- Fibonacci ----
    labels, N = _fibonacci()
    dims = quantum_dimensions(N)
    d_tau = dims[labels.index("tau")]
    assert abs(d_tau - phi) < 1e-12, d_tau           # d_tau = golden ratio phi
    r = compute(category="fibonacci")
    assert abs(r["d_max"] - phi) < 1e-12, r
    assert r["gsd_torus"] == 4, r                    # doubled Fibonacci (DFib): 2^2 anyons
    assert r["n_simple"] == 2 and r["n_anyons_doubled"] == 4, r
    assert abs(r["total_quantum_dim_sq"] - (1.0 + phi ** 2)) < 1e-12, r  # D^2 = 1 + phi^2
    # ---- Ising ----
    labels, N = _ising()
    dims = quantum_dimensions(N)
    d_sigma = dims[labels.index("sigma")]
    d_psi = dims[labels.index("psi")]
    assert abs(d_sigma - np.sqrt(2.0)) < 1e-12, d_sigma  # d_sigma = sqrt2
    assert abs(d_psi - 1.0) < 1e-12, d_psi               # d_psi = 1
    r = compute(category="ising")
    assert r["gsd_torus"] == 9, r                    # doubled Ising: 3^2 anyons
    assert r["n_simple"] == 3 and r["n_anyons_doubled"] == 9, r
    assert abs(r["total_quantum_dim_sq"] - 4.0) < 1e-12, r  # D^2 = 1 + 2 + 1 = 4
    # gsd_torus == n_anyons_doubled for both inputs.
    for cat in ("fibonacci", "ising"):
        c = compute(category=cat)
        assert c["gsd_torus"] == c["n_anyons_doubled"], cat


if __name__ == "__main__":
    oracle_main(compute, {"category": (str, "fibonacci")})
