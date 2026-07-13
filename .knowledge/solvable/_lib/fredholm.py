"""Gauss-Legendre Nystrom solver for 1D linear Fredholm equations of the 2nd kind.

Solves the density equation

    rho(x) - (1/2pi) int_{-B}^{B} K(x, y) rho(y) dy = g(x)

for rho on [-B, B], returning the Gauss-Legendre nodes, weights and rho at the
nodes so a caller can evaluate any functional int f(x) rho(x) dx = sum_i w_i
f(x_i) rho_i by a plain weighted sum.

The (1/2pi) prefactor is baked in because every Bethe-ansatz thermodynamic-limit
density equation in this catalog (Lieb-Liniger, Yang-Gaudin, ...) carries exactly
that factor; fold any additional constant into `kernel`.  The driving term
defaults to the flat source g(x) = 1/(2pi) shared by those same equations and is
overridable (e.g. for the coupled Yang-Gaudin block system a caller assembles the
Nystrom matrix directly from `nodes_weights`).

Nystrom discretization: on the n Gauss-Legendre nodes {x_i} with weights {w_i}
the integral becomes sum_j K(x_i, x_j) w_j rho_j, so the equation is the linear
system

    (I - (1/2pi) K W) rho = g,   M_ij = delta_ij - (1/2pi) K(x_i, x_j) w_j,

solved by a dense LU.  Analytic anchors (K == 0 and K == const) are pinned in
tests/test_lib.py.
"""
import numpy as np

TWO_PI = 2.0 * np.pi


def nodes_weights(B, n=256):
    """n-point Gauss-Legendre nodes and weights on the interval [-B, B]."""
    x, w = np.polynomial.legendre.leggauss(n)
    return B * x, B * w


def solve(kernel, B, n=256, g=None):
    """Solve rho(x) - (1/2pi) int_{-B}^{B} K(x,y) rho(y) dy = g(x).

    Parameters
    ----------
    kernel : callable K(x, y) that broadcasts over numpy arrays (it is called
             once with shapes (n, 1) and (1, n) to build the full matrix).
    B      : half-width of the integration interval.
    n      : number of Gauss-Legendre nodes (default 256).
    g      : driving term callable g(x); default is the flat source 1/(2pi).

    Returns
    -------
    (x, w, rho) : nodes, quadrature weights, and rho evaluated at the nodes.
    """
    x, w = nodes_weights(B, n)
    if g is None:
        rhs = np.full(n, 1.0 / TWO_PI)
    else:
        rhs = np.asarray(g(x), dtype=float) * np.ones(n)
    K = kernel(x[:, None], x[None, :])
    M = np.eye(n) - (K * w[None, :]) / TWO_PI
    rho = np.linalg.solve(M, rhs)
    return x, w, rho
